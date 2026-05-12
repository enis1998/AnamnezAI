"""
AnamnezAI — Backend v5.0
AI-Powered Patient Pre-Triage using Gemma 4 via Ollama
Gemma 4 Good Hackathon — Health & Sciences + Ollama Prize Tracks
v5.0: Rate limiting + QR code + Kiosk lock/unlock + CSV export + Print ticket + PWA support
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import AsyncGenerator, Optional
import httpx
import json
import uuid
import os
import tempfile
import asyncio
import base64
import re
import io
import csv
import secrets
import string
from datetime import datetime
import time as _time

# PostgreSQL
from database import get_cursor, get_conn, init_db as pg_init_db, close_pool
import psycopg2.errors

# Load .env file if present
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(_env_path):
        load_dotenv(_env_path)
except ImportError:
    pass

# Sprint 9 — Rate limiting
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    _rate_limit_available = True
except ImportError:
    _rate_limit_available = False

# Sprint 5 — QR code
try:
    import qrcode
    from PIL import Image as PILImage
    _qr_available = True
except ImportError:
    _qr_available = False

# Auth modülü
from auth import (
    init_auth_tables, create_user, get_user_by_email,
    verify_password, create_access_token, get_current_user,
    require_auth, require_doctor, require_admin,
    get_patient_profile, upsert_patient_profile,
    hash_password, audit,
    UserCreate, UserLogin, Token, UserOut, Role
)

# Safety Guardrails modülü
from safety import apply_guardrails, compute_clinical_completeness, build_evidence_map

# ─────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────
OLLAMA_BASE_URL  = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# Primary model: Gemma 4 (e4b) — Gemma 4 Good Hackathon
GEMMA_MODEL      = os.getenv("GEMMA_MODEL", "gemma4:e4b")
MEDGEMMA_MODEL   = os.getenv("MEDGEMMA_MODEL", "medgemma:4b")   # Vision — multimodal analysis
RAG_ENABLED      = os.getenv("RAG_ENABLED", "true").lower() == "true"

# Sprint Fix — GPU/RAM yetersizse num_gpu=0 ile CPU moduna düş
OLLAMA_NUM_GPU   = int(os.getenv("OLLAMA_NUM_GPU", "0"))  # 0 = CPU mode

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama başladığında DB'yi başlat, geçmiş verileri yükle ve modeli önceden ısıt."""
    pg_init_db()
    init_auth_tables()      # ← Kullanıcı tablolarını oluştur (+ demo doktor)
    db_load_all()
    print(f"[AnamnezAI v5.0] PostgreSQL DB hazır")
    # Modeli arka planda ısıt — ilk hasta gelene kadar hazır olsun
    asyncio.create_task(_background_warmup())
    # Sprint 14: Oturum timeout cleanup (30 dk boş kalan oturumlar)
    asyncio.create_task(_session_cleanup_loop())
    yield  # Uygulama çalışıyor
    close_pool()  # Bağlantı havuzunu kapat


app = FastAPI(
    title="AnamnezAI",
    description="AI-Powered Patient Pre-Triage — Gemma 4 + RAG + Vision | Gemma 4 Good Hackathon",
    version="5.0.0",
    lifespan=lifespan,
)

_cors_origins_raw = os.getenv("ALLOWED_ORIGINS", "*")
_cors_origins = (
    ["*"] if _cors_origins_raw.strip() == "*"
    else [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sprint 9 — Rate limiting setup
if _rate_limit_available:
    limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    print("[AnamnezAI] Rate limiting: active (slowapi)")
else:
    # Limiter stub — endpoint dekoratörleri hata vermez
    class _LimiterStub:
        def limit(self, *a, **kw):
            def decorator(f): return f
            return decorator
    limiter = _LimiterStub()

# Kiosk lock state (Sprint 5)
_kiosk_locked = False

# In-memory storage (synced to SQLite)
sessions:  dict[str, dict] = {}
summaries: dict[str, dict] = {}

# SSE subscribers for real-time queue
_queue_subscribers: list[asyncio.Queue] = []

# Model warmup durumu — tüm hastalar bu bayrağı görür
_model_ready = False
_model_warming = False

# ─────────────────────────────────────────────
#  Adaptif soru sayısı — klinik aciliyete göre
# ─────────────────────────────────────────────
_EMERGENCY_KEYWORDS_TR = [
    "göğüs","kalp","nefes","bilinç","bayıl","felç","inme","kanama",
    "şuur","koma","solunum","boğulma","anafilaksi","kriz","uyuşma",
    "şiddetli","korkunç","dayanılmaz","bayılıyorum","ezber","nabız",
]
_EMERGENCY_KEYWORDS_EN = [
    "chest","heart","breath","conscious","faint","stroke","bleed",
    "coma","airway","anaphyl","seizure","severe","terrible","unbearable",
    "crushing","numb","weakness",
]

def _pediatric_interview_steps() -> list[str]:
    """
    Pediatrik triaj için özel mülakat adımları — önce ateş değerini sor.

    Klinik gerekçe:
    - Çocuk ateşi vakasında İLK soru mutlaka ateş derecesi ve süresi olmalı.
      (Komplikasyon soruları ancak ateş ciddiyeti belirlendikten sonra sorulur.)
    - 3 aydan küçük bebekler → herhangi bir ateş = RED (Manchester Triage)
    - 38.5°C üzeri + titreme / ense tutukluğu → RED
    - 38.5°C altı + genel durum iyi → YELLOW/GREEN

    Adım sırası (bağlamsal, klinisyen önceliğine göre):
      1. Başlangıç: Ateş ne zamandır var ve kaç derece? (termometre varsa)
      2. Şiddet: Ateş nasıl seyrediyor — sürekli mi, gelip gidiyor mu?
      3. Eşlik: Ateşle birlikte kusma, ishal, öksürük, döküntü var mı?
      4. Nörolojik: Havale geçirdi mi? Ense sertliği, ışık hassasiyeti?
      5. Genel durum: Uyku hali mi, emmesi/iştahı nasıl?

    Bu adımlar sistem_promptuna enjekte edilir, Gemma 4 bu çerçevede devam eder.
    """
    return [
        "pediatric_step_1_fever_onset",
        "pediatric_step_2_fever_pattern",
        "pediatric_step_3_associated_symptoms",
        "pediatric_step_4_neurological",
        "pediatric_step_5_general_status",
    ]


# Pediatrik şikayetleri tespit eden anahtar kelimeler
_PEDIATRIC_KEYWORDS_TR = [
    "çocuk", "bebek", "kız", "oğlum", "kızım", "bebeğim", "küçük",
    "1 yaş", "2 yaş", "3 yaş", "4 yaş", "5 yaş", "6 yaş", "7 yaş",
    "8 yaş", "9 yaş", "10 yaş", "aylık", "ay", "infant"
]
_PEDIATRIC_KEYWORDS_EN = [
    "child", "baby", "infant", "toddler", "kid", "son", "daughter",
    "months old", "year old", "years old", "pediatric"
]

_PEDIATRIC_FIRST_Q_TR = (
    "Çocuğunuzun ateşi ne zamandır var ve en son ölçtüğünüzde kaç derece gösterdi? "
    "(termometre ile ölçtüyseniz tam değeri paylaşın)"
)
_PEDIATRIC_FIRST_Q_EN = (
    "How long has your child had a fever, and what was the temperature reading the last time you measured it? "
    "(please share the exact value if measured with a thermometer)"
)


def _is_pediatric_case(session: dict) -> bool:
    """Mevcut oturum çocuk hastası mı? Yaş veya şikayet metnine göre belirler."""
    age = session.get("age", 99)
    if age <= 12:
        return True
    # Ebeveynin şikayetini de tara
    complaint = ""
    for qa in session.get("qa_history", []):
        if qa.get("answer"):
            complaint += qa["answer"].lower() + " "
    lang = session.get("language", "tr")
    kw = _PEDIATRIC_KEYWORDS_TR if lang == "tr" else _PEDIATRIC_KEYWORDS_EN
    return any(k in complaint for k in kw)


def _adaptive_steps(complaint: str, age: int, lang: str = "tr") -> int:
    """
    Şikayetin aciliyetine göre soru sayısını belirler.
    - Acil semptomlar (göğüs ağrısı, bilinç kaybı...) → 7 soru
    - Orta (ateş, karın ağrısı, baş ağrısı) → 5 soru
    - Basit (hafif boğaz, öksürük, kırık olmayan ağrı) → 4 soru
    - Yaşlı hasta (≥70) → minimum 5 (atipik sunum riski)
    - Pediatrik (≤12 yaş) → minimum 5 (ateş değeri önce sorulur)
    """
    c = complaint.lower()
    EMERGENCY_KW = _EMERGENCY_KEYWORDS_TR if lang == "tr" else _EMERGENCY_KEYWORDS_EN
    MEDIUM_KW_TR = ["ateş","sıcaklık","karın","mide","baş ağrısı","kusma","ishal","ağrı","şişlik","sarılık","dök"]
    MEDIUM_KW_EN = ["fever","abdominal","stomach","headache","vomit","diarrhea","pain","swelling","jaundice","rash"]
    MEDIUM_KW = MEDIUM_KW_TR if lang == "tr" else MEDIUM_KW_EN

    if any(k in c for k in EMERGENCY_KW):
        base = 7
    elif any(k in c for k in MEDIUM_KW):
        base = 5
    else:
        base = 4

    # Yaşlı hastada minimum 5 — atipik sunum riski
    if age >= 70:
        base = max(base, 5)

    # Pediatrik hastada minimum 5 — ateş değeri ilk sorulur (klinik protokol)
    if age <= 12:
        base = max(base, 5)

    return base


# ─────────────────────────────────────────────
#  PostgreSQL Persistence
# ─────────────────────────────────────────────

def db_save_session(session_id: str, data: dict):
    """Oturumu PostgreSQL'e kaydeder (upsert)."""
    try:
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO sessions (session_id, data, created_at)
                VALUES (%s, %s::jsonb, %s)
                ON CONFLICT (session_id) DO UPDATE SET data = EXCLUDED.data
                """,
                (session_id, json.dumps(data, ensure_ascii=False),
                 data.get("created_at", datetime.utcnow().isoformat()))
            )
    except Exception as e:
        print(f"[DB] Session save error: {e}")

def db_save_summary(session_id: str, data: dict):
    """Klinik özeti PostgreSQL'e kaydeder (upsert)."""
    try:
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO summaries (session_id, data, created_at)
                VALUES (%s, %s::jsonb, %s)
                ON CONFLICT (session_id) DO UPDATE SET data = EXCLUDED.data
                """,
                (session_id, json.dumps(data, ensure_ascii=False),
                 data.get("generated_at", datetime.utcnow().isoformat()))
            )
    except Exception as e:
        print(f"[DB] Summary save error: {e}")

def db_delete_session(session_id: str):
    """Oturumu ve özetini PostgreSQL'den siler."""
    try:
        with get_cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE session_id = %s", (session_id,))
            cur.execute("DELETE FROM summaries WHERE session_id = %s", (session_id,))
    except Exception as e:
        print(f"[DB] Delete error: {e}")

def db_load_all():
    """Tüm oturum ve özetleri PostgreSQL'den belleğe yükler."""
    try:
        with get_cursor() as cur:
            cur.execute("SELECT session_id, data FROM sessions")
            for row in cur.fetchall():
                try:
                    sessions[row["session_id"]] = (
                        row["data"] if isinstance(row["data"], dict) else json.loads(row["data"])
                    )
                except Exception:
                    pass
            cur.execute("SELECT session_id, data FROM summaries")
            for row in cur.fetchall():
                try:
                    summaries[row["session_id"]] = (
                        row["data"] if isinstance(row["data"], dict) else json.loads(row["data"])
                    )
                except Exception:
                    pass
        print(f"[DB] Yüklendi: {len(sessions)} oturum, {len(summaries)} özet")
    except Exception as e:
        print(f"[DB] Load error: {e}")

async def notify_queue_update():
    """Tüm SSE abonelerine kuyruk güncellemesi bildirir."""
    for q in list(_queue_subscribers):
        try:
            await q.put("update")
        except Exception:
            pass


SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "30"))

async def _session_cleanup_loop():
    """Her 5 dakikada bir, 30 dakikadan fazla boş kalan oturumları temizler (Sprint 14)."""
    while True:
        await asyncio.sleep(300)  # 5 dakikada bir çalış
        try:
            now = datetime.utcnow()
            to_delete = []
            for sid, s in list(sessions.items()):
                if s.get("completed") and s.get("is_seen"):
                    continue  # Görülen hastalar zaten arşivde, temizleme
                created_str = s.get("created_at", "")
                if not created_str:
                    continue
                try:
                    created = datetime.fromisoformat(created_str.replace("Z", ""))
                    age_min = (now - created).total_seconds() / 60
                    if age_min > SESSION_TIMEOUT_MINUTES and not s.get("completed"):
                        to_delete.append(sid)
                except Exception:
                    pass
            for sid in to_delete:
                sessions.pop(sid, None)
                summaries.pop(sid, None)
                db_delete_session(sid)
                print(f"[Session] Timeout temizlendi: {sid[:8]}... ({SESSION_TIMEOUT_MINUTES} dk boşta)")
            if to_delete:
                await notify_queue_update()
        except Exception as e:
            print(f"[Session] Cleanup hatası: {e}")


async def _background_warmup():
    """Sunucu başlayınca modeli arka planda VRAM'e yükler.
    Bu sayede ilk hasta geldiğinde model zaten hazırdır — 90sn bekleme olmaz."""
    global _model_ready, _model_warming
    _model_warming = True
    print("[AnamnezAI] Model ısıtılıyor (arka plan)...")
    try:
        # Ollama başlayana kadar bekle (Docker/yeni başlatma durumları için)
        for attempt in range(12):  # max 60sn bekle
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    r = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
                    if r.status_code == 200:
                        break
            except Exception:
                pass
            await asyncio.sleep(5)

        # Model warmup
        async with httpx.AsyncClient(timeout=180.0) as client:
            await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": GEMMA_MODEL, "prompt": "Hi", "stream": False, "options": {"num_predict": 1}},
            )
        _model_ready = True
        print(f"[AnamnezAI] Model hazir: {GEMMA_MODEL} -- Artik tum hastalar hizli yanit alir")
    except Exception as e:
        print(f"[AnamnezAI] Warmup başarısız (model manual tetiklenecek): {e}")
    finally:
        _model_warming = False

# ─────────────────────────────────────────────
#  RAG Init (lazy — sunucu başlangıcını yavaşlatmaz)
# ─────────────────────────────────────────────
_rag_initialized = False

def _init_rag_if_needed():
    global _rag_initialized
    if _rag_initialized or not RAG_ENABLED:
        return
    try:
        import rag as rag_module
        if rag_module.is_rag_available():
            stats = rag_module.get_db_stats()
            if stats.get("total_chunks", 0) == 0:
                rag_module.ingest_builtin_knowledge()
            _rag_initialized = True
    except Exception as e:
        print(f"[RAG] Başlatma atlandı: {e}")

# ─────────────────────────────────────────────
#  Pydantic Models
# ─────────────────────────────────────────────
class VitalSigns(BaseModel):
    blood_pressure: Optional[str] = None    # "120/80 mmHg"
    pulse: Optional[int] = None             # bpm
    temperature: Optional[float] = None    # °C
    spo2: Optional[int] = None             # %
    respiratory_rate: Optional[int] = None  # /dakika

class StartSessionRequest(BaseModel):
    patient_name: str
    age: int
    gender: str
    language: str = "tr"
    vitals: Optional[VitalSigns] = None    # Ön triaj vital bulguları

class AnswerRequest(BaseModel):
    session_id: str
    answer: str

class ImageAnalyzeRequest(BaseModel):
    session_id: str
    image_base64: str        # base64 kodlanmış görüntü (JPEG/PNG)
    image_mime: str = "image/jpeg"
    context: str = ""        # bağlam (örn: "yara fotoğrafı", "cilt döküntüsü", "EKG")

class SessionResponse(BaseModel):
    session_id: str
    question: str
    step: int
    total_steps: int
    claim_code: Optional[str] = None   # misafir oturumda gösterilir

class ClaimSessionRequest(BaseModel):
    claim_code: str   # 6 haneli kısa kod (örn: K7M2P9)

# ── Kısa talep kodu üretici ──────────────────
def _generate_claim_code() -> str:
    """6 haneli benzersiz talep kodu üretir (büyük harf + rakam, karışık değil: 0/O/1/I yok)."""
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(chars) for _ in range(6))

class ClinicalSummaryResponse(BaseModel):
    session_id: str
    patient_name: str
    age: int
    gender: str
    triage_level: str
    triage_color: str
    confidence_score: int
    chief_complaint: str
    symptoms_summary: str
    possible_conditions: list[str]
    urgency_flags: list[str] = []
    recommended_action: str
    clinical_notes: str
    vitals: Optional[dict] = None
    image_findings: Optional[str] = None
    generated_at: str

    # Trust Layer (Sprint 20)
    evidence: list[str] = []
    guideline_sources: list[str] = []
    doctor_review_required: bool = True
    unsafe_to_self_manage: bool = True

    # Sprint 21 — Clinical intelligence
    clinical_completeness_score: int = 0
    missing_information: list[str] = []
    recommended_next_questions: list[str] = []

    # Evidence map: patient quote → clinical finding
    evidence_map: list[dict] = []

    # Safety guardrails
    safety_guardrail_triggered: bool = False
    guardrail_rules_fired: list[str] = []

    # Local AI proof
    ai_execution_log: dict = {}

# ─────────────────────────────────────────────
#  Ollama /api/chat Helpers
# ─────────────────────────────────────────────
async def ask_gemma(prompt: str, system: str = "", timeout: float = 180.0,
                    model: Optional[str] = None) -> str:
    """Ollama /api/chat üzerinden model isteği gönderir. model=None → GEMMA_MODEL.

    LATENCY CONTEXT (demo / jüri için):
    - Ortalama inference süresi: 11–39 saniye (RTX 8 GB GPU, think=False)
    - `think: False` zorunlu — thinking modu aktif olursa token kotası boşa harcanır ve yanıt üretilemez.
    - Karşılaştırma: Geleneksel manuel triaj ~22 dakika (Gaziantep STEMI senaryosu).
    - AI triaj 15-40 saniye → klinisyen için 22 dakikalık bilgi birikimini sağlar.
    - Demo sırasında bekleme süresini "AI pre-triage: ~15 sn — manuel triaj: 22 dk" bağlamıyla sun.
    """
    _model = model or GEMMA_MODEL
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": _model,
                    "messages": messages,
                    "stream": False,
                    "think": False,
                    "options": {
                        "temperature": 0.25,
                        "top_p": 0.85,
                        "top_k": 40,
                        "num_predict": 512,
                        "repeat_penalty": 1.1,
                        "num_gpu": OLLAMA_NUM_GPU,
                    },
                },
            )
            resp.raise_for_status()
            raw = resp.json()["message"]["content"].strip()
            return clean_gemma_response(raw)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Ollama çalışmıyor. Terminal'de: ollama serve")
    except httpx.ReadTimeout:
        raise HTTPException(status_code=504, detail=f"Model yanıt vermedi (timeout {int(timeout)}sn).")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Bağlantı zaman aşımı. Ollama servisini kontrol edin.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model hatası ({_model}): {str(e)}")


async def ask_gemma_vision(prompt: str, image_base64: str, system: str = "", timeout: float = 180.0) -> str:
    """Gemma 4 multimodal — görüntü + metin analizi (Ollama vision API)."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({
        "role": "user",
        "content": prompt,
        "images": [image_base64],
    })
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": GEMMA_MODEL,
                    "messages": messages,
                    "stream": False,
                    "think": False,          # ← Thinking modunu kapat
                    "options": {"temperature": 0.2, "top_p": 0.9, "num_predict": 600, "num_gpu": OLLAMA_NUM_GPU},
                },
            )
            resp.raise_for_status()
            raw = resp.json()["message"]["content"].strip()
            return clean_gemma_response(raw)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Ollama çalışmıyor.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vision analizi hatası: {str(e)}")


async def ask_gemma_rag(prompt: str, system: str = "", rag_query: str = "",
                        timeout: float = 180.0, model: Optional[str] = None,
                        rag_mode: str = "interview") -> str:
    """RAG bağlamıyla güçlendirilmiş model isteği.
    rag_mode: 'interview' (soru üretimi) | 'triage' (triaj kararı)
    """
    enriched_system = system
    if RAG_ENABLED and rag_query:
        try:
            _init_rag_if_needed()
            import rag as rag_module
            if rag_mode == "triage":
                # Triaj için daha kapsamlı, kategori öncelikli retrieval
                context = rag_module.get_medical_context_for_triage(
                    chief_complaint=rag_query,
                    min_relevance=0.38,
                )
            else:
                # Mülakat sorularında genel retrieval (hızlı)
                context = rag_module.get_context_for_prompt(
                    rag_query, n_results=5, min_relevance=0.35
                )
            if context:
                enriched_system = system + "\n\n" + context if system else context
        except Exception as _e:
            pass  # RAG başarısız olsa da model çalışmaya devam eder
    return await ask_gemma(prompt, system=enriched_system, timeout=timeout, model=model)


async def stream_gemma(prompt: str, system: str = "") -> AsyncGenerator[str, None]:
    """Gemma 4'ten token token streaming (SSE için). Tekrar eden metin algılama dahil.
    Sprint 14: Think bloğu yarım gelirse buffer'la (edge case fix)."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream(
                "POST",
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": GEMMA_MODEL,
                    "messages": messages,
                    "stream": True,
                    "think": False,
                    "options": {
                        "temperature": 0.4,
                        "top_p": 0.85,
                        "num_predict": 400,       #Max token — sonsuz döngü önlemi
                        "repeat_penalty": 1.35,   # Yüksek penalty → tekrar engeller
                        "repeat_last_n": 64,
                        "num_gpu": OLLAMA_NUM_GPU,
                    },
                },
            ) as resp:
                in_think_block = False
                think_buffer = ""   # Sprint 14: yarım think bloğu için buffer
                accumulated = ""
                async for line in resp.aiter_lines():
                    if line.strip():
                        try:
                            chunk = json.loads(line)
                            token = chunk.get("message", {}).get("content", "")
                            if token:
                                # Sprint 14: Think bloğu buffer'lama — yarım gelebilir
                                if not in_think_block:
                                    # <think> başlangıcı bu token'da mı?
                                    if "<think" in token.lower():
                                        in_think_block = True
                                        think_buffer = token
                                        # Token'ın think öncesi kısmını gönder
                                        pre = re.split(r'<think(?:ing)?>', token, maxsplit=1, flags=re.IGNORECASE)[0]
                                        if pre.strip():
                                            accumulated += pre
                                            yield f"data: {json.dumps({'token': pre})}\n\n"
                                        continue
                                    accumulated += token
                                    # Sunucu tarafı tekrar algılama — son 80 karı saymak yerine
                                    # sadece son 320 karaktere bak: O(1) pencere kontrolü
                                    if len(accumulated) > 400:
                                        window = accumulated[-320:]
                                        tail = accumulated[-80:]
                                        if window.count(tail) >= 3:
                                            yield "data: [DONE]\n\n"
                                            return
                                    yield f"data: {json.dumps({'token': token})}\n\n"
                                else:
                                    # Think bloğu içindeyiz — buffer'a ekle
                                    think_buffer += token
                                    if "</think>" in think_buffer.lower():
                                        in_think_block = False
                                        # Think bloğundan sonraki içeriği gönder
                                        post_match = re.split(r'</think(?:ing)?>', think_buffer, maxsplit=1, flags=re.IGNORECASE)
                                        if len(post_match) > 1 and post_match[1].strip():
                                            post = post_match[1]
                                            accumulated += post
                                            yield f"data: {json.dumps({'token': post})}\n\n"
                                        think_buffer = ""
                            if chunk.get("done"):
                                yield "data: [DONE]\n\n"
                                break
                        except json.JSONDecodeError:
                            continue
    except httpx.ConnectError:
        yield f"data: {json.dumps({'error': 'Ollama bağlantısı yok'})}\n\n"

# ─────────────────────────────────────────────
#  Gemma 4 Sistem Promptları
# ─────────────────────────────────────────────
SYSTEM_PROMPT_TR = """Sen AnamnezAI — deneyimli, empatik bir tıbbi pre-triaj asistanısın.
Gemma 4 tarafından güçlendiriliyorsun ve tamamen yerel (Ollama) çalışıyorsun.
UZMANLIK: Türkçe tıbbi terminoloji (dispne, taşikardi, diyaforez, presenkop, pallor, siyanoz, bradikardi, hipertansif kriz, troponin) ile düşün; halkın anlayacağı dilde sor.
GÖREV: Hastanın semptomlarını anlamak için klinik açıdan değerli, bağlamsal sorular sor.
KURALLAR:
- Her seferinde SADECE 1 soru sor (maksimum 2 cümle).
- Önceki cevapları dikkate alarak soru üret (bağlamsal mülakat).
- Tıbbi jargon kullanma, halkın anlayacağı dil kullan.
- ACİL semptomlar VARSA ÖNCE BUNLARI DETAYLANDIR:
  * Göğüs ağrısı/baskısı → sol kol/çene/sırt yayılımı, terleme, nefes darlığı?
  * Nefes darlığı → ani mi, SpO2 ölçüldü mü, önceki akciğer hastalığı?
  * Bilinç değişikliği/bayılma → kaç saniye sürdü, öncesinde çarpıntı/terleme?
  * Felç bulguları (yüz asimetrisi, kol güçsüzlüğü, konuşma bozukluğu) → tam olarak ne zaman başladı?
  * Şiddetli baş ağrısı → "hayatımın en kötüsü" mü, ense sertliği, ışık hassasiyeti?
- OPQRST çerçevesini uygula: Başlangıç, Şiddet (1-10), Kalite, Yayılım, Tetikleyici, Süre.
- MTS (Manchester Triage System) kriterlerine göre değerlendir.
- Empatik, sakinleştirici ton. Soru işaretiyle bitir.

ÖRNEK MÜLAKAT:
Hasta: Ali Yılmaz, 58 yaş, Erkek.
S: "Merhaba Ali Bey, sizi bugün buraya getiren en önemli şikayetiniz nedir?"
C: "Göğsümde baskı hissediyorum sabahtan beri."
S: "Bu baskı hissi elinize, kolunuza ya da çenenize yayılıyor mu?"
C: "Evet, sol koluma kadar geliyor."
S: "Bu his 1'den 10'a kadar bir skalada kaç olur ve nefes almakta güçlük çekiyor musunuz?"

BU ÖRNEĞİ İZLE — Bağlamsal, derinleştirici ve klinisyen gibi düşünen sorular sor."""

SYSTEM_PROMPT_EN = """You are AnamnezAI — an experienced, empathetic medical pre-triage assistant.
Powered by Gemma 4, running 100% locally via Ollama.
EXPERTISE: Think with clinical terminology (dyspnea, tachycardia, diaphoresis, presyncope, pallor, cyanosis, hypertensive crisis); ask in plain language.
TASK: Ask clinically relevant, contextual questions to understand the patient's symptoms.
RULES:
- Ask ONLY ONE question at a time (max 2 sentences).
- Generate questions based on ALL previous answers (contextual interview).
- Avoid medical jargon, use plain language.
- EMERGENCY signs — explore IMMEDIATELY if present:
  * Chest pain/pressure → arm/jaw/back radiation, sweating, breathlessness?
  * Dyspnea → sudden onset, SpO2 measured, prior lung disease?
  * Altered consciousness/syncope → duration, prior palpitations/sweating?
  * Stroke signs (facial droop, arm weakness, speech) → exact onset time?
  * Severe headache → "worst of life", neck stiffness, photophobia?
- Apply OPQRST: Onset, Quality, Radiation, Severity (1-10), Timing, Triggers.
- Apply MTS (Manchester Triage System) criteria throughout.
- Empathetic, calming tone. End with a question mark.

EXAMPLE EXCHANGE:
Patient: John Doe, 58y, Male.
Q: "Hello John, what's the main reason you're here today?"
A: "I've had chest pressure since this morning."
Q: "Does this pressure spread to your arm, jaw, or back?"
A: "Yes, it goes down my left arm."
Q: "On a scale of 1-10 how severe is it, and do you have any difficulty breathing?"

FOLLOW THIS EXAMPLE — contextual, deepening, clinician-like questions."""

TRIAGE_SYSTEM_TR = """Sen Manchester Triage System (MTS) ve CTAS standartlarına göre eğitilmiş klinik triaj uzmanısın (Gemma 4 tarafından güçlendirilmişsin).
Hastanın semptom mülakat geçmişini dikkatle analiz et.

GÜVENLİK KURALI (PATIENT SAFETY FIRST):
- Şüphe halinde her zaman daha yüksek triaj seviyesi seç (GREEN yerine YELLOW, YELLOW yerine RED).
- Yaşlı (≥65), diyabetik veya immünosüpresif hastalarda atipik sunum olabilir — RED eşiğini düşür.
- Göğüs ağrısı + herhangi bir risk faktörü → en az YELLOW, kardiyak şüphe varsa RED.
- "Hayatımın en kötü baş ağrısı" ifadesi → HEP RED (SAK dışlanana kadar).

ÇIKTI: SADECE geçerli JSON döndür. Başka hiçbir metin veya markdown ekleme.
{
  "triage_level": "RED veya YELLOW veya GREEN",
  "confidence_score": 0-100 arası tam sayı,
  "chief_complaint": "Ana şikayet — tek net cümle",
  "symptoms_summary": "Semptom özeti 2-3 cümle",
  "possible_conditions": ["En olası tanı", "İkinci olasılık", "Üçüncü olasılık"],
  "recommended_action": "Önerilen eylem tek cümle",
  "clinical_notes": "Doktor için kritik gözlemler 2-3 cümle",
  "urgency_flags": ["Acil uyarı bayrakları — örn: Kardiyak risk faktörleri mevcut"],
  "evidence": ["Triaj kararını destekleyen klinik bulgu 1", "Bulgu 2", "Bulgu 3"],
  "guideline_sources": ["MTS Göğüs Ağrısı Diskriminatörü", "CTAS Kardiyak Semptomlar"],
  "doctor_review_required": true veya false,
  "unsafe_to_self_manage": true veya false
}
TRİAJ STANDARTLARI (MTS):
RED = Hayati risk / derhal müdahale (AMI, inme, anafilaksi, solunum yetmezliği, GCS<8, şok, status epileptikus, aort diseksiyonu, SAK)
YELLOW = Acil, 30dk-2saat içinde görülmeli (yüksek ateş ≥38.5°C, orta ağrı 4-6/10, taşikardi>130, hipertansif acil şüphesi, ilk konvülsiyon, ciddi dehidrasyon)
GREEN = Rutin (hafif semptom 1-3/10, kronik takip, basit ÜSYE, hafif travma)

KIRMIZI BAYRAKLAR — Bunların HERHANGİ BİRİ varsa RED zorunlu:
- Göğüs ağrısı + sol kol/çene yayılımı + terleme
- SpO2 <90% veya siyanoz
- Bilinç değişikliği (GCS <15)
- Sistolik KB <90 mmHg (hipotansiyon)
- Solunum hızı >30/dk veya <8/dk
- Ani başlayan en şiddetli baş ağrısı
- Fokal nörolojik defisit (felç bulgusu)"""

TRIAGE_SYSTEM_EN = """You are a clinical triage expert trained on Manchester Triage System (MTS) and CTAS standards (powered by Gemma 4).
Carefully analyze the patient's symptom interview history.

PATIENT SAFETY RULE:
- When in doubt, ALWAYS choose a higher triage level (GREEN→YELLOW, YELLOW→RED).
- Elderly (≥65), diabetic, or immunosuppressed patients may present atypically — lower the RED threshold.
- Chest pain + any risk factor → minimum YELLOW, RED if cardiac suspicion.
- "Worst headache of my life" → ALWAYS RED (until SAH excluded).

OUTPUT: Return ONLY valid JSON. No other text or markdown.
{
  "triage_level": "RED or YELLOW or GREEN",
  "confidence_score": integer 0-100,
  "chief_complaint": "Main complaint one sentence",
  "symptoms_summary": "Symptom summary 2-3 sentences",
  "possible_conditions": ["Most likely", "Second", "Third"],
  "recommended_action": "Action one sentence",
  "clinical_notes": "Critical notes for doctor 2-3 sentences",
  "urgency_flags": ["Emergency flags if any"],
  "evidence": ["Clinical finding supporting triage decision 1", "Finding 2", "Finding 3"],
  "evidence_map": [
    {"finding": "Clinical finding", "patient_quote": "Direct patient quote", "risk_weight": "high or medium or low", "supports": "RED or YELLOW or GREEN"}
  ],
  "guideline_sources": ["MTS Chest Pain Discriminator", "CTAS Level 2 Cardiac Symptoms"],
  "doctor_review_required": true or false,
  "unsafe_to_self_manage": true or false
}
TRIAGE STANDARDS (MTS):
RED = Life-threatening / immediate (AMI, stroke, anaphylaxis, respiratory failure, GCS<8, shock, SE, aortic dissection, SAH)
YELLOW = Urgent, within 30min-2hrs (fever ≥38.5°C, moderate pain 4-6/10, tachycardia>130, hypertensive urgency, first seizure, severe dehydration)
GREEN = Routine (mild symptoms 1-3/10, chronic follow-up, simple URTI, minor trauma)

RED FLAGS — ANY of these requires RED:
- Chest pain + left arm/jaw radiation + diaphoresis
- SpO2 <90% or cyanosis
- Altered consciousness (GCS <15)
- Systolic BP <90 mmHg
- RR >30/min or <8/min
- Sudden worst-ever headache
- Focal neurological deficit (stroke signs)"""

VISION_SYSTEM_TR = """Sen klinik görüntü analizi yapan bir tıbbi asistansın (Gemma 4 multimodal).
Sana gönderilen tıbbi görüntüyü (yara, cilt, EKG, röntgen vb.) dikkatle incele.
KURALLAR:
- Gözlemlediğin klinik bulguları net ve sade Türkçe ile açıkla.
- Acil durum bulguları varsa (enfeksiyon, nekroz, MI paterni vb.) açıkça belirt.
- Olası tanı seçeneklerini listele.
- Kesin tanı koyma; "olası", "şüpheli" gibi ifadeler kullan.
- Yanıtı 3-5 cümle ile sınırla."""

VISION_SYSTEM_EN = """You are a medical image analysis assistant (Gemma 4 multimodal).
Carefully examine the medical image (wound, skin, ECG, X-ray, etc.).
RULES:
- Describe clinical findings clearly in plain language.
- If emergency findings are present (infection, necrosis, MI pattern etc.) state clearly.
- List possible diagnoses.
- Do not make definitive diagnoses; use terms like "possibly", "suspicious for".
- Limit response to 3-5 sentences."""

# Triage renk paleti
TRIAGE_COLOR = {"RED": "#ba1a1a", "YELLOW": "#e07b26", "GREEN": "#006a68"}



def get_system_prompt(lang: str) -> str:
    return SYSTEM_PROMPT_TR if lang == "tr" else SYSTEM_PROMPT_EN


def get_triage_system(lang: str) -> str:
    return TRIAGE_SYSTEM_TR if lang == "tr" else TRIAGE_SYSTEM_EN


def vitals_to_dict(v: Optional[VitalSigns]) -> Optional[dict]:
    if not v:
        return None
    d = v.model_dump()
    return {k: val for k, val in d.items() if val is not None} or None


def clean_gemma_response(text: str) -> str:
    """Gemma 4 thinking bloklarını ve gereksiz içerikleri temizler.

    Gemma 4 (gemma4:e4b) bazen <think>...</think> blokları üretir.
    Bu bloklar HTML'de görünmez etiket olarak işlenir → cevap boş görünür.
    """
    # <think>...</think> veya <thinking>...</thinking> bloklarını kaldır
    text = re.sub(r'<think(?:ing)?>.*?</think(?:ing)?>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Baştaki/sondaki markdown code fence varsa kaldır
    text = re.sub(r'^```(?:json)?\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text.strip())
    return text.strip()


# ─────────────────────────────────────────────
#  Auth Endpoints
# ─────────────────────────────────────────────

@app.post("/auth/register", response_model=Token)
async def register(data: UserCreate):
    """Yeni kullanıcı kaydı (varsayılan: hasta). Doktor kaydı için clinic_code gerekli."""
    user = create_user(data)
    token = create_access_token({"sub": user["user_id"], "role": user["role"]})
    return Token(
        access_token=token,
        user=UserOut(**user)
    )


@app.post("/auth/google", response_model=Token)
async def google_auth(body: dict):
    """Google OAuth2 ID token ile giriş / otomatik kayıt (sadece hasta rolü)."""
    import os as _os
    credential = body.get("credential", "")
    if not credential:
        raise HTTPException(status_code=400, detail="Google credential eksik.")

    GOOGLE_CLIENT_ID = _os.getenv("GOOGLE_CLIENT_ID", "")
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=501,
            detail="Google OAuth yapılandırılmamış. GOOGLE_CLIENT_ID env değişkenini ayarlayın."
        )

    try:
        from google.oauth2 import id_token as _gid
        from google.auth.transport import requests as _greq
        id_info = _gid.verify_oauth2_token(credential, _greq.Request(), GOOGLE_CLIENT_ID)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Google token doğrulama başarısız: {exc}")

    email = id_info.get("email", "").lower().strip()
    name  = id_info.get("name") or email.split("@")[0]

    if not email:
        raise HTTPException(status_code=400, detail="Google hesabından e-posta alınamadı.")

    # Kullanıcı var mı? Yoksa otomatik oluştur
    user = get_user_by_email(email)
    if not user:
        import uuid as _uuid
        user_id = str(_uuid.uuid4())
        now = datetime.utcnow().isoformat()
        try:
            with get_cursor() as cur:
                cur.execute(
                    "INSERT INTO users (user_id, name, email, password_hash, role, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
                    (user_id, name, email, hash_password(str(_uuid.uuid4())), "patient", now)
                )
        except psycopg2.errors.UniqueViolation:
            pass
        user = get_user_by_email(email)
        if not user:
            raise HTTPException(status_code=500, detail="Kullanıcı oluşturulamadı.")

    token = create_access_token({"sub": user["user_id"], "role": user["role"]})
    return Token(
        access_token=token,
        user=UserOut(
            user_id=user["user_id"], name=user["name"], email=user["email"],
            role=user["role"], specialty=user.get("specialty"),
            created_at=user["created_at"]
        )
    )


@app.post("/auth/login", response_model=Token)
async def login(data: UserLogin):
    """E-posta + şifre ile giriş — JWT token döndürür."""
    user = get_user_by_email(data.email.lower().strip())
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="E-posta veya şifre hatalı.")
    token = create_access_token({"sub": user["user_id"], "role": user["role"]})
    return Token(
        access_token=token,
        user=UserOut(
            user_id=user["user_id"], name=user["name"], email=user["email"],
            role=user["role"], specialty=user.get("specialty"),
            created_at=user["created_at"]
        )
    )


@app.get("/auth/me", response_model=UserOut)
async def me(current_user: dict = Depends(require_auth)):
    """Mevcut oturum bilgisini döndürür."""
    return UserOut(
        user_id=current_user["user_id"], name=current_user["name"],
        email=current_user["email"], role=current_user["role"],
        specialty=current_user.get("specialty"), created_at=current_user["created_at"]
    )


@app.get("/auth/profile")
async def get_my_profile(current_user: dict = Depends(require_auth)):
    """Hasta profilini döndürür (sadece hasta rolü için)."""
    profile = get_patient_profile(current_user["user_id"])
    return {"user": {k: current_user[k] for k in ("user_id","name","email","role","specialty")},
            "profile": profile or {}}


@app.put("/auth/profile")
async def update_my_profile(body: dict, current_user: dict = Depends(require_auth)):
    """Hasta profilini günceller."""
    upsert_patient_profile(current_user["user_id"], body)
    return {"status": "ok", "message": "Profil güncellendi."}


@app.get("/auth/patients")
async def list_patients(current_user: dict = Depends(require_doctor)):
    """Doktor/admin için kayıtlı hasta listesi."""
    with get_cursor() as cur:
        cur.execute(
            "SELECT user_id, name, email, created_at FROM users WHERE role = 'patient' AND is_active = 1 ORDER BY created_at DESC"
        )
        rows = cur.fetchall()
    return {"patients": [dict(r) for r in rows]}

# ─────────────────────────────────────────────
#  Endpoints
# ─────────────────────────────────────────────

@app.post("/api/warmup")
async def warmup_model():
    """Gemma 4 modelini hafızaya yükler (ilk çağrıyı hızlandırır)."""
    try:
        async with httpx.AsyncClient(timeout=200.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": GEMMA_MODEL, "prompt": "Hi", "stream": False, "options": {"num_predict": 1}},
            )
            resp.raise_for_status()
        return {"status": "warmed_up", "model": GEMMA_MODEL}
    except Exception as e:
        return {"status": "warmup_failed", "error": str(e)}


@app.post("/api/model/compare")
async def compare_models(body: dict):
    """Gemma 4 (gemma4:e4b) ile prompt test endpoint'i."""
    prompt = body.get("prompt", "").strip()
    system = body.get("system", "")
    if not prompt or len(prompt) < 5:
        raise HTTPException(status_code=400, detail="prompt parametresi gerekli (min 5 karakter).")

    results = {}
    try:
        resp_full = await ask_gemma(prompt, system=system, model=GEMMA_MODEL, timeout=120.0)
        results["gemma4"] = {"model": GEMMA_MODEL, "response": resp_full, "status": "ok"}
    except Exception as e:
        results["gemma4"] = {"model": GEMMA_MODEL, "response": None, "status": "error", "error": str(e)}

    return {
        "prompt": prompt,
        "results": results,
        "model": GEMMA_MODEL,
    }


# ─────────────────────────────────────────────
#  RAG Endpoints
# ─────────────────────────────────────────────

@app.get("/api/rag/status")
async def rag_status():
    if not RAG_ENABLED:
        return {"enabled": False, "reason": "RAG_ENABLED=false"}
    try:
        import rag as rag_module
        if not rag_module.is_rag_available():
            return {"enabled": False, "reason": "chromadb veya sentence-transformers kurulu değil"}
        _init_rag_if_needed()
        stats = rag_module.get_db_stats()
        return {"enabled": True, "initialized": _rag_initialized, **stats}
    except Exception as e:
        return {"enabled": False, "error": str(e)}


@app.post("/api/rag/ingest/text")
async def rag_ingest_text(body: dict):
    text = body.get("text", "")
    source = body.get("source", "user_upload")
    category = body.get("category", "custom")
    if not text or len(text.strip()) < 20:
        raise HTTPException(status_code=400, detail="Metin çok kısa (min 20 karakter).")
    try:
        import rag as rag_module
        _init_rag_if_needed()
        added = rag_module.ingest_text(text, source=source, category=category)
        return {"added_chunks": added, "source": source}
    except ImportError:
        raise HTTPException(status_code=503, detail="RAG bileşenleri kurulu değil.")


@app.post("/api/rag/ingest/pdf")
async def rag_ingest_pdf(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Sadece PDF dosyası kabul edilir.")
    try:
        import rag as rag_module
        contents = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        def _ingest():
            try:
                _init_rag_if_needed()
                count = rag_module.ingest_pdf(tmp_path, source_name=file.filename[:40])
                os.unlink(tmp_path)
                print(f"[RAG] PDF yüklendi: {file.filename} — {count} chunk")
            except Exception as e:
                print(f"[RAG] PDF hatası: {e}")

        if background_tasks:
            background_tasks.add_task(_ingest)
            return {"status": "processing", "filename": file.filename}
        else:
            _ingest()
            stats = rag_module.get_db_stats()
            return {"status": "done", "filename": file.filename, "total_chunks": stats.get("total_chunks")}
    except ImportError:
        raise HTTPException(status_code=503, detail="RAG bileşenleri kurulu değil.")


@app.post("/api/rag/ingest/builtin")
async def rag_ingest_builtin():
    try:
        import rag as rag_module
        added = rag_module.ingest_builtin_knowledge()
        stats = rag_module.get_db_stats()
        return {"added_chunks": added, "total_chunks": stats.get("total_chunks", 0), "sources": stats.get("sources", {})}
    except ImportError:
        raise HTTPException(status_code=503, detail="RAG bileşenleri kurulu değil.")


# ─────────────────────────────────────────────
#  Vision — Tıbbi Görüntü Analizi (MedGemma / Gemma 4 fallback)
# ─────────────────────────────────────────────

async def _get_vision_model() -> str:
    """MedGemma kuruluysa onu, yoksa Gemma 4'ü döner."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get(f"{OLLAMA_BASE_URL}/api/tags")
            names = [m["name"] for m in r.json().get("models", [])]
            if any("medgemma" in n.lower() for n in names):
                return MEDGEMMA_MODEL
    except Exception:
        pass
    return GEMMA_MODEL   # Gemma 4 multimodal fallback


@app.post("/api/analyze-image")
async def analyze_image(
    file: UploadFile = File(...),
    lang: str = "tr",
    session_id: str = ""
):
    """
    Tıbbi görüntü analizi — yara, cilt, EKG, röntgen vb.
    MedGemma (medgemma:4b) varsa kullanır; yoksa Gemma 4 (gemma4:e4b) multimodal ile devam eder.
    """
    # Dosyayı oku & base64'e çevir
    content = await file.read()
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Dosya çok büyük (maks. 15 MB).")

    b64 = base64.b64encode(content).decode()
    vision_model = await _get_vision_model()
    system = VISION_SYSTEM_TR if lang == "tr" else VISION_SYSTEM_EN

    try:
        async with httpx.AsyncClient(timeout=140.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": vision_model,
                    "messages": [
                        {"role": "system", "content": system},
                        {
                            "role": "user",
                            "content": "Bu tıbbi görüntüyü analiz et ve klinik bulgularını açıkla." if lang == "tr" else "Analyze this medical image and explain the clinical findings.",
                            "images": [b64]
                        }
                    ],
                    "stream": False,
                    "options": {"temperature": 0.15}
                }
            )
        resp.raise_for_status()
        findings = resp.json()["message"]["content"].strip()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Görüntü analizi başarısız: {exc}")

    # Session varsa bulgular özete de eklenir
    if session_id and session_id in summaries:
        summaries[session_id]["image_findings"] = findings
        summaries[session_id]["image_model"] = vision_model
        db_save_summary(session_id, summaries[session_id])

    is_medgemma = "medgemma" in vision_model.lower()
    print(f"[Vision] model={vision_model} session={session_id or '—'} is_medgemma={is_medgemma}")
    return {
        "findings": findings,
        "model_used": vision_model,
        "is_medgemma": is_medgemma
    }


@app.get("/api/rag/query")
async def rag_query(q: str, n: int = 4):
    if not q:
        raise HTTPException(status_code=400, detail="q parametresi gerekli.")
    try:
        import rag as rag_module
        _init_rag_if_needed()
        hits = rag_module.retrieve(q, n_results=n)
        return {
            "query": q,
            "results": hits,
            "context_preview": rag_module.get_context_for_prompt(q, n_results=n)[:500] + "...",
        }
    except ImportError:
        raise HTTPException(status_code=503, detail="RAG bileşenleri kurulu değil.")


@app.get("/healthz")
async def healthz():
    """Docker HEALTHCHECK için lightweight endpoint — Ollama'ya bağlanmadan sadece uygulama durumunu döndürür."""
    return {"status": "ok", "version": "5.0.0"}


@app.get("/health")
async def health_check():
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            models = [m["name"] for m in resp.json().get("models", [])]
            model_base = GEMMA_MODEL.split(":")[0]
            gemma_available = any(model_base in m for m in models)
            medgemma_available = any("medgemma" in m.lower() for m in models)

        rag_info = {"rag_enabled": RAG_ENABLED, "rag_chunks": 0}
        if RAG_ENABLED:
            try:
                import rag as rag_module
                if rag_module.is_rag_available():
                    stats = rag_module.get_db_stats()
                    rag_info["rag_chunks"] = stats.get("total_chunks", 0)
                    rag_info["rag_available"] = True
                else:
                    rag_info["rag_available"] = False
            except Exception:
                rag_info["rag_available"] = False

        return {
            "status": "ok",
            "version": "5.0.0",
            "ollama": "connected",
            "gemma_model": GEMMA_MODEL,
            "gemma_available": gemma_available,
            "medgemma_model": MEDGEMMA_MODEL,
            "medgemma_available": medgemma_available,
            "model_ready": _model_ready,
            "model_warming": _model_warming,
            "available_models": models,
            "sessions_active": len(sessions),
            "summaries_cached": len(summaries),
            "session_timeout_minutes": SESSION_TIMEOUT_MINUTES,
            "db_backend": "PostgreSQL",
            **rag_info,
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "ollama": "disconnected",
                "error": str(e),
                "message": "Ollama servisi çalışmıyor veya bağlantı kurulamadı. Lütfen 'ollama serve' komutunu çalıştırın."
            }
        )



@app.post("/api/session/start")
@limiter.limit("20/minute")
async def start_session(req: StartSessionRequest, request: Request, current_user: Optional[dict] = Depends(get_current_user)):
    """Yeni hasta mülakatı başlatır — ilk soru anında döner (model çağrısı yok), 2. sorudan itibaren Gemma 4 + RAG devreye girer."""
    session_id = str(uuid.uuid4())
    lang = req.language

    vitals_dict = vitals_to_dict(req.vitals)
    vitals_ctx = ""

    # ── Adaptif soru sayısı ──────────────────
    # Hasta ilk girdiğinde şikayeti henüz yok ama ad/yaş/cinsiyet var.
    # İlk soru geldikten sonra (answer sırasında) adaptif sayı güncellenir.
    # Başlangıçta 5 kullan, ilk cevaptan sonra otomatik ayarlanır.
    initial_steps = 5
    if vitals_dict:
        parts = []
        if req.vitals.blood_pressure: parts.append(f"KB: {req.vitals.blood_pressure}")
        if req.vitals.pulse: parts.append(f"Nabız: {req.vitals.pulse} bpm")
        if req.vitals.temperature: parts.append(f"Ateş: {req.vitals.temperature}°C")
        if req.vitals.spo2: parts.append(f"SpO2: {req.vitals.spo2}%")
        if req.vitals.respiratory_rate: parts.append(f"SS: {req.vitals.respiratory_rate}/dk")
        if parts:
            vitals_ctx = f"\nVital bulgular: {', '.join(parts)}" if lang == "tr" else f"\nVitals: {', '.join(parts)}"

    # ── İlk soru: anında sabit yanıt — model çağrısı YOK ──────────────────
    # İlk soru her zaman "Ana şikayetiniz nedir?" eşdeğeridir.
    # AI gücü 2. sorudan itibaren hastanın cevabını analiz ederek devreye girer.
    _name = req.patient_name.split()[0] if req.patient_name else ""
    _vitals_note = f" (Vital bulgular kaydedildi.)" if vitals_dict and lang == "tr" else (" (Vitals recorded.)" if vitals_dict else "")
    if lang == "tr":
        first_question = (
            f"Merhaba {_name}! 👋 Bugün sizi buraya getiren şikayetiniz nedir?"
            f"{_vitals_note}"
        )
    elif lang == "ar":
        first_question = (
            f"مرحباً {_name}! 👋 ما هي الشكوى التي أحضرتك إلى هنا اليوم?"
            f"{_vitals_note}"
        )
    else:
        first_question = (
            f"Hello {_name}! 👋 What brings you in today — what's your main concern?"
            f"{_vitals_note}"
        )

    # 6 haneli kısa talep kodu — misafir oturum iken kullanıcı bu kodu girerek mülakatı hesabına ekler
    claim_code = _generate_claim_code() if not (current_user) else None

    sessions[session_id] = {
        "patient_name": req.patient_name,
        "age": req.age,
        "gender": req.gender,
        "language": lang,
        "step": 1,
        "total_steps": initial_steps,
        "qa_history": [{"question": first_question, "answer": None}],
        "completed": False,
        "vitals": vitals_dict,
        "image_analyses": [],
        "patient_id": current_user["user_id"] if current_user else None,
        "claim_code": claim_code,
        "created_at": datetime.utcnow().isoformat(),
    }
    db_save_session(session_id, sessions[session_id])
    await notify_queue_update()

    return SessionResponse(session_id=session_id, question=first_question, step=1, total_steps=initial_steps, claim_code=claim_code)


@app.post("/api/session/claim")
async def claim_session(req: ClaimSessionRequest, current_user: dict = Depends(require_auth)):
    """Kullanıcı 6 haneli talep kodunu girerek misafir mülakatını hesabına bağlar."""
    code = req.claim_code.strip().upper()

    # Bellekteki ve DB'deki oturumları kısa kod ile ara
    found_id = None
    found_session = None

    # 1. Önce in-memory'de ara
    for sid, s in sessions.items():
        if s.get("claim_code") == code:
            found_id = sid
            found_session = s
            break

    # 2. Bellekte yoksa DB'de ara
    if not found_id:
        try:
            with get_cursor() as cur:
                cur.execute("SELECT session_id, data FROM sessions")
                rows = cur.fetchall()
            for row in rows:
                s = row["data"] if isinstance(row["data"], dict) else json.loads(row["data"])
                if s.get("claim_code") == code:
                    found_id = row["session_id"]
                    found_session = s
                    sessions[found_id] = s  # belleğe yükle
                    break
        except Exception:
            pass

    if not found_id or not found_session:
        raise HTTPException(status_code=404, detail="Geçersiz kod. Lütfen mülakat sonunda gösterilen 6 haneli kodu doğru girin.")

    if found_session.get("patient_id"):
        if str(found_session["patient_id"]) == str(current_user["user_id"]):
            return {"status": "already_claimed", "session_id": found_id,
                    "patient_name": found_session.get("patient_name", "")}
        raise HTTPException(status_code=409, detail="Bu kod zaten başka bir hesaba bağlı.")

    found_session["patient_id"] = current_user["user_id"]
    found_session["claim_code"] = None   # kodu tüket — bir kez kullanılabilir
    db_save_session(found_id, found_session)
    print(f"[Claim] {code} -> session {found_id[:8]}... -> user {current_user['user_id']}")
    return {"status": "claimed", "session_id": found_id,
            "patient_name": found_session.get("patient_name", "")}


@app.post("/api/session/answer", response_model=SessionResponse)
@limiter.limit("60/minute")
async def submit_answer(req: AnswerRequest, request: Request):
    """Cevabı kaydeder, Gemma 4 ile bağlamsal sonraki soruyu üretir."""
    session = sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı.")
    if session["completed"]:
        raise HTTPException(status_code=400, detail="Mülakat zaten tamamlandı.")

    session["qa_history"][-1]["answer"] = req.answer
    current_step = session["step"]
    total_steps  = session["total_steps"]

    # ── Adaptif soru sayısı güncelle (ilk cevaptan sonra) ──
    # Hastanın ilk cevabı ana şikayeti içerir → gerçek aciliyet burada belli olur
    if current_step == 1 and req.answer:
        lang_s = session.get("language", "tr")
        age_s = session.get("age", 30)
        new_steps = _adaptive_steps(req.answer, age_s, lang_s)
        if new_steps != total_steps:
            session["total_steps"] = new_steps
            total_steps = new_steps
            print(f"[Adaptive] '{req.answer[:40]}...' → {new_steps} soru (yaş:{age_s})")

    if current_step >= total_steps:
        session["completed"] = True
        db_save_session(req.session_id, session)
        await notify_queue_update()
        return SessionResponse(session_id=req.session_id, question="__COMPLETED__", step=current_step, total_steps=total_steps)

    lang = session["language"]
    history_text = "\n".join(
        f"S{i+1}: {qa['question']}\nC{i+1}: {qa['answer']}"
        for i, qa in enumerate(session["qa_history"])
        if qa.get("answer")
    )

    # ── Pediatrik protokol: 2. sorudan itibaren klinik çerçeve eklenir ─────
    pediatric_hint = ""
    if _is_pediatric_case(session) and current_step == 1:
        if lang == "tr":
            pediatric_hint = (
                "\n⚠️ PEDİATRİK VAKA: Çocuk hastası. Bir sonraki soru MUTLAKA ateş derecesini "
                "ve süresini sormalı. Komplikasyon soruları (havale, ense sertliği) ancak "
                "ateş ciddiyeti belirlendikten SONRA sorulur.\n"
            )
        else:
            pediatric_hint = (
                "\n⚠️ PEDIATRIC CASE: Child patient. The NEXT question MUST ask for the specific "
                "temperature reading and duration first. Complication questions (seizure, neck stiffness) "
                "come only AFTER fever severity is established.\n"
            )

    if lang == "tr":
        next_prompt = (
            f"Hasta: {session['patient_name']}, {session['age']} yaşında, {session['gender']}.\n"
            f"{pediatric_hint}"
            f"Mülakat geçmişi:\n{history_text}\n\n"
            f"Yukarıdaki cevaplara dayanarak tanıyı netleştirecek SONRAKI en kritik soruyu sor. "
            f"Acil belirti varsa o yönde derinleş. Soru {current_step+1}/{total_steps}."
        )
    else:
        next_prompt = (
            f"Patient: {session['patient_name']}, {session['age']}y, {session['gender']}.\n"
            f"{pediatric_hint}"
            f"Interview so far:\n{history_text}\n\n"
            f"Based on above answers, ask the NEXT most critical question to clarify the diagnosis. "
            f"If emergency signs present, explore further. Q{current_step+1}/{total_steps}."
        )

    rag_query = req.answer + " " + history_text[-300:]
    next_question = await ask_gemma_rag(next_prompt, system=get_system_prompt(lang),
                                         rag_query=rag_query)
    session["step"] += 1
    session["qa_history"].append({"question": next_question, "answer": None})

    db_save_session(req.session_id, session)

    return SessionResponse(session_id=req.session_id, question=next_question, step=session["step"], total_steps=total_steps)


@app.get("/api/session/{session_id}/summary", response_model=ClinicalSummaryResponse)
async def get_clinical_summary(session_id: str):
    """Tamamlanan mülakattan Gemma 4 ile klinik özet ve triaj üretir."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı.")
    if not session["completed"]:
        raise HTTPException(status_code=400, detail="Mülakat henüz tamamlanmadı.")

    if session_id in summaries:
        return ClinicalSummaryResponse(**summaries[session_id])

    _t_start = _time.time()

    lang = session["language"]
    history_text = "\n".join(
        f"Q{i+1}: {qa['question']}\nA: {qa.get('answer', 'Yanıt yok')}"
        for i, qa in enumerate(session["qa_history"])
    )

    # Vital bulgular varsa triaj prompt'una ekle
    vitals_dict = session.get("vitals") or {}
    vitals_ctx = ""
    if vitals_dict:
        vitals_ctx = "\nVital bulgular: " + ", ".join(f"{k}: {v}" for k, v in vitals_dict.items())

    # Görüntü analizi varsa ekle
    image_analyses = session.get("image_analyses", [])
    image_ctx = ""
    if image_analyses:
        last = image_analyses[-1]
        image_ctx = f"\nGörüntü analizi (Gemma 4 Vision): {last['analysis'][:400]}"

    # Hasta profil bağlamı (kronik hastalık, ilaç, alerji)
    profile_ctx = session.get("patient_profile_ctx", "")
    profile_section = f"\nHASTA PROFİLİ: {profile_ctx}" if profile_ctx else ""

    triage_prompt = (
        f"HASTA: {session['patient_name']}, {session['age']} yaş, {session['gender']}{vitals_ctx}{profile_section}{image_ctx}\n\n"
        f"5 TURLU MÜLAKAT:\n{history_text}\n\n"
        f"Bu hastayı triaj et. Sadece JSON döndür."
    ) if lang == "tr" else (
        f"PATIENT: {session['patient_name']}, {session['age']}y, {session['gender']}{vitals_ctx}{profile_section}{image_ctx}\n\n"
        f"5-TURN INTERVIEW:\n{history_text}\n\n"
        f"Triage this patient. Return ONLY JSON."
    )

    raw = await ask_gemma_rag(
        triage_prompt,
        system=get_triage_system(lang),
        rag_query=session.get("chief_complaint", "") or session.get("answers", [""])[0][:200],
        rag_mode="triage",
        timeout=200.0,
    )

    _t_llm = _time.time()
    _llm_latency = round(_t_llm - _t_start, 2)

    # Robust JSON parse
    cleaned = raw.strip()
    if "```" in cleaned:
        parts = cleaned.split("```")
        for part in parts:
            if part.startswith("json"):
                cleaned = part[4:].strip(); break
            elif "{" in part:
                cleaned = part.strip(); break
    try:
        start = cleaned.find("{")
        end   = cleaned.rfind("}") + 1
        triage_data = json.loads(cleaned[start:end])
    except Exception:
        triage_data = {
            "triage_level": "YELLOW", "confidence_score": 70,
            "chief_complaint": "Değerlendirme tamamlandı",
            "symptoms_summary": raw[:300],
            "possible_conditions": ["Doktor değerlendirmesi gerekli"],
            "recommended_action": "Doktor muayenesi önerilir",
            "clinical_notes": raw[:400], "urgency_flags": [],
        }

    # ── Safety Guardrail Layer (deterministic override) ──────────────────
    qa_history = session.get("qa_history", [])
    triage_data, guardrail_triggered = apply_guardrails(
        triage_data, qa_history, lang=lang, vitals=vitals_dict or None
    )

    level = triage_data.get("triage_level", "YELLOW").upper()
    if level not in TRIAGE_COLOR:
        level = "YELLOW"

    # ── Clinical Completeness Score ─────────────────────────────────────
    completeness = compute_clinical_completeness(qa_history, lang=lang, vitals=vitals_dict or None)

    # ── Evidence Map (patient quotes → findings) ────────────────────────
    # Prefer LLM-generated evidence_map, fall back to rule-based
    llm_evidence_map = triage_data.get("evidence_map", [])
    rule_evidence_map = build_evidence_map(qa_history, lang=lang)
    evidence_map = llm_evidence_map if len(llm_evidence_map) >= 2 else rule_evidence_map

    # ── AI Execution Log ─────────────────────────────────────────────────
    # Fetch RAG stats
    rag_chunks = 0
    try:
        if RAG_ENABLED:
            import rag as _rag
            rag_chunks = _rag.get_db_stats().get("total_chunks", 0)
    except Exception:
        pass

    ai_execution_log = {
        "model": GEMMA_MODEL,
        "runtime": "Ollama (local)",
        "external_api": False,
        "patient_data_egress": False,
        "rag_enabled": RAG_ENABLED,
        "rag_backend": "ChromaDB (local)",
        "rag_chunks": rag_chunks,
        "embedding_model": "sentence-transformers/multilingual-MiniLM (local)",
        "inference_latency_s": _llm_latency,
        "safety_guardrail": triage_data.get("safety_guardrail_triggered", False),
        "guardrails_fired": len(guardrail_triggered),
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }

    flags = [f for f in triage_data.get("urgency_flags", [])
             if f and len(f) > 3 and "boş" not in f.lower() and "empty" not in f.lower()]

    # Alerji bayraklarını urgency flags'e ekle
    allergy_flags = session.get("allergy_flags", [])
    for alg in allergy_flags:
        flag_msg = f"⚠️ Alerji geçmişi: {alg}" if session.get("language") == "tr" else f"⚠️ Known allergy: {alg}"
        if flag_msg not in flags:
            flags.insert(0, flag_msg)

    # Son görüntü analiz bulgusunu ekle
    image_findings = None
    if image_analyses:
        image_findings = image_analyses[-1].get("analysis", "")[:500]

    # ── Enrich RAG guideline sources with relevance metadata ─────────────
    raw_sources = triage_data.get("guideline_sources", [])[:4]
    enriched_sources = []
    try:
        if RAG_ENABLED:
            import rag as _rag
            _complaint = (session.get("chief_complaint", "")
                          or (qa_history[0].get("answer", "") if qa_history else ""))[:200]
            hits = _rag.retrieve(_complaint, n_results=4)
            for hit in hits[:4]:
                meta = hit.get("metadata", {})
                enriched_sources.append({
                    "source": meta.get("source", hit.get("id", "Unknown")),
                    "chunk_id": hit.get("id", ""),
                    "relevance_score": round(hit.get("relevance", 0), 3),
                    "excerpt": hit.get("text", "")[:200],
                })
        if not enriched_sources:
            enriched_sources = [{"source": s, "chunk_id": "", "relevance_score": None, "excerpt": ""}
                                 for s in raw_sources]
    except Exception:
        enriched_sources = [{"source": s, "chunk_id": "", "relevance_score": None, "excerpt": ""}
                             for s in raw_sources]

    result = ClinicalSummaryResponse(
        session_id=session_id,
        patient_name=session["patient_name"],
        age=session["age"],
        gender=session["gender"],
        triage_level=level,
        triage_color=TRIAGE_COLOR[level],
        confidence_score=min(100, max(0, int(triage_data.get("confidence_score", 75)))),
        chief_complaint=triage_data.get("chief_complaint", ""),
        symptoms_summary=triage_data.get("symptoms_summary", ""),
        possible_conditions=triage_data.get("possible_conditions", [])[:5],
        urgency_flags=flags,
        recommended_action=triage_data.get("recommended_action", ""),
        clinical_notes=triage_data.get("clinical_notes", ""),
        vitals=vitals_dict or None,
        image_findings=image_findings,
        generated_at=datetime.utcnow().isoformat() + "Z",
        # Trust Layer
        evidence=[e for e in triage_data.get("evidence", []) if e and len(e) > 3][:5],
        guideline_sources=[s["source"] for s in enriched_sources],
        doctor_review_required=True,
        unsafe_to_self_manage=(level == "RED"),
        # Clinical Completeness
        clinical_completeness_score=completeness["clinical_completeness_score"],
        missing_information=completeness["missing_information"],
        recommended_next_questions=completeness["recommended_next_questions"],
        # Evidence Map
        evidence_map=evidence_map,
        # Safety Guardrail
        safety_guardrail_triggered=triage_data.get("safety_guardrail_triggered", False),
        guardrail_rules_fired=triage_data.get("guardrail_rules_fired", []),
        # AI Execution Log
        ai_execution_log=ai_execution_log,
    )

    result_dict = result.model_dump()
    # Store enriched sources separately for FHIR / clinical review
    result_dict["enriched_guideline_sources"] = enriched_sources

    summaries[session_id] = result_dict
    db_save_summary(session_id, result_dict)
    await notify_queue_update()
    return result


@app.get("/api/session/{session_id}/stream-summary")
async def stream_summary(session_id: str):
    """Klinik özeti SSE ile token token akıtır."""
    session = sessions.get(session_id)
    if not session or not session["completed"]:
        raise HTTPException(status_code=400, detail="Geçersiz oturum.")
    lang = session["language"]
    history_text = "\n".join(
        f"Q{i+1}: {qa['question']}\nA: {qa.get('answer','')}"
        for i, qa in enumerate(session["qa_history"])
    )
    vitals_dict = session.get("vitals") or {}
    vitals_ctx = ""
    if vitals_dict:
        vitals_ctx = "\nVitals: " + ", ".join(f"{k}: {v}" for k, v in vitals_dict.items())

    prompt = (
        f"Hasta: {session['patient_name']}, {session['age']} yaş, {session['gender']}.{vitals_ctx}\n"
        f"Mülakat:\n{history_text}\n\nDoktor için kısa klinik özet yaz (3-4 cümle). Triaj seviyesini ve acil uyarıları vurgula."
    ) if lang == "tr" else (
        f"Patient: {session['patient_name']}, {session['age']}y, {session['gender']}.{vitals_ctx}\n"
        f"Interview:\n{history_text}\n\nWrite a brief clinical summary for the doctor (3-4 sentences). Highlight triage level and urgent findings."
    )
    return StreamingResponse(
        stream_gemma(prompt, get_system_prompt(lang)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/session/image-analyze")
async def image_analyze(req: ImageAnalyzeRequest):
    """Gemma 4 Multimodal — Yara, cilt döküntüsü, EKG, röntgen görüntüsü analizi."""
    session = sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı.")

    lang = session.get("language", "tr")
    patient_ctx = f"{session['patient_name']}, {session['age']} yaş, {session['gender']}"
    vitals_dict = session.get("vitals") or {}
    vitals_ctx = ""
    if vitals_dict:
        vitals_ctx = "\nVital bulgular: " + ", ".join(f"{k}: {v}" for k, v in vitals_dict.items())

    context_label = req.context or ("tıbbi görüntü" if lang == "tr" else "medical image")

    if lang == "tr":
        prompt = (
            f"Hasta: {patient_ctx}{vitals_ctx}\n"
            f"Görüntü türü: {context_label}\n\n"
            f"Bu görüntüyü klinik olarak değerlendir. Gördüğün bulguları, olası tanıları ve acil durum varsa belirt."
        )
    else:
        prompt = (
            f"Patient: {patient_ctx}{vitals_ctx}\n"
            f"Image type: {context_label}\n\n"
            f"Clinically evaluate this image. Describe findings, possible diagnoses, and any emergency indicators."
        )

    system = VISION_SYSTEM_TR if lang == "tr" else VISION_SYSTEM_EN
    analysis = await ask_gemma_vision(prompt, req.image_base64, system=system)

    # Analizi oturuma kaydet
    if "image_analyses" not in session:
        session["image_analyses"] = []
    session["image_analyses"].append({
        "analysis": analysis,
        "context": context_label,
        "timestamp": datetime.utcnow().isoformat(),
    })
    db_save_session(req.session_id, session)

    return {
        "analysis": analysis,
        "session_id": req.session_id,
        "context": context_label,
        "image_count": len(session["image_analyses"]),
    }


@app.get("/api/patients/queue")
async def get_patient_queue(current_user: Optional[dict] = Depends(get_current_user)):
    """Triaj önceliğine göre tam veriyle hasta kuyruğunu döndürür."""
    priority = {"RED": 0, "YELLOW": 1, "GREEN": 2, "PENDING": 3}
    patients = []
    for sid, s in sessions.items():
        if s["completed"] and not s.get("is_seen"):  # Görüldü işaretliler kuyruğa dahil değil
            p = {
                "session_id": sid,
                "patient_name": s["patient_name"],
                "age": s["age"],
                "gender": s["gender"],
                "created_at": s.get("created_at", ""),
                "vitals": s.get("vitals"),
                "triage_level": "PENDING",
                "triage_color": "#8c9499",
                "confidence_score": 0,
                "chief_complaint": "Özet bekleniyor...",
                "urgency_flags": [],
                "recommended_action": "",
                "symptoms_summary": "",
                "possible_conditions": [],
                "clinical_notes": "",
                "image_findings": None,
                "allergy_flags": s.get("allergy_flags", []),
                "generated_at": "",
            }
            if sid in summaries:
                p.update(summaries[sid])
            patients.append(p)

    patients.sort(key=lambda x: priority.get(x.get("triage_level", "PENDING"), 3))
    return {
        "total": len(patients),
        "patients": patients,
        "stats": {
            "red":     sum(1 for p in patients if p.get("triage_level") == "RED"),
            "yellow":  sum(1 for p in patients if p.get("triage_level") == "YELLOW"),
            "green":   sum(1 for p in patients if p.get("triage_level") == "GREEN"),
            "pending": sum(1 for p in patients if p.get("triage_level") == "PENDING"),
        },
    }


@app.get("/api/patients/stream")
async def stream_patient_queue():
    """Gerçek zamanlı hasta kuyruğu — SSE (Server-Sent Events)."""
    q: asyncio.Queue = asyncio.Queue()
    _queue_subscribers.append(q)

    async def event_generator():
        try:
            # İlk bağlantıda anlık verileri gönder
            queue_data = await get_patient_queue()
            yield f"data: {json.dumps({'type': 'connected', 'data': queue_data})}\n\n"

            while True:
                try:
                    await asyncio.wait_for(q.get(), timeout=25.0)
                    # Kuyruk güncellendi — anlık veri gönder
                    queue_data = await get_patient_queue()
                    yield f"data: {json.dumps({'type': 'update', 'data': queue_data})}\n\n"
                except asyncio.TimeoutError:
                    # 25sn'de bir heartbeat — bağlantıyı canlı tut
                    yield f"data: {json.dumps({'type': 'heartbeat', 'ts': datetime.utcnow().isoformat()})}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            try:
                _queue_subscribers.remove(q)
            except ValueError:
                pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str, current_user: dict = Depends(require_doctor)):
    """Oturumu siler (HIPAA uyumu için). Sadece doktor/admin yapabilir."""
    if session_id in sessions:
        del sessions[session_id]
        summaries.pop(session_id, None)
        db_delete_session(session_id)
        await notify_queue_update()
        return {"message": "Oturum silindi."}
    raise HTTPException(status_code=404, detail="Oturum bulunamadı.")


# ─────────────────────────────────────────────
#  Sprint 2 — Hasta Geçmişi
# ─────────────────────────────────────────────

@app.get("/api/patient/history")
async def get_patient_history(current_user: dict = Depends(require_auth)):
    """Mevcut hastanın tüm tamamlanmış oturumlarını ve özetlerini döndürür."""
    patient_id = current_user["user_id"]
    history = []
    for sid, s in sessions.items():
        if s.get("patient_id") == patient_id and s.get("completed"):
            entry = {
                "session_id": sid,
                "created_at": s.get("created_at", ""),
                "patient_name": s.get("patient_name"),
                "age": s.get("age"),
                "gender": s.get("gender"),
                "vitals": s.get("vitals"),
                "triage_level": "PENDING",
                "triage_color": "#8c9499",
                "chief_complaint": "Özet bekleniyor...",
                "confidence_score": 0,
            }
            if sid in summaries:
                entry.update({
                    "triage_level": summaries[sid].get("triage_level", "PENDING"),
                    "triage_color": summaries[sid].get("triage_color", "#8c9499"),
                    "chief_complaint": summaries[sid].get("chief_complaint", ""),
                    "confidence_score": summaries[sid].get("confidence_score", 0),
                    "symptoms_summary": summaries[sid].get("symptoms_summary", ""),
                    "recommended_action": summaries[sid].get("recommended_action", ""),
                    "generated_at": summaries[sid].get("generated_at", ""),
                })
            history.append(entry)
    history.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"history": history[:20], "total": len(history)}


# ─────────────────────────────────────────────
#  Sprint 3 — Doktor İş Akışı
# ─────────────────────────────────────────────

@app.post("/api/session/{session_id}/note")
async def add_doctor_note(session_id: str, body: dict, current_user: dict = Depends(require_doctor)):
    """Doktor notu ekler / günceller."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı.")
    note_text = body.get("note", "").strip()
    if not note_text:
        raise HTTPException(status_code=400, detail="Not metni boş olamaz.")
    
    note = {
        "text": note_text,
        "doctor_id": current_user["user_id"],
        "doctor_name": current_user["name"],
        "timestamp": datetime.utcnow().isoformat(),
    }
    if "doctor_notes" not in session:
        session["doctor_notes"] = []
    session["doctor_notes"].append(note)
    db_save_session(session_id, session)
    
    # Özet varsa oraya da kaydet
    if session_id in summaries:
        summaries[session_id]["doctor_notes"] = session["doctor_notes"]
        db_save_summary(session_id, summaries[session_id])
    
    await notify_queue_update()
    return {"status": "ok", "note": note, "total_notes": len(session["doctor_notes"])}


@app.put("/api/session/{session_id}/triage")
async def override_triage(session_id: str, body: dict, current_user: dict = Depends(require_doctor)):
    """Doktor triaj seviyesini değiştirir — Human-in-the-loop audit trail kaydeder."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı.")
    new_level = body.get("triage_level", "").upper()
    if new_level not in ("RED", "YELLOW", "GREEN"):
        raise HTTPException(status_code=400, detail="Geçersiz triaj seviyesi. RED / YELLOW / GREEN olmalı.")

    ai_triage = summaries.get(session_id, {}).get("triage_level", "PENDING")
    override_entry = {
        "level": new_level,
        "ai_triage": ai_triage,
        "original_level": ai_triage,
        "override_reason": body.get("override_reason", ""),
        "doctor_id": current_user["user_id"],
        "doctor_name": current_user["name"],
        "timestamp": datetime.utcnow().isoformat(),
    }

    session["triage_override"] = override_entry
    db_save_session(session_id, session)

    if session_id in summaries:
        summaries[session_id]["triage_level"] = new_level
        summaries[session_id]["triage_color"] = TRIAGE_COLOR[new_level]
        summaries[session_id]["triage_override"] = override_entry
        summaries[session_id]["doctor_final_triage"] = new_level
        db_save_summary(session_id, summaries[session_id])

    # Audit
    audit("triage_override", user_id=current_user["user_id"], user_role=current_user["role"],
          resource=session_id, details=f"AI:{ai_triage} → Doctor:{new_level} reason:{body.get('override_reason','')}")

    await notify_queue_update()
    return {
        "status": "ok",
        "new_level": new_level,
        "ai_triage": ai_triage,
        "override": override_entry,
        "human_in_the_loop": True,
    }


@app.put("/api/session/{session_id}/seen")
async def mark_as_seen(session_id: str, current_user: dict = Depends(require_doctor)):
    """Hasta 'Görüldü' olarak işaretler — kuyruktan çıkarır."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı.")
    session["seen_by"] = {
        "doctor_id": current_user["user_id"],
        "doctor_name": current_user["name"],
        "timestamp": datetime.utcnow().isoformat(),
    }
    session["is_seen"] = True
    db_save_session(session_id, session)
    if session_id in summaries:
        summaries[session_id]["is_seen"] = True
        db_save_summary(session_id, summaries[session_id])
    await notify_queue_update()
    return {"status": "ok", "seen_by": session["seen_by"]}


@app.delete("/api/session/{session_id}/seen")
async def unmark_as_seen(session_id: str, current_user: dict = Depends(require_doctor)):
    """'Görüldü' işaretini kaldırır — hastayı kuyruğa geri alır."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı.")
    session["is_seen"] = False
    session.pop("seen_by", None)
    db_save_session(session_id, session)
    if session_id in summaries:
        summaries[session_id]["is_seen"] = False
        db_save_summary(session_id, summaries[session_id])
    await notify_queue_update()
    return {"status": "ok", "message": "Hasta kuyruğa geri alındı."}


@app.get("/api/patients/seen")
async def get_seen_patients(
    limit: int = 50,
    current_user: dict = Depends(require_doctor)
):
    """Görüldü işaretlenmiş hastaların arşivini döndürür (en yeniden eskiye)."""
    seen_list = []
    for sid, s in sessions.items():
        if not s.get("is_seen"):
            continue
        summary = summaries.get(sid, {})
        seen_by = s.get("seen_by", {})
        seen_list.append({
            "session_id": sid,
            "patient_name": s["patient_name"],
            "age": s["age"],
            "gender": s["gender"],
            "created_at": s.get("created_at", ""),
            "seen_at": seen_by.get("timestamp", ""),
            "seen_by_name": seen_by.get("doctor_name", ""),
            "triage_level": summary.get("triage_level", "PENDING"),
            "triage_color": summary.get("triage_color", "#8c9499"),
            "confidence_score": summary.get("confidence_score", 0),
            "chief_complaint": summary.get("chief_complaint", "—"),
            "urgency_flags": summary.get("urgency_flags", []),
            "possible_conditions": summary.get("possible_conditions", []),
        })
    # En yeni "görüldü" önce
    seen_list.sort(key=lambda x: x["seen_at"], reverse=True)
    return {"patients": seen_list[:limit], "total": len(seen_list)}


@app.get("/api/session/{session_id}/detail")
async def get_session_detail(session_id: str, current_user: dict = Depends(require_doctor)):
    """Oturum detayını döndürür (görüldü olanlar dahil). Doktor tekrar erişimine izin verir."""
    # Önce RAM'deki sessions sözlüğüne bak
    session = sessions.get(session_id)
    if not session:
        # RAM'de yoksa DB'den yükle
        try:
            with get_cursor() as cur:
                cur.execute("SELECT data FROM sessions WHERE session_id = %s", (session_id,))
                row = cur.fetchone()
            if row:
                session = row["data"] if isinstance(row["data"], dict) else json.loads(row["data"])
            else:
                raise HTTPException(status_code=404, detail="Oturum bulunamadı.")
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=404, detail="Oturum bulunamadı.")

    summary = summaries.get(session_id)
    if not summary:
        try:
            with get_cursor() as cur:
                cur.execute("SELECT data FROM summaries WHERE session_id = %s", (session_id,))
                row = cur.fetchone()
            if row:
                summary = row["data"] if isinstance(row["data"], dict) else json.loads(row["data"])
        except Exception:
            summary = None

    return {
        "session_id": session_id,
        "session": session,
        "summary": summary,
    }


@app.get("/api/session/{session_id}/icd10")
async def suggest_icd10(session_id: str, current_user: dict = Depends(require_doctor)):
    """Gemma 4 ile otomatik ICD-10 kod önerisi üretir."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı.")
    
    summary = summaries.get(session_id, {})
    complaint = summary.get("chief_complaint", "")
    conditions = summary.get("possible_conditions", [])
    
    if not complaint and not conditions:
        raise HTTPException(status_code=400, detail="Özet henüz oluşturulmamış.")
    
    prompt = (
        f"Klinik bulgular:\n"
        f"Ana şikayet: {complaint}\n"
        f"Olası tanılar: {', '.join(conditions)}\n\n"
        f"Bu bulgular için en uygun ICD-10 kodlarını (maksimum 3 adet) öner. "
        f"Format: [{{'code': 'X00.0', 'description': 'Tanı açıklaması', 'confidence': 'yüksek/orta/düşük'}}] "
        f"sadece JSON döndür."
    )
    system = "Sen ICD-10 kodlama uzmanısın. Verilen klinik tanılara göre doğru ICD-10 kodlarını JSON formatında öner. Sadece JSON döndür."
    
    raw = await ask_gemma(prompt, system)
    try:
        start = raw.find("[")
        end = raw.rfind("}") + 1
        codes = json.loads(raw[start:end])
    except Exception:
        codes = [{"code": "Z03.89", "description": "Diğer şüpheli hastalıklar için gözlem", "confidence": "düşük"}]
    
    return {"session_id": session_id, "icd10_suggestions": codes, "generated_by": "gemma4"}


# ─────────────────────────────────────────────
#  Sprint 8 — Analitik
# ─────────────────────────────────────────────

@app.get("/api/analytics")
async def get_analytics(current_user: dict = Depends(require_doctor)):
    """Temel triaj istatistikleri ve analitik verileri döndürür."""
    all_summaries = list(summaries.values())
    all_sessions_list = list(sessions.values())
    
    total = len([s for s in all_sessions_list if s.get("completed")])
    red = sum(1 for s in all_summaries if s.get("triage_level") == "RED")
    yellow = sum(1 for s in all_summaries if s.get("triage_level") == "YELLOW")
    green = sum(1 for s in all_summaries if s.get("triage_level") == "GREEN")
    seen = sum(1 for s in all_sessions_list if s.get("is_seen"))
    
    # Ortalama güven skoru
    scores = [s.get("confidence_score", 0) for s in all_summaries if s.get("confidence_score")]
    avg_confidence = round(sum(scores) / len(scores), 1) if scores else 0
    
    # Cinsiyet dağılımı
    genders = {}
    for s in all_sessions_list:
        g = s.get("gender", "Bilinmiyor")
        genders[g] = genders.get(g, 0) + 1
    
    # Yaş grupları
    age_groups = {"0-17": 0, "18-35": 0, "36-60": 0, "60+": 0}
    for s in all_sessions_list:
        age = s.get("age", 0)
        if age <= 17: age_groups["0-17"] += 1
        elif age <= 35: age_groups["18-35"] += 1
        elif age <= 60: age_groups["36-60"] += 1
        else: age_groups["60+"] += 1
    
    # Son 7 gün günlük triaj sayıları (basit)
    from datetime import timedelta
    daily = {}
    today = datetime.utcnow().date()
    for s in all_sessions_list:
        ct = s.get("created_at", "")
        if ct:
            try:
                d = datetime.fromisoformat(ct).date()
                delta = (today - d).days
                if 0 <= delta <= 6:
                    key = d.isoformat()
                    daily[key] = daily.get(key, 0) + 1
            except Exception:
                pass
    
    # En sık semptomlar (urgency flags)
    flag_count = {}
    for s in all_summaries:
        for flag in s.get("urgency_flags", []):
            flag_count[flag] = flag_count.get(flag, 0) + 1
    top_flags = sorted(flag_count.items(), key=lambda x: -x[1])[:5]
    
    return {
        "summary": {
            "total_completed": total,
            "red": red, "yellow": yellow, "green": green,
            "seen": seen, "pending": total - seen,
            "avg_confidence": avg_confidence,
        },
        "distributions": {
            "gender": genders,
            "age_groups": age_groups,
            "triage": {"RED": red, "YELLOW": yellow, "GREEN": green},
        },
        "daily_activity": daily,
        "top_urgency_flags": [{"flag": f, "count": c} for f, c in top_flags],
        "generated_at": datetime.utcnow().isoformat(),
    }


# ─────────────────────────────────────────────
#  Sprint 6 — FHIR R4 Export
# ─────────────────────────────────────────────

@app.get("/api/session/{session_id}/fhir")
async def fhir_export(session_id: str, current_user: dict = Depends(require_doctor)):
    """FHIR R4 ClinicalImpression + Patient resource döndürür."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı.")
    summary = summaries.get(session_id, {})
    
    fhir_bundle = {
        "resourceType": "Bundle",
        "id": session_id,
        "type": "collection",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": session.get("patient_id") or session_id,
                    "name": [{"use": "official", "text": session["patient_name"]}],
                    "gender": "male" if session["gender"] in ("Erkek", "Male") else "female",
                    "birthDate": str(datetime.utcnow().year - session["age"]),
                }
            },
            {
                "resource": {
                    "resourceType": "ClinicalImpression",
                    "id": f"ci-{session_id}",
                    "status": "completed",
                    "subject": {"reference": f"Patient/{session.get('patient_id') or session_id}"},
                    "date": session.get("created_at", datetime.utcnow().isoformat()),
                    "description": summary.get("chief_complaint", ""),
                    "summary": summary.get("clinical_notes", ""),
                    "finding": [
                        {"itemCodeableConcept": {"text": cond}}
                        for cond in summary.get("possible_conditions", [])
                    ],
                    "note": [{"text": summary.get("symptoms_summary", "")}],
                    "extension": [
                        {
                            "url": "https://anamnezai.tr/fhir/StructureDefinition/triage-level",
                            "valueString": summary.get("triage_level", "PENDING")
                        },
                        {
                            "url": "https://anamnezai.tr/fhir/StructureDefinition/ai-confidence",
                            "valueInteger": summary.get("confidence_score", 0)
                        },
                        {
                            "url": "https://anamnezai.tr/fhir/StructureDefinition/recommended-action",
                            "valueString": summary.get("recommended_action", "")
                        },
                    ],
                }
            }
        ]
    }

    # Vital signs — FHIR Observation
    vitals = session.get("vitals") or {}
    if vitals:
        obs_components = []
        if vitals.get("blood_pressure"):
            obs_components.append({
                "code": {"coding": [{"system": "http://loinc.org", "code": "55284-4", "display": "Blood pressure"}]},
                "valueString": vitals["blood_pressure"]
            })
        if vitals.get("pulse"):
            obs_components.append({
                "code": {"coding": [{"system": "http://loinc.org", "code": "8867-4", "display": "Heart rate"}]},
                "valueQuantity": {"value": vitals["pulse"], "unit": "/min"}
            })
        if vitals.get("temperature"):
            obs_components.append({
                "code": {"coding": [{"system": "http://loinc.org", "code": "8310-5", "display": "Body temperature"}]},
                "valueQuantity": {"value": vitals["temperature"], "unit": "Cel"}
            })
        if vitals.get("spo2"):
            obs_components.append({
                "code": {"coding": [{"system": "http://loinc.org", "code": "2708-6", "display": "Oxygen saturation"}]},
                "valueQuantity": {"value": vitals["spo2"], "unit": "%"}
            })
        fhir_bundle["entry"].append({
            "resource": {
                "resourceType": "Observation",
                "id": f"obs-{session_id}",
                "status": "final",
                "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "vital-signs"}]}],
                "subject": {"reference": f"Patient/{session.get('patient_id') or session_id}"},
                "effectiveDateTime": session.get("created_at", ""),
                "component": obs_components,
            }
        })

    audit("fhir_export", user_id=current_user["user_id"], user_role=current_user["role"],
          resource=session_id)
    return fhir_bundle


# ─────────────────────────────────────────────
#  Sprint 9 — Güvenlik & KVKK/GDPR
# ─────────────────────────────────────────────

@app.get("/api/audit-log")
async def get_audit_log(limit: int = 50, current_user: dict = Depends(require_admin)):
    """Audit log listesi — sadece admin."""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM audit_log ORDER BY created_at DESC LIMIT %s", (limit,))
        rows = cur.fetchall()
    return {"logs": [dict(r) for r in rows], "total": len(rows)}


@app.get("/api/admin/users")
async def list_all_users(current_user: dict = Depends(require_admin)):
    """Tüm kullanıcıları listeler — sadece admin."""
    with get_cursor() as cur:
        cur.execute(
            "SELECT user_id, name, email, role, specialty, created_at, is_active FROM users ORDER BY created_at DESC"
        )
        rows = cur.fetchall()
    return {"users": [dict(r) for r in rows], "total": len(rows)}


@app.put("/api/admin/users/{user_id}/role")
async def change_user_role(user_id: str, body: dict, current_user: dict = Depends(require_admin)):
    """Kullanıcı rolünü değiştirir — sadece admin."""
    new_role = body.get("role")
    valid_roles = ["patient", "doctor", "personnel", "admin"]
    if new_role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Geçersiz rol. Geçerli roller: {valid_roles}")
    if user_id == current_user["user_id"]:
        raise HTTPException(status_code=400, detail="Kendi rolünüzü değiştiremezsiniz.")
    with get_cursor() as cur:
        cur.execute("UPDATE users SET role = %s WHERE user_id = %s", (new_role, user_id))
        affected = cur.rowcount
    if affected == 0:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")
    audit("role_change", user_id=current_user["user_id"], user_role=current_user["role"],
          details=f"user {user_id} role → {new_role}")
    return {"status": "ok", "user_id": user_id, "new_role": new_role}


@app.put("/api/admin/users/{user_id}/active")
async def toggle_user_active(user_id: str, body: dict, current_user: dict = Depends(require_admin)):
    """Kullanıcıyı aktif/pasif yapar — sadece admin."""
    if user_id == current_user["user_id"]:
        raise HTTPException(status_code=400, detail="Kendi hesabınızı devre dışı bırakamazsınız.")
    is_active = 1 if body.get("active", True) else 0
    with get_cursor() as cur:
        cur.execute("UPDATE users SET is_active = %s WHERE user_id = %s", (is_active, user_id))
    action = "activate" if is_active else "deactivate"
    audit(action, user_id=current_user["user_id"], user_role=current_user["role"],
          details=f"user {user_id}")
    return {"status": "ok", "user_id": user_id, "is_active": bool(is_active)}


@app.get("/api/admin/stats")
async def admin_stats(current_user: dict = Depends(require_admin)):
    """Sistem istatistikleri — sadece admin."""
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS cnt FROM users WHERE is_active = 1")
        total_users = cur.fetchone()["cnt"]
        cur.execute("SELECT role, COUNT(*) AS cnt FROM users WHERE is_active = 1 GROUP BY role")
        by_role = {r["role"]: r["cnt"] for r in cur.fetchall()}
        cur.execute("SELECT COUNT(*) AS cnt FROM sessions")
        total_sessions_db = cur.fetchone()["cnt"]
    return {
        "total_users": total_users,
        "by_role": by_role,
        "sessions_in_memory": len(sessions),
        "sessions_in_db": total_sessions_db,
        "seen_count": sum(1 for s in sessions.values() if s.get("is_seen")),
        "queue_length": sum(1 for s in sessions.values() if s.get("completed") and not s.get("is_seen")),
        "kiosk_locked": _kiosk_locked,
        "model": GEMMA_MODEL,
        "rag_enabled": RAG_ENABLED,
    }


@app.delete("/api/user/{user_id}/all-data")
async def gdpr_delete_user_data(user_id: str, current_user: dict = Depends(require_auth)):
    """KVKK/GDPR hakkı: kullanıcının tüm verilerini siler. Sadece kendi verisi veya admin."""
    if current_user["user_id"] != user_id and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Sadece kendi verinizi silebilirsiniz.")
    
    deleted_sessions = 0
    to_delete = [sid for sid, s in sessions.items() if s.get("patient_id") == user_id]
    for sid in to_delete:
        del sessions[sid]
        summaries.pop(sid, None)
        db_delete_session(sid)
        deleted_sessions += 1
    
    # Kullanıcı profilini ve hesabını kaldır (is_active = 0)
    with get_cursor() as cur:
        cur.execute("UPDATE users SET is_active = 0 WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM patient_profiles WHERE user_id = %s", (user_id,))
    
    audit("gdpr_delete", user_id=current_user["user_id"], user_role=current_user["role"],
          resource=user_id, details=f"{deleted_sessions} sessions deleted")
    await notify_queue_update()
    return {
        "status": "ok",
        "message": f"Tüm veriler silindi. {deleted_sessions} oturum kaldırıldı.",
        "deleted_sessions": deleted_sessions
    }


# ─────────────────────────────────────────────
#  Sprint 5 — Kiosk Modu
# ─────────────────────────────────────────────

@app.get("/api/kiosk/status")
async def kiosk_status():
    """Kiosk screen system status (anonymous access)."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            online = r.status_code == 200
    except Exception:
        online = False
    
    queue_len = len([s for s in sessions.values() if s.get("completed") and not s.get("is_seen")])
    return {
        "system_online": online,
        "model_ready": _model_ready,
        "is_locked": _kiosk_locked,
        "queue_length": queue_len,
        "estimated_wait_minutes": max(1, queue_len * 3),
        "message_tr": "Sisteme hoş geldiniz. Lütfen bilgilerinizi girin." if online else "Sistem bakımda.",
        "message_en": "Welcome. Please enter your information." if online else "System under maintenance.",
    }


@app.post("/api/kiosk/lock")
async def kiosk_lock(current_user: dict = Depends(require_doctor)):
    """Lock the kiosk — doktor veya admin yapabilir."""
    global _kiosk_locked
    _kiosk_locked = True
    audit("kiosk_lock", user_id=current_user["user_id"], user_role=current_user["role"])
    return {"status": "locked", "message": "Kiosk locked."}


@app.post("/api/kiosk/unlock")
async def kiosk_unlock(current_user: dict = Depends(require_doctor)):
    """Unlock the kiosk — doktor veya admin yapabilir."""
    global _kiosk_locked
    _kiosk_locked = False
    audit("kiosk_unlock", user_id=current_user["user_id"], user_role=current_user["role"])
    return {"status": "unlocked", "message": "Kiosk unlocked."}


# ─────────────────────────────────────────────
#  Sprint 5 — QR Code Session Continuation
# ─────────────────────────────────────────────

@app.get("/api/session/{session_id}/qr")
async def session_qr_code(session_id: str, base_url: str = "http://localhost:8000"):
    """Generate QR code PNG for session continuation (Sprint 5)."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found.")
    if not _qr_available:
        raise HTTPException(status_code=503, detail="qrcode library not installed.")
    
    url = f"{base_url}/?session={session_id}"
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#001f2a", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png", headers={
        "Content-Disposition": f'inline; filename="qr-{session_id[:8]}.png"'
    })


@app.get("/api/session/{session_id}/ticket", response_class=HTMLResponse)
async def print_ticket(session_id: str):
    """Print ticket HTML for kiosk queue slip (Sprint 5)."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    summary = summaries.get(session_id, {})
    triage = summary.get("triage_level", "PENDING")
    color_map = {"RED": "#d32f2f", "YELLOW": "#f57c00", "GREEN": "#388e3c", "PENDING": "#666"}
    triage_color = color_map.get(triage, "#666")
    triage_tr = {"RED": "ACİL", "YELLOW": "İKİNCİL ACİL", "GREEN": "RUTİN", "PENDING": "—"}.get(triage, triage)
    now = datetime.utcnow().strftime("%d.%m.%Y %H:%M")
    short_id = session_id[:8].upper()

    html = f"""<!DOCTYPE html>
<html lang="tr">
<head><meta charset="utf-8"/><title>Sıra Fişi — AnamnezAI</title>
<style>
  body{{font-family:'Courier New',monospace;max-width:320px;margin:0 auto;padding:16px;background:#fff;color:#000}}
  .center{{text-align:center}} .big{{font-size:48px;font-weight:900;color:{triage_color}}}
  .border{{border-top:2px dashed #ccc;margin:12px 0}} hr{{border:none;border-top:1px dashed #ccc;margin:8px 0}}
  @media print{{body{{padding:0}}}}
</style>
</head>
<body>
<div class="center">
  <div style="font-size:18px;font-weight:bold">AnamnezAI</div>
  <div style="font-size:12px;color:#666">AI Destekli Hasta Ön Triajı</div>
  <div class="border"></div>
  <div style="font-size:13px">Sıra No</div>
  <div class="big">{short_id}</div>
  <div class="border"></div>
  <div style="font-size:13px;color:#666">Hasta</div>
  <div style="font-size:16px;font-weight:bold">{session.get('patient_name','—')}</div>
  <div style="font-size:12px">{session.get('age','—')} yaş · {session.get('gender','—')}</div>
  <div class="border"></div>
  <div style="font-size:13px;color:#666">Triaj Önceliği</div>
  <div style="font-size:24px;font-weight:900;color:{triage_color}">{triage_tr}</div>
  <div style="font-size:12px;color:#666;margin-top:4px">{summary.get('chief_complaint','—')}</div>
  <div class="border"></div>
  <div style="font-size:11px;color:#888">{now}</div>
  <div style="font-size:11px;color:#aaa;margin-top:8px">Verileriniz KVKK kapsamında korunmaktadır.</div>
</div>
<script>window.onload=()=>window.print()</script>
</body></html>"""
    return HTMLResponse(content=html)


# ─────────────────────────────────────────────
#  Sprint 8 — Analytics CSV Export
# ─────────────────────────────────────────────

@app.get("/api/analytics/export/csv")
async def export_analytics_csv(current_user: dict = Depends(require_admin)):
    """Export anonymised analytics as CSV (Sprint 8)."""
    rows = []
    for sid, s in sessions.items():
        if not s.get("completed"):
            continue
        summ = summaries.get(sid, {})
        rows.append({
            "session_id": sid[:8],
            "age_group": ("0-17" if s.get("age", 0) <= 17 else
                          "18-35" if s.get("age", 0) <= 35 else
                          "36-60" if s.get("age", 0) <= 60 else "60+"),
            "gender": s.get("gender", ""),
            "triage_level": summ.get("triage_level", ""),
            "confidence_score": summ.get("confidence_score", 0),
            "chief_complaint_category": summ.get("chief_complaint", "")[:40],
            "urgency_flags": "|".join(summ.get("urgency_flags", [])),
            "is_seen": s.get("is_seen", False),
            "created_date": s.get("created_at", "")[:10],
        })

    output = io.StringIO()
    if rows:
        writer = csv.DictWriter(output, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    audit("analytics_csv_export", user_id=current_user["user_id"], user_role=current_user["role"])
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="anamnezai-analytics-{datetime.utcnow().strftime("%Y%m%d")}.csv"'}
    )


# ─────────────────────────────────────────────
#  Sprint 9 — Rate-limited public endpoints
# ─────────────────────────────────────────────

if _rate_limit_available:
    @app.get("/api/session/start/ratelimit-check")
    @limiter.limit("30/minute")
    async def _rate_check(request: Request):
        return {"ok": True}


# ─────────────────────────────────────────────
#  Offline Proof & Trust Endpoints
#  IMPORTANT: Must be defined BEFORE static files mount.
#  app.mount("/", StaticFiles(...)) captures ALL routes — any route
#  defined after the mount will never be reached (returns 404).
# ─────────────────────────────────────────────

@app.get("/api/offline-proof")
async def offline_proof():
    """Ollama prize proof: shows all AI inference runs locally, zero cloud API."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{OLLAMA_BASE_URL}/api/tags")
            models_loaded = [m["name"] for m in r.json().get("models", [])]
            ollama_running = True
    except Exception:
        models_loaded = []
        ollama_running = False
    return {
        "runtime": "ollama",
        "cloud_api_keys_required": False,
        "internet_required_after_setup": False,
        "patient_data_external_transfer": False,
        "privacy_guarantee": "All patient data stays on-device. No cloud API used.",
        "models": {
            "primary": GEMMA_MODEL,
            "vision": MEDGEMMA_MODEL,
            "backend": "FastAPI + PostgreSQL — fully local",
        },
        "ollama_running": ollama_running,
        "models_loaded": models_loaded,
        "kvkk_gdpr_compliant": True,
        "disclaimer": (
            "AnamnezAI is not a diagnostic or treatment system. "
            "It is a privacy-preserving clinical intake assistant that structures "
            "patient history, flags urgency, and prepares a physician-reviewable summary. "
            "All clinical decisions require physician review."
        ),
    }


# ─────────────────────────────────────────────
#  Sprint 21 — Evaluation Dashboard API
# ─────────────────────────────────────────────

@app.get("/api/evaluation")
async def get_evaluation_results(current_user: Optional[dict] = Depends(get_current_user)):
    """Evaluation dashboard — AI quality metrics + live system stats."""
    # Static evaluation results from evaluation/results.md (May 2026 run)
    static_results = {
        "generated": "2026-05-11",
        "model": GEMMA_MODEL,
        "runtime": "Ollama local",
        "gpu": "RTX 8 GB VRAM",
        "rag_chunks": 90,
        "summary": {
            "overall_score_pct": 93.0,
            "cases_tested": 15,
            "passed": 14,
            "failed": 1,
            "triage_accuracy_pct": 100.0,
            "rag_accuracy_pct": 100.0,
            "red_flag_recall_pct": 100.0,
            "json_validity_pct": 100.0,
            "avg_latency_s": "11–39s",
            "local_inference": True,
            "cloud_api_used": False,
        },
        "triage_cases": [
            {"case": "AMI — Acute Cardiac Emergency", "expected": "RED",    "predicted": "RED",    "confidence": 100, "pass": True},
            {"case": "High Fever Child (39.5°C)",      "expected": "YELLOW", "predicted": "YELLOW", "confidence": 90,  "pass": True},
            {"case": "Simple URTI",                    "expected": "GREEN",  "predicted": "GREEN",  "confidence": 95,  "pass": True},
            {"case": "Stroke Suspicion",               "expected": "RED",    "predicted": "RED",    "confidence": 98,  "pass": True},
            {"case": "Abdominal Pain — Appendicitis",  "expected": "YELLOW", "predicted": "YELLOW", "confidence": 90,  "pass": True},
        ],
        "rag_cases": [
            {"query": "Chest pain, radiation to left arm", "expected": "Cardiac_Emergency", "found": "Cardiac_Emergency", "score": 0.821, "pass": True},
            {"query": "Infant 2 months fever 38.5",        "expected": "Pediatric",          "found": "Pediatric_Triage", "score": 0.581, "pass": True},
            {"query": "Sudden severe headache neck stiffness", "expected": "Neurological",   "found": "Neurological_Emerg", "score": 0.789, "pass": True},
            {"query": "Lower back pain, urinary retention",    "expected": "Orthopedic",     "found": "Orthopedic_Triage",  "score": 0.470, "pass": True},
            {"query": "Rash fever petechiae",              "expected": "Dermatology",        "found": "Dermatology_Triage", "score": 0.588, "pass": True},
            {"query": "Ear pain child",                    "expected": "ENT",                "found": "ENT_Emergency",      "score": 0.651, "pass": True},
        ],
    }

    # Live stats
    live_summaries = list(summaries.values())
    guardrail_count = sum(1 for s in live_summaries if s.get("safety_guardrail_triggered"))
    avg_completeness = 0
    if live_summaries:
        scores = [s.get("clinical_completeness_score", 0) for s in live_summaries]
        avg_completeness = round(sum(scores) / len(scores), 1)

    static_results["live_stats"] = {
        "total_sessions_in_db": len(sessions),
        "completed_sessions": sum(1 for s in sessions.values() if s.get("completed")),
        "guardrail_escalations": guardrail_count,
        "avg_clinical_completeness_pct": avg_completeness,
        "triage_distribution": {
            "RED":    sum(1 for s in live_summaries if s.get("triage_level") == "RED"),
            "YELLOW": sum(1 for s in live_summaries if s.get("triage_level") == "YELLOW"),
            "GREEN":  sum(1 for s in live_summaries if s.get("triage_level") == "GREEN"),
        },
    }
    return static_results


# ─────────────────────────────────────────────
#  Sprint 21 — Patient Timeline / Visit Comparison
# ─────────────────────────────────────────────

@app.get("/api/session/{session_id}/timeline")
async def get_patient_timeline(session_id: str, current_user: dict = Depends(require_doctor)):
    """Patient visit timeline — compares current visit to previous ones."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı.")

    patient_name = session.get("patient_name", "")
    current_summary = summaries.get(session_id, {})
    current_level = current_summary.get("triage_level", "PENDING")
    current_complaint = current_summary.get("chief_complaint", "")
    current_date = session.get("created_at", "")[:10]

    # Find previous visits for same patient name
    previous_visits = []
    for sid, s in sessions.items():
        if sid == session_id:
            continue
        if s.get("patient_name", "").lower() == patient_name.lower() and s.get("completed"):
            summ = summaries.get(sid, {})
            previous_visits.append({
                "session_id": sid,
                "date": s.get("created_at", "")[:10],
                "triage_level": summ.get("triage_level", "PENDING"),
                "chief_complaint": summ.get("chief_complaint", ""),
                "symptoms_summary": summ.get("symptoms_summary", ""),
                "urgency_flags": summ.get("urgency_flags", []),
            })

    previous_visits.sort(key=lambda x: x["date"], reverse=True)

    # Detect changes vs most recent previous visit
    changes_detected = []
    if previous_visits:
        prev = previous_visits[0]
        prev_level = prev.get("triage_level", "GREEN")
        level_rank = {"GREEN": 0, "YELLOW": 1, "RED": 2, "PENDING": -1}

        if level_rank.get(current_level, -1) > level_rank.get(prev_level, -1):
            changes_detected.append(f"⬆️ Triaj seviyesi yükseldi: {prev_level} → {current_level}")
        elif level_rank.get(current_level, -1) < level_rank.get(prev_level, -1):
            changes_detected.append(f"⬇️ Triaj seviyesi düştü: {prev_level} → {current_level}")

        # Compare urgency flags
        prev_flags = set(prev.get("urgency_flags", []))
        curr_flags = set(current_summary.get("urgency_flags", []))
        new_flags = curr_flags - prev_flags
        for f in list(new_flags)[:3]:
            changes_detected.append(f"🆕 Yeni acil bulgu: {f}")

    return {
        "session_id": session_id,
        "patient_name": patient_name,
        "current_visit": {
            "date": current_date,
            "triage_level": current_level,
            "chief_complaint": current_complaint,
        },
        "previous_visits": previous_visits[:5],
        "total_previous": len(previous_visits),
        "changes_detected": changes_detected,
        "risk_trend": (
            "increasing" if any("yükseldi" in c or "raised" in c.lower() for c in changes_detected)
            else "stable" if changes_detected
            else "first_visit" if not previous_visits
            else "decreasing"
        ),
    }


# ─────────────────────────────────────────────
#  Sprint 21 — Enriched FHIR Preview
# ─────────────────────────────────────────────

@app.get("/api/session/{session_id}/fhir-preview")
async def fhir_preview(session_id: str, current_user: dict = Depends(require_doctor)):
    """FHIR Bundle summary card — hospital integration preview."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı.")
    summary = summaries.get(session_id, {})
    vitals = session.get("vitals") or {}

    obs_count = 0
    if vitals:
        obs_count = sum(1 for v in vitals.values() if v is not None)

    conditions = summary.get("possible_conditions", [])
    has_triage_note = bool(summary.get("triage_level"))

    return {
        "session_id": session_id,
        "fhir_version": "R4",
        "resource_type": "Bundle",
        "bundle_type": "collection",
        "resources": {
            "Patient": 1,
            "ClinicalImpression": 1,
            "Observation": obs_count,
            "Condition": len(conditions),
            "Encounter": 1,
        },
        "triage_note_included": has_triage_note,
        "ai_generated": True,
        "doctor_review_required": True,
        "export_url": f"/api/session/{session_id}/fhir",
        "disclaimer": "FHIR export is AI-generated and requires physician review before integration.",
    }


# ─────────────────────────────────────────────
#  Static Files — MUST be mounted LAST.
#  Mounting at "/" captures every unmatched route.
#  All API endpoints must be registered above this line.
# ─────────────────────────────────────────────

FRONTEND_DIR = os.getenv(
    "FRONTEND_DIR",
    os.path.join(os.path.dirname(__file__), "..", "frontend"),
)

# Root "/" → landing.html (Marketing / entry page)
# Interview form is accessible at /index.html
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root():
    """Serve landing.html at the root URL."""
    landing_path = os.path.join(FRONTEND_DIR, "landing.html")
    if os.path.exists(landing_path):
        with open(landing_path, encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    # Fallback: redirect to index.html
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/index.html")

@app.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_route():
    """Serve admin_login.html at /admin — dedicated admin entry point."""
    from fastapi.responses import RedirectResponse
    admin_login_path = os.path.join(FRONTEND_DIR, "admin_login.html")
    if os.path.exists(admin_login_path):
        with open(admin_login_path, encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return RedirectResponse(url="/admin_login.html")

if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    print(f"\n{'='*60}")
    print(f"  AnamnezAI v5.0 — Gemma 4 Medical Pre-Triage")
    print(f"  Model    : {GEMMA_MODEL} (via Ollama)")
    print(f"  Ollama   : {OLLAMA_BASE_URL}")
    print(f"  RAG      : {'Aktif' if RAG_ENABLED else 'Devre Dışı'}")
    print(f"  DB       : PostgreSQL")
    print(f"  API      : http://localhost:8000")
    print(f"  Docs     : http://localhost:8000/docs")
    print(f"  Features : Multimodal Vision | SSE Kuyruk | PostgreSQL | Vital Bulgular")
    print(f"{'='*60}\n")

    pg_init_db()
    db_load_all()

    if RAG_ENABLED:
        try:
            import rag as rag_module
            if rag_module.is_rag_available():
                stats = rag_module.get_db_stats()
                if stats.get("total_chunks", 0) == 0:
                    print("  RAG: Yerleşik tıbbi bilgi tabanı yükleniyor...")
                    rag_module.ingest_builtin_knowledge()
                    print(f"  RAG: HAZIR ({rag_module.get_db_stats().get('total_chunks')} chunk)")
                else:
                    print(f"  RAG: HAZIR ({stats.get('total_chunks')} chunk, {len(stats.get('sources', {}))} kaynak)")
            else:
                print("  RAG: chromadb/sentence-transformers kurulu değil")
        except Exception as e:
            print(f"  RAG: Atıldı — {e}")

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)



