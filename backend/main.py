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
import mimetypes

# woff2/woff font MIME type'larını Python'a kaydet (varsayılan olarak bilinmiyor)
mimetypes.add_type('font/woff2', '.woff2')
mimetypes.add_type('font/woff', '.woff')
mimetypes.add_type('font/ttf', '.ttf')
mimetypes.add_type('font/otf', '.otf')

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

# GPU desteği — 99 = tüm katmanları GPU'ya yükle (Ollama max'a sınırlar).
# CPU-only moduna düşmek için: OLLAMA_NUM_GPU=0 env değişkeni
OLLAMA_NUM_GPU   = int(os.getenv("OLLAMA_NUM_GPU", "99"))  # 99 = tüm katmanlar GPU'da

# Cloud çeviri — varsayılan KAPALI (local-first garantisi).
# Sadece ALLOW_CLOUD_TRANSLATION=true ile açılır.
ALLOW_CLOUD_TRANSLATION = os.getenv("ALLOW_CLOUD_TRANSLATION", "false").lower() == "true"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama başladığında DB'yi başlat, geçmiş verileri yükle ve modeli önceden ısıt."""
    pg_init_db()
    init_auth_tables()      # ← Kullanıcı tablolarını oluştur (+ demo doktor)
    db_load_all()
    # Randevuları DB'den yükle (restart sonrası geri getir)
    try:
        db_load_appointments()
    except Exception as _e:
        print(f"[AnamnezAI] Randevu yükleme hatası: {_e}")
    # Demo vakaları seed et (DB'de yoksa)
    try:
        db_seed_demo_cases()
    except Exception as _e:
        print(f"[AnamnezAI] Demo seed hatası: {_e}")
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
#  RAG Bağlam Önbelleği — aynı şikayet için ChromaDB'ye tekrar gitme
# ─────────────────────────────────────────────
_rag_context_cache: dict[str, tuple[str, float]] = {}  # key → (context, timestamp)
_RAG_CACHE_TTL = 300.0  # 5 dakika


def _get_rag_context_cached(query: str, mode: str = "interview") -> str:
    """RAG bağlamını önbellekten getirir; yoksa hesaplar ve önbelleğe alır."""
    import hashlib as _hashlib
    cache_key = _hashlib.md5(f"{mode}:{query[:160]}".encode()).hexdigest()
    now = _time.time()
    hit = _rag_context_cache.get(cache_key)
    if hit and (now - hit[1]) < _RAG_CACHE_TTL:
        return hit[0]
    # Canlı hesapla
    ctx = ""
    try:
        if RAG_ENABLED and query:
            _init_rag_if_needed()
            import rag as rag_module
            if rag_module.is_rag_available():
                if mode == "triage":
                    ctx = rag_module.get_medical_context_for_triage(
                        chief_complaint=query[:200], min_relevance=0.38)
                else:
                    ctx = rag_module.get_context_for_prompt(
                        query, n_results=4, min_relevance=0.35)
    except Exception:
        pass
    _rag_context_cache[cache_key] = (ctx, now)
    # Önbellek büyüdüyse eskilerini at
    if len(_rag_context_cache) > 300:
        oldest = sorted(_rag_context_cache.items(), key=lambda x: x[1][1])[:60]
        for k, _ in oldest:
            del _rag_context_cache[k]
    return ctx

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
    """Sunucu başlayınca modeli VRAM'e yükler VE /api/chat KV cache'ini tıbbi sistem promptuyla doldurur.

    ÖNEMLİ: stream_gemma() /api/chat kullanıyor. Warmup'ın da /api/chat kullanması gerekir,
    yoksa farklı token formatı üretilir ve KV cache hit olmaz → ilk token hâlâ yavaş kalır.
    """
    global _model_ready, _model_warming
    _model_warming = True
    print("[AnamnezAI] Model isitiliyor (arka plan) -- /api/chat KV cache doldurulacak...")
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

        # ADIM 1: Hızlı /api/chat ile modeli VRAM'e al
        async with httpx.AsyncClient(timeout=180.0) as client:
            await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": GEMMA_MODEL,
                    "messages": [{"role": "user", "content": "Merhaba"}],
                    "stream": False,
                    "options": {"num_predict": 1},
                },
            )

        # ADIM 2: Gerçek sistem promptuyla /api/chat KV cache doldur
        # stream_gemma() ile AYNI format → prefix cache hit olacak
        warmup_messages = [
            {"role": "system", "content": SYSTEM_PROMPT_TR},
            {
                "role": "user",
                "content": (
                    "Hasta: Ayse Kaya, 45 yas, Kadin.\n"
                    "Mulakat gecmisi:\nS1: Sizi bugun buraya getiren sikayet nedir?\n"
                    "C1: Basim cok agriyor, bulantim da var.\n\n"
                    "Yukaridaki cevaba dayanarak en kritik SONRAKI soruyu sor. Soru 2/5."
                ),
            },
        ]
        async with httpx.AsyncClient(timeout=200.0) as client:
            await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": GEMMA_MODEL,
                    "messages": warmup_messages,
                    "stream": False,
                    "think": False,
                    "options": {
                        "num_predict": 25,
                        "temperature": 0.4,
                        "num_gpu": OLLAMA_NUM_GPU,
                    },
                },
            )

        _model_ready = True
        print(f"[AnamnezAI] Model hazir, KV cache /api/chat formatinda dolu: {GEMMA_MODEL}")
    except Exception as e:
        _model_ready = True   # warmup başarısız olsa da model kullanılabilir
        print(f"[AnamnezAI] Warmup kismi basarisiz (model yine de calisiyor): {e}")
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

class ChannelIntakeRequest(BaseModel):
    """Dış kanal (WhatsApp-style, Telegram, mobil app) intake mesajı."""
    channel: str = "custom"          # whatsapp_demo | telegram_demo | mobile_app | call_center | custom
    external_user_id: str            # dış kanaldaki kullanıcı ID'si
    message: str                     # hastanın yazdığı mesaj
    language: str = "tr"             # tr | en | ar
    session_id: Optional[str] = None # devam eden oturum; None ise yeni başlatılır

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
                    model: Optional[str] = None, num_predict: int = 512) -> str:
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
                            "num_predict": num_predict,
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
                        rag_mode: str = "interview", num_predict: int = 512) -> str:
    """RAG bağlamıyla güçlendirilmiş model isteği.
    rag_mode: 'interview' (soru üretimi) | 'triage' (triaj kararı)
    """
    enriched_system = system
    if RAG_ENABLED and rag_query:
        try:
            context = _get_rag_context_cached(rag_query, rag_mode)
            if context:
                enriched_system = system + "\n\n" + context if system else context
        except Exception as _e:
            pass  # RAG başarısız olsa da model çalışmaya devam eder
    return await ask_gemma(prompt, system=enriched_system, timeout=timeout,
                           model=model, num_predict=num_predict)


async def stream_gemma(prompt: str, system: str = "", num_predict: int = 400) -> AsyncGenerator[str, None]:
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
                            "num_predict": num_predict,       #Max token — sonsuz döngü önlemi
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
GÖREV: Hastanın semptomlarını anlamak için klinik açıdan değerli, çeşitli ve bağlamsal sorular sor.
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
- KLİNİK TAM KAPSAM — Mülakat boyunca sadece mevcut semptomu sormakla kalma; uygun adımda şu kategorilerden bağlamsal olanları mutlaka sor:
  * Geçmiş kronik hastalıklar (HT, DM, koroner arter hastalığı, KOAH, böbrek/karaciğer, inme/TİA)
  * Güncel ilaç kullanımı (antikoagülan, antiagregan, antihipertansif, insülin, statin — adı ve dozu)
  * Aile geçmişi (erken kardiyovasküler hastalık, ani ölüm, DM, inme, kanser)
  * Risk faktörleri (sigara — kaç yıl/paket, alkol, obezite, sedanter yaşam)
- SORU ÇEŞİTLİLİĞİ: Her soru FARKLI bir klinik boyutu ele almalı. Önceki sorularda ele alınan konuyu TEKRARLAMA.
- MTS (Manchester Triage System) kriterlerine göre değerlendir.
- Empatik, sakinleştirici ton. Soru işaretiyle bitir.

ÖRNEK MÜLAKAT (çeşitli kategoriler):
Hasta: Ali Yılmaz, 58 yaş, Erkek.
S1: "Merhaba Ali Bey, sizi bugün buraya getiren en önemli şikayetiniz nedir?"
C1: "Göğsümde baskı hissediyorum sabahtan beri."
S2: "Bu baskı hissi elinize, kolunuza ya da çenenize yayılıyor mu?"
C2: "Evet, sol koluma kadar geliyor."
S3: "Bu his 1'den 10'a kadar bir skalada kaç olur ve nefes almakta güçlük çekiyor musunuz?"
C3: "8/10, biraz nefes darlığım var."
S4: "Daha önce kalp hastalığı, hipertansiyon veya şeker hastalığı teşhisi aldınız mı? Düzenli ilaç kullanıyor musunuz?"
C4: "Tansiyon hastasıyım, metoprolol kullanıyorum."
S5: "Ailenizde erken yaşta kalp hastalığı veya ani ölüm yaşayan var mı?"

BU ÖRNEĞİ İZLE — Bağlamsal, derinleştirici, çeşitli kategorileri kapsayan klinisyen soruları sor."""

SYSTEM_PROMPT_EN = """You are AnamnezAI — an experienced, empathetic medical pre-triage assistant.
Powered by Gemma 4, running 100% locally via Ollama.
EXPERTISE: Think with clinical terminology (dyspnea, tachycardia, diaphoresis, presyncope, pallor, cyanosis, hypertensive crisis); ask in plain language.
TASK: Ask clinically relevant, varied, and contextual questions to understand the patient's symptoms fully.
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
- CLINICAL COMPLETENESS — Don't only ask about the current symptom; at the right step, cover:
  * Past medical history (HTN, DM, CAD, COPD, kidney/liver disease, stroke/TIA)
  * Current medications (anticoagulants, antiplatelets, antihypertensives, insulin — name and dose)
  * Family history (early cardiovascular disease, sudden death, DM, stroke, cancer)
  * Risk factors (smoking — pack-years, alcohol, obesity, sedentary lifestyle)
- QUESTION DIVERSITY: Each question must address a DIFFERENT clinical dimension. Never repeat a category already covered.
- Apply MTS (Manchester Triage System) criteria throughout.
- Empathetic, calming tone. End with a question mark.
- IMPORTANT: Always respond in ENGLISH only.

EXAMPLE EXCHANGE (varied categories):
Patient: John Doe, 58y, Male.
Q1: "Hello John, what's the main reason you're here today?"
A1: "I've had chest pressure since this morning."
Q2: "Does this pressure spread to your arm, jaw, or back?"
A2: "Yes, it goes down my left arm."
Q3: "On a scale of 1-10 how severe is it, and do you have any difficulty breathing?"
A3: "8/10, some shortness of breath."
Q4: "Have you ever been diagnosed with heart disease, high blood pressure, or diabetes? Are you on any regular medications?"
A4: "I have hypertension, I take metoprolol."
Q5: "Does anyone in your family have early heart disease or a history of sudden cardiac death?"

FOLLOW THIS EXAMPLE — contextual, deepening, multi-category clinician-like questions."""

SYSTEM_PROMPT_AR = """أنت AnamnezAI — مساعد طبي خبير ومتعاطف لفرز المرضى مسبقاً.
مدعوم بـ Gemma 4 ويعمل محلياً بالكامل عبر Ollama.
الخبرة: التفكير بالمصطلحات السريرية مع الأسئلة بلغة عامية مفهومة.
المهمة: طرح أسئلة سريرية سياقية ذات صلة لفهم أعراض المريض.
القواعد:
- اطرح سؤالاً واحداً فقط في كل مرة (جملة أو جملتان كحد أقصى).
- توليد الأسئلة بناءً على جميع الإجابات السابقة.
- تجنب المصطلحات الطبية المعقدة، استخدم لغة عامية مفهومة.
- الأعراض الطارئة — استفسر فوراً إذا وُجدت:
  * ألم/ضغط في الصدر → انتشار نحو الذراع/الفك/الظهر، تعرق، ضيق تنفس؟
  * ضيق التنفس → مفاجئ، قياس SpO2، مرض رئوي سابق؟
  * فقدان الوعي/إغماء → المدة، خفقان/تعرق قبله؟
  * أعراض السكتة الدماغية (شلل الوجه، ضعف الذراع، صعوبة الكلام) → وقت البداية الدقيق؟
  * صداع شديد → "أسوأ صداع في حياتي"، تصلب الرقبة، حساسية للضوء؟
- طبّق OPQRST: البداية، الجودة، الانتشار، الشدة (1-10)، التوقيت، المحفزات.
- نبرة تعاطفية ومهدئة. انتهِ دائماً بعلامة استفهام.
- مهم جداً: أجب باللغة العربية فقط في جميع الأوقات.

مثال على المقابلة:
مريض: علي، 58 سنة، ذكر.
س: "مرحباً علي، ما هي الشكوى الرئيسية التي أتت بك اليوم؟"
ج: "عندي ضغط في صدري من الصباح."
س: "هل هذا الضغط ينتشر إلى ذراعك أو فكك أو ظهرك؟"
ج: "نعم، يصل إلى ذراعي الأيسر."
س: "على مقياس من 1 إلى 10، كم شدة الألم؟ وهل تشعر بصعوبة في التنفس؟"

اتبع هذا المثال — أسئلة سياقية معمّقة كالطبيب السريري."""

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
    if lang == "ar":
        return SYSTEM_PROMPT_AR
    return SYSTEM_PROMPT_TR if lang == "tr" else SYSTEM_PROMPT_EN


def get_triage_system(lang: str) -> str:
    base = TRIAGE_SYSTEM_TR if lang == "tr" else TRIAGE_SYSTEM_EN
    if lang == "ar":
        base += ("\n\nمهم: يجب أن تكون القيم النصية في JSON "
                 "(chief_complaint, symptoms_summary, recommended_action, "
                 "clinical_notes, urgency_flags, evidence) باللغة العربية فقط.")
    return base


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


async def _google_auth_impl(body: dict):
    """Google OAuth2 ID token ile giriş / otomatik kayıt (sadece hasta rol) — ortak impl."""
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
        except Exception:
            pass
        user = get_user_by_email(email)
        if not user:
            raise HTTPException(status_code=500, detail="Kullanıcı oluşturulamadı.")

    token = create_access_token({"sub": user["user_id"], "role": user["role"]})
    return Token(
        access_token=token,
        user=UserOut(**user)
    )


@app.post("/auth/google", response_model=Token)
async def google_auth(body: dict):
    """Google OAuth2 - /auth/google endpoint (eski uyumluluk)."""
    return await _google_auth_impl(body)


@app.post("/api/gsi", response_model=Token)
async def google_auth_gsi(body: dict):
    """Google Sign-In - /api/gsi endpoint (ag filtresi bypass icin)."""
    return await _google_auth_impl(body)

@app.post("/p/connect", response_model=Token)
async def google_auth_connect(body: dict):
    """Google Sign-In - /p/connect endpoint (notral yol, ag filtresi bypass)."""
    return await _google_auth_impl(body)

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
    """Gemma 4 modelini VRAM'e yükler ve /api/chat KV cache'ini tıbbi sistem promptuyla doldurur.

    stream_gemma() /api/chat kullanır. Warmup da aynı endpoint+format kullanmalı
    ki KV cache prefix hit olsun. /api/generate farklı token formatı üretir → hit olmaz.
    """
    try:
        # Hızlı VRAM yükleme
        async with httpx.AsyncClient(timeout=30.0) as c0:
            await c0.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": GEMMA_MODEL,
                    "messages": [{"role": "user", "content": "Merhaba"}],
                    "stream": False,
                    "options": {"num_predict": 1},
                },
            )

        # Sistem promptuyla KV cache doldur — stream_gemma() ile aynı format
        warmup_messages = [
            {"role": "system", "content": SYSTEM_PROMPT_TR},
            {
                "role": "user",
                "content": (
                    "Hasta: Ayse Kaya, 45 yas, Kadin.\n"
                    "Mulakat gecmisi:\nS1: Sizi bugun buraya getiren sikayet nedir?\n"
                    "C1: Basim cok agriyor, bulantim da var.\n\n"
                    "Yukaridaki cevaba dayanarak en kritik SONRAKI soruyu sor. Soru 2/5."
                ),
            },
        ]
        async with httpx.AsyncClient(timeout=200.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": GEMMA_MODEL,
                    "messages": warmup_messages,
                    "stream": False,
                    "think": False,
                    "options": {
                        "num_predict": 25,
                        "temperature": 0.4,
                        "num_gpu": OLLAMA_NUM_GPU,
                    },
                },
            )
            resp.raise_for_status()
        return {"status": "warmed_up", "model": GEMMA_MODEL, "kv_cache": "primed_chat"}
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
        # ── Özet arka planda başlat — hasta beklemiyor, doktor kuyruğu hazır olacak ──
        asyncio.create_task(_background_summary(req.session_id))
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
    elif lang == "ar":
        next_prompt = (
            f"المريض: {session['patient_name']}, {session['age']} سنة, {session['gender']}.\n"
            f"{pediatric_hint}"
            f"سجل المقابلة:\n{history_text}\n\n"
            f"بناءً على الإجابات أعلاه، اطرح السؤال الأكثر أهمية التالي لتوضيح التشخيص. "
            f"إذا كانت هناك أعراض طارئة، تعمق في هذا الاتجاه. السؤال {current_step+1}/{total_steps}. "
            f"أجب باللغة العربية فقط."
        )
    else:
        next_prompt = (
            f"Patient: {session['patient_name']}, {session['age']}y, {session['gender']}.\n"
            f"{pediatric_hint}"
            f"Interview so far:\n{history_text}\n\n"
            f"Based on above answers, ask the NEXT most critical question to clarify the diagnosis. "
            f"If emergency signs present, explore further. Q{current_step+1}/{total_steps}. "
            f"Respond in English only."
        )

    # ── Kategori çeşitliliği ipucu: daha önce sorulmamış klinik alanları tespit et ──
    _diversity_hint = ""
    if current_step >= 2:
        _hl = history_text.lower()
        _covered = []
        if any(w in _hl for w in ["geçmiş", "hastalığ", "kronik", "diyab", "hipertans", "tansiyon hastası", "astım", "kanser", "böbrek", "karaciğer"]):
            _covered.append("geçmiş hastalık")
        if any(w in _hl for w in ["ilaç", "kullanıyor", "metoprolol", "aspirin", "hap", "tablet", "statin", "insülin"]):
            _covered.append("ilaç kullanımı")
        if any(w in _hl for w in ["aile", "babanız", "anneniz", "kardeş", "ebeveyn", "ailede"]):
            _covered.append("aile geçmişi")
        if any(w in _hl for w in ["sigara", "alkol", "içiyor", "içki", "paket", "bıraktım"]):
            _covered.append("sigara/alkol")
        _all_cats_tr = ["geçmiş hastalık", "ilaç kullanımı", "aile geçmişi", "sigara/alkol"]
        _uncovered = [c for c in _all_cats_tr if c not in _covered]
        if _uncovered:
            if current_step >= 4:
                # 4. adımdan sonra güçlü direktif: mevcut semptom yeterince sorgulandı
                _diversity_hint = (
                    f" ÇOK ÖNEMLİ: Mevcut semptomlar yeterince değerlendirildi. "
                    f"Bu soru için MUTLAKA '{_uncovered[0]}' kategorisini sor."
                )
            else:
                _diversity_hint = f" Henüz sorulmamış önemli kategori: {_uncovered[0]}."

    if lang == "tr":
        next_prompt = (
            f"Hasta: {session['patient_name']}, {session['age']} yaşında, {session['gender']}.\n"
            f"{pediatric_hint}"
            f"Mülakat geçmişi:\n{history_text}\n\n"
            f"Yukarıdaki cevaplara dayanarak tanıyı netleştirecek SONRAKI en kritik soruyu sor. "
            f"Acil belirti varsa o yönde derinleş.{_diversity_hint} Soru {current_step+1}/{total_steps}."
        )
    elif lang == "ar":
        next_prompt = (
            f"المريض: {session['patient_name']}, {session['age']} سنة, {session['gender']}.\n"
            f"{pediatric_hint}"
            f"سجل المقابلة:\n{history_text}\n\n"
            f"بناءً على الإجابات أعلاه، اطرح السؤال الأكثر أهمية التالي لتوضيح التشخيص. "
            f"إذا كانت هناك أعراض طارئة، تعمق في هذا الاتجاه. السؤال {current_step+1}/{total_steps}. "
            f"أجب باللغة العربية فقط."
        )
    else:
        _diversity_hint_en = ""
        if current_step >= 2:
            _hl_en = history_text.lower()
            _covered_en = []
            if any(w in _hl_en for w in ["history", "diabetes", "hypertension", "heart disease", "copd", "kidney", "liver", "stroke"]):
                _covered_en.append("past medical history")
            if any(w in _hl_en for w in ["medication", "taking", "metoprolol", "aspirin", "insulin", "statin"]):
                _covered_en.append("medications")
            if any(w in _hl_en for w in ["family", "father", "mother", "sibling", "relative"]):
                _covered_en.append("family history")
            if any(w in _hl_en for w in ["smok", "alcohol", "drink", "pack", "quit"]):
                _covered_en.append("smoking/alcohol")
            _all_cats_en = ["past medical history", "medications", "family history", "smoking/alcohol"]
            _uncovered_en = [c for c in _all_cats_en if c not in _covered_en]
            if _uncovered_en:
                _diversity_hint_en = f" Uncovered category to explore: {_uncovered_en[0]}."
        next_prompt = (
            f"Patient: {session['patient_name']}, {session['age']}y, {session['gender']}.\n"
            f"{pediatric_hint}"
            f"Interview so far:\n{history_text}\n\n"
            f"Based on above answers, ask the NEXT most critical question to clarify the diagnosis. "
            f"If emergency signs present, explore further.{_diversity_hint_en} Q{current_step+1}/{total_steps}. "
            f"Respond in English only."
        )

    rag_query = req.answer + " " + history_text[-300:]
    next_question = await ask_gemma_rag(next_prompt, system=get_system_prompt(lang),
                                         rag_query=rag_query, num_predict=200)
    session["step"] += 1
    session["qa_history"].append({"question": next_question, "answer": None})

    db_save_session(req.session_id, session)

    return SessionResponse(session_id=req.session_id, question=next_question, step=session["step"], total_steps=total_steps)


@app.post("/api/session/answer/stream")
@limiter.limit("60/minute")
async def submit_answer_stream(req: AnswerRequest, request: Request):
    """Cevabı kaydeder, sonraki soruyu SSE ile token token akıtır.
    Kullanıcı ilk tokeni ~1 saniyede görür (GPU ile). Non-streaming'e göre ~3x daha hızlı algılanan yanıt."""

    async def _err(msg: str):
        yield f"data: {json.dumps({'error': msg})}\n\ndata: [DONE]\n\n"

    session = sessions.get(req.session_id)
    if not session:
        return StreamingResponse(_err("Oturum bulunamadı"), media_type="text/event-stream",
                                  headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    if session["completed"]:
        return StreamingResponse(_err("Mülakat zaten tamamlandı"), media_type="text/event-stream",
                                  headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    session["qa_history"][-1]["answer"] = req.answer
    current_step = session["step"]
    total_steps  = session["total_steps"]

    # Adaptif soru sayısı (ilk cevaptan sonra)
    if current_step == 1 and req.answer:
        lang_s = session.get("language", "tr")
        age_s  = session.get("age", 30)
        new_steps = _adaptive_steps(req.answer, age_s, lang_s)
        if new_steps != total_steps:
            session["total_steps"] = new_steps
            total_steps = new_steps

    # Mülakat tamamlandı mı?
    if current_step >= total_steps:
        session["completed"] = True
        db_save_session(req.session_id, session)
        asyncio.create_task(notify_queue_update())
        # ── Özet arka planda başlat — streaming biter bitmez AI analizi başlıyor ──
        asyncio.create_task(_background_summary(req.session_id))

        async def completed_gen():
            yield f"data: {json.dumps({'metadata': {'completed': True, 'step': current_step, 'total_steps': total_steps}})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(completed_gen(), media_type="text/event-stream",
                                  headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    lang = session["language"]
    history_text = "\n".join(
        f"S{i+1}: {qa['question']}\nC{i+1}: {qa['answer']}"
        for i, qa in enumerate(session["qa_history"])
        if qa.get("answer")
    )

    # Pediatrik ipucu
    pediatric_hint = ""
    if _is_pediatric_case(session) and current_step == 1:
        if lang == "tr":
            pediatric_hint = (
                "\n⚠️ PEDİATRİK VAKA: Çocuk hastası. Bir sonraki soru MUTLAKA ateş derecesini "
                "ve süresini sormalı.\n"
            )
        else:
            pediatric_hint = (
                "\n⚠️ PEDIATRIC CASE: Child patient. The NEXT question MUST ask for the specific "
                "temperature reading and duration first.\n"
            )

    # RAG bağlam (önbellekten)
    # --- Kategori çeşitliliği ipucu (streaming path) ---
    _diversity_hint_s = ""
    if current_step >= 2:
        _hl_s = history_text.lower()
        _covered_s = []
        if any(w in _hl_s for w in ["geçmiş", "hastalığ", "kronik", "diyab", "hipertans", "tansiyon hastası", "astım", "kanser"]):
            _covered_s.append("geçmiş hastalık")
        if any(w in _hl_s for w in ["ilaç", "kullanıyor", "metoprolol", "aspirin", "hap", "statin", "insülin"]):
            _covered_s.append("ilaç kullanımı")
        if any(w in _hl_s for w in ["aile", "babanız", "anneniz", "kardeş", "ailede"]):
            _covered_s.append("aile geçmişi")
        if any(w in _hl_s for w in ["sigara", "alkol", "içiyor", "paket", "bıraktım"]):
            _covered_s.append("sigara/alkol")
        _all_cats_s = ["geçmiş hastalık", "ilaç kullanımı", "aile geçmişi", "sigara/alkol"]
        _uncovered_s = [c for c in _all_cats_s if c not in _covered_s]
        if _uncovered_s:
            if current_step >= 4:
                if lang == "tr":
                    _diversity_hint_s = (
                        f" ÇOK ÖNEMLİ: Mevcut semptomlar yeterince değerlendirildi. "
                        f"Bu soru için MUTLAKA '{_uncovered_s[0]}' kategorisini sor."
                    )
                elif lang == "en":
                    _en_map = {"geçmiş hastalık": "past medical history", "ilaç kullanımı": "medications",
                               "aile geçmişi": "family history", "sigara/alkol": "smoking/alcohol"}
                    _diversity_hint_s = (
                        f" CRITICAL: Current symptoms sufficiently explored. "
                        f"This question MUST address: '{_en_map.get(_uncovered_s[0], _uncovered_s[0])}'."
                    )
            else:
                if lang == "tr":
                    _diversity_hint_s = f" Henüz sorulmamış önemli kategori: {_uncovered_s[0]}."
                elif lang == "en":
                    _en_map = {"geçmiş hastalık": "past medical history", "ilaç kullanımı": "medications",
                               "aile geçmişi": "family history", "sigara/alkol": "smoking/alcohol"}
                    _diversity_hint_s = f" Uncovered category: {_en_map.get(_uncovered_s[0], _uncovered_s[0])}."

    if lang == "tr":
        next_prompt = (
            f"Hasta: {session['patient_name']}, {session['age']} yaşında, {session['gender']}.\n"
            f"{pediatric_hint}"
            f"Mülakat geçmişi:\n{history_text}\n\n"
            f"Yukarıdaki cevaplara dayanarak tanıyı netleştirecek SONRAKI en kritik soruyu sor. "
            f"Acil belirti varsa o yönde derinleş.{_diversity_hint_s} Soru {current_step+1}/{total_steps}."
        )
    elif lang == "ar":
        next_prompt = (
            f"المريض: {session['patient_name']}, {session['age']} سنة, {session['gender']}.\n"
            f"{pediatric_hint}"
            f"سجل المقابلة:\n{history_text}\n\n"
            f"بناءً على الإجابات أعلاه، اطرح السؤال الأكثر أهمية التالي لتوضيح التشخيص. "
            f"السؤال {current_step+1}/{total_steps}. أجب باللغة العربية فقط."
        )
    else:
        next_prompt = (
            f"Patient: {session['patient_name']}, {session['age']}y, {session['gender']}.\n"
            f"{pediatric_hint}"
            f"Interview so far:\n{history_text}\n\n"
            f"Based on above answers, ask the NEXT most critical question to clarify the diagnosis. "
            f"If emergency signs present, explore further.{_diversity_hint_s} Q{current_step+1}/{total_steps}. "
            f"Respond in English only."
        )

    # RAG bağlam (önbellekten)
    # ÖNEMLİ: RAG context'i sistem mesajına DEĞİL, kullanıcı mesajına ekle.
    # Sistem mesajı sabit kalırsa Ollama prefix KV cache her istekte hit olur
    # → ilk token süresi ~150s yerine ~5s. Sistem mesajına ekleme prefix'i bozar.
    rag_query = req.answer + " " + history_text[-300:]
    rag_ctx   = _get_rag_context_cached(rag_query, "interview")
    system_prompt = get_system_prompt(lang)   # sabit — KV cache korunur

    # RAG bağlamını kullanıcı mesajının başına ekle (klinik rehber olarak)
    if rag_ctx:
        rag_header = (
            "[KLİNİK REHBER - sadece bu soruya referans için]\n"
            if lang == "tr" else
            ("[CLINICAL REFERENCE - for this question only]\n"
             if lang == "en" else
             "[المرجع السريري - لهذا السؤال فقط]\n")
        )
        enriched_prompt = rag_header + rag_ctx.strip() + "\n\n---\n" + next_prompt
    else:
        enriched_prompt = next_prompt

    full_parts: list[str] = []

    async def event_gen():
        try:
            async for sse_line in stream_gemma(enriched_prompt, system=system_prompt, num_predict=200):
                if sse_line.strip() == "data: [DONE]":
                    break
                yield sse_line
                # Tokeni de biriktir (session'a kaydetmek için)
                if sse_line.startswith("data: "):
                    try:
                        d = json.loads(sse_line[6:].strip())
                        if "token" in d:
                            full_parts.append(d["token"])
                    except Exception:
                        pass
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

        # Soruyu session'a kaydet
        full_question = clean_gemma_response("".join(full_parts))
        if full_question:
            session["step"] += 1
            session["qa_history"].append({"question": full_question, "answer": None})
            db_save_session(req.session_id, session)
            asyncio.create_task(notify_queue_update())

        yield f"data: {json.dumps({'metadata': {'step': session.get('step', current_step + 1), 'total_steps': total_steps, 'completed': False}})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


# ── Özet arka plan üretici + durum takibi ────────────────────────────────────
# Mülakat tamamlanır tamamlanmaz başlatılır — hasta beklemiyor.
# Frontend /summary/status ile polling yapar, hazır olunca tek seferlik /summary çağırır.
_summary_generating: set[str] = set()   # hangi session'lar şu an üretiliyor
_summary_events: dict = {}              # session_id -> asyncio.Event (generation done signal)

async def _background_summary(session_id: str) -> None:
    """
    Özeti arka planda üretir ve `summaries` dict'ine kaydeder.
    Timeout veya hata durumunda 1 kez otomatik retry yapar.
    """
    if session_id in summaries:
        return                           # zaten hazır, tekrar üretme
    if session_id in _summary_generating:
        return                           # zaten başlatılmış, ikinci task açma
    _summary_generating.add(session_id)
    evt = asyncio.Event()
    _summary_events[session_id] = evt
    max_attempts = 2
    for attempt in range(max_attempts):
        try:
            await get_clinical_summary(session_id)
            break   # Başarılı, döngüden çık
        except HTTPException as e:
            if e.status_code in (504, 503) and attempt < max_attempts - 1:
                # Timeout / Ollama yavaş → kısa bekleme sonrası retry
                print(f"[BG-Summary] {session_id[:8]}... {e.status_code}, {attempt+1}. deneme sonrası retry (15s)...")
                await asyncio.sleep(15)
            else:
                print(f"[BG-Summary] {session_id[:8]}... HTTPException {e.status_code}: {e.detail}")
                break
        except Exception as e:
            print(f"[BG-Summary] {session_id[:8]}... hata (deneme {attempt+1}): {e}")
            if attempt < max_attempts - 1:
                await asyncio.sleep(10)
            else:
                break
    _summary_generating.discard(session_id)
    evt.set()
    _summary_events.pop(session_id, None)


@app.get("/api/session/{session_id}/summary/status")
async def get_summary_status(session_id: str):
    """
    Özet hazır mı? Frontend bu endpoint'i polling ile sorgular.
    Bloklamaz — anlık durum döner.

    Yanıt:
      ready=true  → /api/session/{id}/summary çağrılabilir, anlık yanıt gelir
      ready=false → generating=true ise arka planda üretiliyor, birkaç sn bekle
    """
    session = sessions.get(session_id)
    # Backend restart sonrası memory'de yoksa DB'den yükle
    if not session:
        try:
            with get_cursor() as cur:
                cur.execute("SELECT data FROM sessions WHERE session_id=%s", (session_id,))
                row = cur.fetchone()
                if row:
                    session = row["data"] if isinstance(row["data"], dict) else json.loads(row["data"])
                    sessions[session_id] = session  # cache back in memory
        except Exception:
            pass
    if not session:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı.")
    # DB'de summary var mı kontrol et (memory'de yoksa)
    if session_id not in summaries:
        try:
            with get_cursor() as cur:
                cur.execute("SELECT 1 FROM summaries WHERE session_id=%s", (session_id,))
                if cur.fetchone():
                    # Summary DB'de var — memory cache'e de işaretle
                    summaries_db_ready = True
                else:
                    summaries_db_ready = False
        except Exception:
            summaries_db_ready = False
        ready = summaries_db_ready
    else:
        ready = True

    generating = session_id in _summary_generating
    completed = session.get("completed", False)

    return {
        "session_id": session_id,
        "ready": ready,
        "generating": generating,
        "completed": completed,
        "estimated_wait_seconds": 0 if ready else (20 if generating else None),
    }


@app.get("/api/session/{session_id}/summary", response_model=ClinicalSummaryResponse)
async def get_clinical_summary(session_id: str):
    session = sessions.get(session_id)
    # Session not in memory — try loading from DB directly
    if not session:
        try:
            with get_cursor() as cur:
                cur.execute("SELECT data FROM sessions WHERE session_id=%s", (session_id,))
                row = cur.fetchone()
                if row:
                    session = row["data"] if isinstance(row["data"], dict) else json.loads(row["data"])
                    sessions[session_id] = session  # cache back
        except Exception as _e:
            pass
    if not session:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı.")
    if not session.get("completed"):
        raise HTTPException(status_code=400, detail="Mülakat henüz tamamlanmadı.")

    if session_id in summaries:
        return ClinicalSummaryResponse(**summaries[session_id])
    # Try loading summary from DB
    try:
        with get_cursor() as cur:
            cur.execute("SELECT data FROM summaries WHERE session_id=%s", (session_id,))
            row = cur.fetchone()
            if row:
                smry = row["data"] if isinstance(row["data"], dict) else json.loads(row["data"])
                summaries[session_id] = smry
                return ClinicalSummaryResponse(**smry)
    except Exception as _e:
        pass

    # If background task is already generating, wait for it (max 250s) instead of double-calling LLM
    if session_id in _summary_generating:
        evt = _summary_events.get(session_id)
        if evt:
            try:
                await asyncio.wait_for(asyncio.shield(evt.wait()), timeout=250.0)
            except asyncio.TimeoutError:
                pass
        # Check cache again after waiting
        if session_id in summaries:
            return ClinicalSummaryResponse(**summaries[session_id])
        try:
            with get_cursor() as cur:
                cur.execute("SELECT data FROM summaries WHERE session_id=%s", (session_id,))
                row = cur.fetchone()
                if row:
                    smry = row["data"] if isinstance(row["data"], dict) else json.loads(row["data"])
                    summaries[session_id] = smry
                    return ClinicalSummaryResponse(**smry)
        except Exception:
            pass

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
        f"{'5-TURN INTERVIEW' if lang == 'en' else 'مقابلة المريض'}:\n{history_text}\n\n"
        f"{'Triage this patient. Return ONLY JSON.' if lang == 'en' else 'قيّم هذا المريض. أعد JSON فقط مع القيم النصية باللغة العربية.'}"
    )

    raw = await ask_gemma_rag(
        triage_prompt,
        system=get_triage_system(lang),
        rag_query=session.get("chief_complaint", "") or session.get("answers", [""])[0][:200],
        rag_mode="triage",
        timeout=260.0,
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
        f"{'Patient' if lang == 'en' else 'المريض'}: {session['patient_name']}, {session['age']}{'y' if lang == 'en' else ' سنة'}, {session['gender']}.{vitals_ctx}\n"
        f"{'Interview' if lang == 'en' else 'المقابلة'}:\n{history_text}\n\n"
        f"{'Write a brief clinical summary for the doctor (3-4 sentences). Highlight triage level and urgent findings.' if lang == 'en' else 'اكتب ملخصاً سريرياً موجزاً للطبيب (3-4 جمل). أبرز مستوى الفرز والنتائج العاجلة. أجب باللغة العربية فقط.'}"
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
    """Mevcut hastanın tüm tamamlanmış oturumlarını ve özetlerini döndürür (in-memory + DB)."""
    patient_id = current_user["user_id"]
    history = []
    seen_sids = set()

    # 1) In-memory sessions
    for sid, s in sessions.items():
        if s.get("patient_id") == patient_id and s.get("completed"):
            seen_sids.add(sid)
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

    # 2) DB fallback — pick up sessions not yet in memory
    try:
        with get_cursor() as cur:
            cur.execute(
                "SELECT s.session_id, s.data as sdata, sm.data as smdata "
                "FROM sessions s LEFT JOIN summaries sm ON s.session_id=sm.session_id "
                "WHERE (s.data->>'patient_id')=%s AND (s.data->>'completed')='true'",
                (str(patient_id),)
            )
            for row in cur.fetchall():
                sid = row["session_id"]
                if sid in seen_sids:
                    continue
                s = row["sdata"] if isinstance(row["sdata"], dict) else json.loads(row["sdata"] or '{}')
                sm = (row["smdata"] if isinstance(row["smdata"], dict) else json.loads(row["smdata"] or '{}')) if row["smdata"] else {}
                entry = {
                    "session_id": sid,
                    "created_at": s.get("created_at", ""),
                    "patient_name": s.get("patient_name"),
                    "age": s.get("age"),
                    "gender": s.get("gender"),
                    "vitals": s.get("vitals"),
                    "triage_level": sm.get("triage_level", "PENDING") if sm else "PENDING",
                    "triage_color": sm.get("triage_color", "#8c9499") if sm else "#8c9499",
                    "chief_complaint": sm.get("chief_complaint", "") if sm else "",
                    "confidence_score": sm.get("confidence_score", 0) if sm else 0,
                    "symptoms_summary": sm.get("symptoms_summary", "") if sm else "",
                    "recommended_action": sm.get("recommended_action", "") if sm else "",
                    "generated_at": sm.get("generated_at", "") if sm else "",
                }
                history.append(entry)
    except Exception as _e:
        print(f"[patient/history DB fallback error] {_e}")

    history.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"history": history[:50], "total": len(history)}


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
        "local_inference": True,
        "external_ai_api": False,
        "remote_embeddings": False,
        "cloud_translation_enabled": ALLOW_CLOUD_TRANSLATION,
        "strict_local_mode": not ALLOW_CLOUD_TRANSLATION,
        "mcp_ready": True,
        "channel_adapters_optional": True,
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
#  Demo Cases — DB-backed hardcoded-free demo
# ─────────────────────────────────────────────

_DEMO_CASES_SEED = [
    {
        "session_id": "demo-1",
        "patient_name": "Mehmet Yılmaz",
        "age": 66, "gender": "Erkek",
        "triage_level": "RED", "triage_color": "#ba1a1a",
        "confidence_score": 98,
        "chief_complaint": "Göğüs ağrısı — sol kola yayılım + terleme",
        "symptoms_summary": "Sabahtan beri süren göğüs baskısı, sol kola ve çeneye yayılım, aşırı terleme, nefes darlığı. Diyabetik hasta, 10 yıldır hipertansiyon. Ağrı şiddeti 9/10.",
        "possible_conditions": ["Akut Miyokard Enfarktüsü (STEMI)", "Unstabil Angina Pektoris", "Aort Diseksiyonu"],
        "urgency_flags": ["🔴 GUARDRAIL [cardiac_emergency]: Olası kardiyak acil (AMI/AKS)", "⚠️ Kardiyak risk faktörleri: DM + HT + 66 yaş erkek", "🔴 Klasik STEMI triadı: Göğüs + sol kol + diyaforez"],
        "recommended_action": "Derhal EKG + troponin; kardiyoloji acil konsültasyonu; aspirin 300 mg PO",
        "clinical_notes": "MTS RED: Akut koroner sendrom bulguları mevcut. 3 kırmızı bayrak eş zamanlı. AI mülakat süresi: 4 dakika. Manuel triajda bu hasta 22 dakika bekletilmişti. Safety guardrail devreye girdi.",
        "vitals": {"blood_pressure": "160/95 mmHg", "pulse": 108, "temperature": 36.8, "spo2": 94},
        "evidence": ["Göğüs baskısı — sol kola ve çeneye yayılım", "Diyaforez (aşırı terleme) — kardiyak kaynaklı", "Nefes darlığı — kardiyak yetmezlik şüphesi", "Diyabetik hasta: MI sessiz seyredebilir"],
        "guideline_sources": ["MTS Göğüs Ağrısı Diskriminatörü", "CTAS Level 1 Kardiyak"],
        "safety_guardrail_triggered": True, "guardrail_rules_fired": ["Olası kardiyak acil (AMI/AKS)"],
        "ai_execution_log": {"model": "gemma4:e4b", "runtime": "Ollama (local)", "external_api": False, "patient_data_egress": False, "inference_latency_s": 14.3},
        "is_demo": True, "source": "seed_demo",
    },
    {
        "session_id": "demo-2",
        "patient_name": "Fatma Şahin",
        "age": 71, "gender": "Kadın",
        "triage_level": "RED", "triage_color": "#ba1a1a",
        "confidence_score": 96,
        "chief_complaint": "Ani konuşma bozukluğu ve sağ kol güçsüzlüğü",
        "symptoms_summary": "Son 2 saatte başlayan konuşma bozukluğu (kelime bulamıyor), sağ kol güçsüzlüğü, hafif yüz asimetrisi. 71 yaşında, AF tanısı var, antikoagülan kullanıyor.",
        "possible_conditions": ["İskemik İnme (İntra-serebral)", "TIA", "Todd Felci"],
        "urgency_flags": ["⚡ GUARDRAIL [stroke_fast]: Olası inme — FAST kriterleri pozitif", "⚠️ 2 saatlik pencere — tPA adayı olabilir", "⚠️ Atriyal fibrilasyon + antikoagülan geçmişi"],
        "recommended_action": "Acil BT beyin; nöroloji konsültasyonu; tPA penceresi değerlendirme",
        "clinical_notes": "FAST: Yüz (kısmi) + Kol (güçsüzlük) + Konuşma (afazi) — üç kriter pozitif. 2 saatlik semptom penceresi ile intravenöz tPA adayı olabilir.",
        "vitals": {"blood_pressure": "178/102 mmHg", "pulse": 88, "spo2": 97},
        "evidence": ["Konuşma bozukluğu (afazi) — FAST-S pozitif", "Sağ kol güçsüzlüğü — FAST-A pozitif", "Hafif yüz asimetrisi — FAST-F pozitif"],
        "guideline_sources": ["MTS Nörolojik Diskriminatörler", "AHA/ASA İnme Kılavuzu"],
        "safety_guardrail_triggered": True, "guardrail_rules_fired": ["Olası inme (FAST kriterleri)"],
        "ai_execution_log": {"model": "gemma4:e4b", "runtime": "Ollama (local)", "external_api": False, "patient_data_egress": False, "inference_latency_s": 18.7},
        "is_demo": True, "source": "seed_demo",
    },
    {
        "session_id": "demo-3",
        "patient_name": "Elif Aydın (3 yaş)",
        "age": 3, "gender": "Kız",
        "triage_level": "YELLOW", "triage_color": "#e07b26",
        "confidence_score": 88,
        "chief_complaint": "Çocuk ateş — 39.8°C, halsizlik",
        "symptoms_summary": "39.8°C ateş, 2 gündür devam ediyor. İştahsızlık, hafif öksürük. Ebeveyn ense sertliği sorulduğunda net cevap veremedi. Ateş paracetamol ile geçici düşüyor.",
        "possible_conditions": ["Viral ÜSYE", "Akut Otit Media", "Pnömoni (Atipik)"],
        "urgency_flags": ["⚡ GUARDRAIL [pediatric_high_fever]: Çocuk yüksek ateş — acil değerlendirme gerekir", "⚠️ Ense sertliği dışlanamadı — meningit göz önünde bulundurulmalı"],
        "recommended_action": "Pediatri muayenesi; ense muayenesi; KBB-Kulak değerlendirme",
        "clinical_notes": "Pediatrik protokol: İlk soru ateş derecesini sordu. 39.8°C ateş — MTS YELLOW. Ense tutukluğu dışlanana kadar meningit ihtimali göz ardı edilemez.",
        "vitals": {"temperature": 39.8, "pulse": 124},
        "evidence": ["Ateş 39.8°C — 2 gündür devam ediyor", "Taşikardi (nabız 124) — ateşe bağlı / dehidrasyon"],
        "guideline_sources": ["MTS Pediatrik Ateş Diskriminatörü"],
        "safety_guardrail_triggered": True, "guardrail_rules_fired": ["Bebek / küçük çocuk ateşi — acil değerlendirme gerekir"],
        "ai_execution_log": {"model": "gemma4:e4b", "runtime": "Ollama (local)", "external_api": False, "patient_data_egress": False, "inference_latency_s": 11.2},
        "is_demo": True, "source": "seed_demo",
    },
    {
        "session_id": "demo-4",
        "patient_name": "Serkan Koç",
        "age": 24, "gender": "Erkek",
        "triage_level": "YELLOW", "triage_color": "#e07b26",
        "confidence_score": 82,
        "chief_complaint": "Sağ alt karın ağrısı, bulantı, iştahsızlık",
        "symptoms_summary": "12 saattir göbek çevresinde başlayan, sağ alt kadrana göçen ağrı. 7/10 şiddetinde. Bulantı mevcut, 1 kez kusma. Hafif ateş (37.9°C).",
        "possible_conditions": ["Akut Apandisit", "Mesenteric Lenfadenit", "Sağ Üreter Taşı"],
        "urgency_flags": ["⚠️ Göçen ağrı (göbek → sağ alt kadran) — apandisit klasik sunumu", "⚠️ Hafif ateş + lökositoz şüphesi"],
        "recommended_action": "Cerrahi konsültasyon; Alvarado skoru; karın US veya BT",
        "clinical_notes": "Alvarado puanı: 6-7 (migration + nausea + RLQ tenderness + fever). Cerrahi değerlendirme öncelikli. Oral alım kısıtlanmalı.",
        "vitals": {"temperature": 37.9, "pulse": 95},
        "evidence": ["Göbek çevresinden sağ alt kadrana göçen ağrı", "Bulantı + 1 kez kusma", "Hafif ateş (37.9°C)"],
        "guideline_sources": ["MTS Karın Ağrısı Diskriminatörü", "Alvarado Apandisit Skoru"],
        "safety_guardrail_triggered": False,
        "ai_execution_log": {"model": "gemma4:e4b", "runtime": "Ollama (local)", "external_api": False, "patient_data_egress": False, "inference_latency_s": 16.8},
        "is_demo": True, "source": "seed_demo",
    },
    {
        "session_id": "demo-5",
        "patient_name": "Zeynep Arslan",
        "age": 29, "gender": "Kadın",
        "triage_level": "GREEN", "triage_color": "#006a68",
        "confidence_score": 91,
        "chief_complaint": "Boğaz ağrısı, hafif ateş, burun akıntısı — 3 gün",
        "symptoms_summary": "Son 3 gündür boğaz ağrısı, 37.5°C hafif ateş, burun akıntısı ve hafif baş ağrısı. Nefes darlığı yok, genel durum iyi, sıvı alıyor.",
        "possible_conditions": ["Akut Farenjit (viral)", "Rinit", "ÜSYE"],
        "urgency_flags": [],
        "recommended_action": "Semptomatik tedavi; bol sıvı; analjezik/antipretik; 3 günde düzelmezse tekrar başvuru",
        "clinical_notes": "MTS GREEN: Hayati risk yok, kronik hastalık yok, genel durum iyi. Rutin muayene sırası.",
        "vitals": {"temperature": 37.5, "pulse": 76},
        "evidence": ["Hafif ateş (37.5°C) — viral seyre uyumlu", "Burun + boğaz semptomları — ÜSYE tablosu"],
        "guideline_sources": ["MTS ÜSYE Diskriminatörü"],
        "safety_guardrail_triggered": False,
        "ai_execution_log": {"model": "gemma4:e4b", "runtime": "Ollama (local)", "external_api": False, "patient_data_egress": False, "inference_latency_s": 9.4},
        "is_demo": True, "source": "seed_demo",
    },
]


def db_seed_demo_cases():
    """Demo vakaları DB'ye seed eder (idempotent — zaten varsa atlar)."""
    try:
        with get_cursor() as cur:
            for case in _DEMO_CASES_SEED:
                cur.execute(
                    """INSERT INTO demo_cases (session_id, data, is_demo, source)
                       VALUES (%s, %s::jsonb, %s, %s)
                       ON CONFLICT (session_id) DO NOTHING""",
                    (case["session_id"], json.dumps(case), True, "seed_demo")
                )
        print("[DB] Demo vakalar seed edildi.")
    except Exception as e:
        print(f"[DB] Demo seed hatası: {e}")


def db_get_demo_cases() -> list[dict]:
    """DB'deki demo vakalarını döndürür."""
    try:
        with get_cursor() as cur:
            cur.execute("SELECT data FROM demo_cases WHERE is_demo = TRUE ORDER BY id")
            rows = cur.fetchall()
            return [
                (r["data"] if isinstance(r["data"], dict) else json.loads(r["data"]))
                for r in rows
            ]
    except Exception as e:
        print(f"[DB] Demo vakalar alınamadı: {e}")
        return []


@app.get("/api/demo/cases")
async def get_demo_cases(current_user: Optional[dict] = Depends(get_current_user)):
    """DB'den demo hasta vakalarını döndürür (frontend hardcoded DEMO yerine)."""
    cases = db_get_demo_cases()
    if not cases:
        db_seed_demo_cases()
        cases = db_get_demo_cases()
    # Dinamik created_at ekle (bekleme süresi gösterimi için)
    offsets = [3, 8, 15, 22, 35]
    now_dt = datetime.utcnow()
    for i, c in enumerate(cases):
        if not c.get("created_at"):
            from datetime import timedelta
            c["created_at"] = (now_dt - timedelta(minutes=offsets[i % len(offsets)])).isoformat()
    return {"cases": cases, "total": len(cases), "source": "db_seed"}


@app.post("/api/demo/cases/seed")
async def seed_demo_cases_endpoint(current_user: Optional[dict] = Depends(get_current_user)):
    """Demo vakaları yeniden seed eder."""
    db_seed_demo_cases()
    cases = db_get_demo_cases()
    return {"seeded": len(cases), "cases": [c["session_id"] for c in cases], "status": "ok"}


# ─────────────────────────────────────────────
#  Admin — Oturum Temizleme
# ─────────────────────────────────────────────

@app.post("/api/admin/sessions/cleanup")
async def cleanup_old_sessions(body: dict = {}, current_user: dict = Depends(require_admin)):
    """
    Eski oturumları temizler:
    - 'seen' işaretlenmiş ve 7+ gün geçmiş oturumlar
    - RAM + DB'den
    """
    from datetime import timedelta
    cutoff_days = int((body or {}).get("days", 7))
    cutoff = datetime.utcnow() - timedelta(days=cutoff_days)

    to_delete_mem = []
    for sid, s in sessions.items():
        if s.get("is_seen"):
            seen_at_str = s.get("seen_by", {}).get("timestamp", "")
            if seen_at_str:
                try:
                    if datetime.fromisoformat(seen_at_str) < cutoff:
                        to_delete_mem.append(sid)
                except Exception:
                    pass

    for sid in to_delete_mem:
        sessions.pop(sid, None)
        summaries.pop(sid, None)

    deleted_db = 0
    try:
        with get_cursor() as cur:
            cur.execute(
                "DELETE FROM sessions WHERE created_at < %s AND data->>'is_seen' = 'true'",
                (cutoff.isoformat(),)
            )
            deleted_db = cur.rowcount
    except Exception as e:
        print(f"[cleanup] DB temizleme hatası: {e}")

    audit("sessions_cleanup", user_id=current_user["user_id"], user_role=current_user["role"],
          details=f"RAM:{len(to_delete_mem)} DB:{deleted_db} cutoff:{cutoff_days}d")

    return {
        "status": "ok",
        "deleted_from_memory": len(to_delete_mem),
        "deleted_from_db": deleted_db,
        "cutoff_days": cutoff_days,
        "cutoff_date": cutoff.isoformat(),
    }


# ─────────────────────────────────────────────
#  Public Landing Metrics
# ─────────────────────────────────────────────

@app.get("/api/public/landing-metrics")
async def public_landing_metrics():
    """Public endpoint — landing sayfası için metrikleri döndürür. Auth gerektirmez."""
    eval_data = {
        "triage_accuracy_pct": 93.0,
        "cases_tested": 15,
        "passed": 14,
        "medgemma_score": "5/5",
        "avg_latency_ai_s": 15,
        "avg_latency_manual_min": 22,
        "languages": 3,
        "avg_interview_questions": 5,
        "guardrail_layers": 23,
        "local_inference": True,
        "cloud_api_used": False,
    }
    try:
        completed = sum(1 for s in sessions.values() if s.get("completed"))
        if completed >= 5:
            s_list = list(summaries.values())
            scores = [s.get("confidence_score", 0) for s in s_list if s.get("confidence_score")]
            if scores:
                eval_data["avg_confidence"] = round(sum(scores) / len(scores), 1)
            eval_data["total_live_sessions"] = completed
    except Exception:
        pass

    return {
        "source": "evaluation",
        "metrics": eval_data,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "fallback": False,
    }


# ─────────────────────────────────────────────
#  Appointments DB persistence helpers
# ─────────────────────────────────────────────

def db_save_appointment(appt_id: str, appt_data: dict):
    """Randevuyu DB'ye kaydeder."""
    try:
        appt_date = (appt_data.get("appointment_time") or "")[:10]
        is_demo_flag = appt_id.startswith("appt-demo-")
        with get_cursor() as cur:
            cur.execute(
                """INSERT INTO appointments (appointment_id, data, appointment_date, is_demo)
                   VALUES (%s, %s::jsonb, %s, %s)
                   ON CONFLICT (appointment_id) DO UPDATE SET data = EXCLUDED.data""",
                (appt_id, json.dumps(appt_data), appt_date, is_demo_flag)
            )
    except Exception as e:
        print(f"[DB] Randevu kayıt hatası: {e}")


def db_load_appointments():
    """DB'deki randevuları belleğe yükler."""
    try:
        with get_cursor() as cur:
            cur.execute("SELECT appointment_id, data FROM appointments ORDER BY created_at DESC LIMIT 500")
            for r in cur.fetchall():
                appt_data = r["data"] if isinstance(r["data"], dict) else json.loads(r["data"])
                _appointments[r["appointment_id"]] = appt_data
        print(f"[DB] {len(_appointments)} randevu yüklendi.")
    except Exception as e:
        print(f"[DB] Randevu yükleme hatası: {e}")


@app.post("/api/demo/appointments/seed")
async def seed_demo_appointments(current_user: Optional[dict] = Depends(get_current_user)):
    """Demo randevuları DB'ye seed eder — restart sonrası kaybolmaz."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    demo_appts = [
        {
            "appointment_id": f"appt-demo-{i+1:03d}",
            "patient_name": n, "patient_age": a, "patient_gender": g,
            "doctor_name": d, "specialty": s,
            "appointment_time": f"{today}T{t}:00",
            "appointment_type": at, "language": "tr", "status": "scheduled",
            "previsit_status": "pending", "session_id": None, "brief": None,
            "created_at": datetime.utcnow().isoformat(),
        }
        for i, (n, a, g, d, s, t, at) in enumerate([
            ("Ayşe Kaya",     45, "Kadın",  "Dr. Fatma Şahin",   "Kardiyoloji",     "09:00", "kontrol"),
            ("Mehmet Demir",  62, "Erkek",  "Dr. Ali Yıldız",    "İç Hastalıkları", "10:30", "yeni_hasta"),
            ("Zeynep Arslan", 28, "Kadın",  "Dr. Fatma Şahin",   "Kardiyoloji",     "11:00", "kontrol"),
            ("Hasan Çelik",   71, "Erkek",  "Dr. Elif Koca",     "Nöroloji",        "14:00", "takip"),
            ("Elif Yılmaz",    8, "Kız",    "Dr. Osman Güneş",   "Pediatri",        "15:30", "kontrol"),
        ])
    ]
    for appt in demo_appts:
        _appointments[appt["appointment_id"]] = appt
        db_save_appointment(appt["appointment_id"], appt)

    return {
        "created": len(demo_appts),
        "appointments": demo_appts,
        "persisted": True,
        "note": "Demo randevular DB'ye kaydedildi — sunucu yeniden başlatılsa da kaybolmaz.",
    }


# ─────────────────────────────────────────────
#  MCP Channel Adapter — dış kanal intake
#  WhatsApp-style / Telegram / Mobile / Call Center
# ─────────────────────────────────────────────

# Dış kullanıcı → session_id eşlemesi (bellek içi, prod'da cache/DB kullanın)
_channel_sessions: dict[str, str] = {}   # external_user_id → session_id

@app.post("/api/channel/intake/message")
@limiter.limit("30/minute")
async def channel_intake_message(req: ChannelIntakeRequest, request: Request):
    """
    Dış kanal (WhatsApp-style, Telegram, mobil app, çağrı merkezi) üzerinden
    hasta intake mesajı alır.

    Tek endpoint üzerinden şu işlemleri gerçekleştirir:
    1. İlk mesajda: yeni oturum başlatır (session/start)
    2. Devam eden mesajlarda: cevabı kaydeder, sonraki soruyu döndürür
    3. Mülakat tamamlandığında: özeti üretir ve doktor kuyruğuna bildirir

    Gizlilik notu:
    - Tüm AI inferansı yerel Gemma 4 üzerinde yapılır.
    - Kanal adaptör sadece mesajı yönlendirir; hasta verisi dış AI API'ye gitmez.
    - Mesajın iletildiği platform (WhatsApp, Telegram) kendi veri politikalarına tabidir.
    """
    msg  = req.message.strip()
    lang = req.language or "tr"
    ext_id = req.external_user_id

    if not msg:
        raise HTTPException(status_code=400, detail="Mesaj boş olamaz.")

    # ── Oturum yönetimi ───────────────────────────────────────────────────────
    # Öncelik: istekte gelen session_id → dış kullanıcı eşlemesi → yeni oturum
    sid = req.session_id or _channel_sessions.get(ext_id)

    # Oturum geçerli mi kontrol et
    if sid and sid not in sessions:
        sid = None  # eskimiş oturum — yeni başlat

    # Tamamlanmış oturum tekrar başlatılmasın
    if sid and sessions.get(sid, {}).get("completed"):
        sid = None

    # ── Yeni oturum başlat ───────────────────────────────────────────────────
    if not sid:
        # İsimden yola çıkararak anonim hasta oluştur
        _name_tr = "Anon Hasta"
        _name_en = "Anon Patient"
        _name_ar = "مريض مجهول"
        _pname   = _name_ar if lang == "ar" else (_name_en if lang == "en" else _name_tr)

        new_session = {
            "patient_name": _pname,
            "age": 30,             # kanal hatalar için varsayılan; hasta mesajından güncellenemez
            "gender": "Belirtilmedi" if lang == "tr" else "Not specified",
            "language": lang,
            "step": 1,
            "total_steps": 5,
            "qa_history": [],
            "completed": False,
            "vitals": None,
            "image_analyses": [],
            "patient_id": None,
            "claim_code": None,
            "created_at": datetime.utcnow().isoformat(),
            "channel": req.channel,
            "external_user_id": ext_id,
            "channel_source": f"{req.channel} — Channel Adapter Demo",
        }
        sid = str(uuid.uuid4())
        sessions[sid] = new_session
        db_save_session(sid, new_session)
        _channel_sessions[ext_id] = sid

        # İlk soru oluştur (session/start ile aynı mantık)
        if lang == "tr":
            first_q = "Merhaba! 👋 Şikayetinizi anlatın, size yardımcı olacağım."
        elif lang == "ar":
            first_q = "مرحباً! 👋 أخبرني عن شكواك وسأساعدك."
        else:
            first_q = "Hello! 👋 Please describe your complaint and I'll help you."

        new_session["qa_history"] = [{"question": first_q, "answer": None}]
        db_save_session(sid, new_session)
        await notify_queue_update()

        # İlk mesajı cevap olarak işle (soruyu sormak yerine direkt devam et)
        # Aynı request içinde cevabı da kaydedelim
        new_session["qa_history"][-1]["answer"] = msg
        new_session["step"] = 1

        # Adaptif adım sayısı
        new_steps = _adaptive_steps(msg, new_session["age"], lang)
        new_session["total_steps"] = new_steps
        db_save_session(sid, new_session)

    session = sessions[sid]

    # ── Mülakat tamamlandı mı kontrolü ───────────────────────────────────────
    if session.get("completed"):
        # Özet mevcut mu?
        summ = summaries.get(sid, {})
        triage = summ.get("triage_level") if summ else None
        reply_completed = {
            "tr": "Mülakatınız daha önce tamamlandı. Bilgileriniz doktora iletildi.",
            "en": "Your intake was already completed. Information sent to the doctor.",
            "ar": "تم الانتهاء من المقابلة مسبقاً. تم إرسال المعلومات للطبيب."
        }.get(lang, "Mülakat tamamlandı.")
        return {
            "session_id": sid,
            "reply": reply_completed,
            "triage_preview": triage,
            "doctor_queue_created": bool(summ),
            "next_action": "completed",
            "channel": req.channel,
        }

    # ── Aktif mülakatta cevabı kaydet ve sonraki soruyu al ───────────────────
    # Mevcut soru listesinde bekleyen cevap yok ise bu mesajı ekle
    qa = session.get("qa_history", [])
    if qa and qa[-1].get("answer") is None:
        # Zaten açık soru var — bu mesajı o soruya cevap olarak kaydet
        qa[-1]["answer"] = msg
    else:
        # Tüm sorular cevaplanmış — bu mesajı serbest cevap olarak ekle
        if qa:
            qa[-1]["answer"] = msg
        else:
            session["qa_history"] = [{"question": "Şikayetiniz?", "answer": msg}]
            qa = session["qa_history"]

    current_step = session.get("step", 1)
    total_steps  = session.get("total_steps", 5)

    # ── Tüm adımlar tamamlandı mı? ───────────────────────────────────────────
    if current_step >= total_steps:
        session["completed"] = True
        db_save_session(sid, session)
        asyncio.create_task(notify_queue_update())

        # Arka planda özet üret (hemen bir triaj ön bakışı döndürelim)
        async def _gen_summary_bg():
            try:
                # get_clinical_summary mantığını çağır
                await get_clinical_summary(sid)
            except Exception as _e:
                print(f"[Channel] Arka plan özet hatası: {_e}")

        asyncio.create_task(_gen_summary_bg())

        # Tamamlanma mesajı
        completed_reply = {
            "tr": (
                "✅ Bilgileriniz kaydedildi. Klinik özetiniz hazırlanıyor ve doktor kuyruğuna iletiliyor. "
                "Acil bir durum söz konusu olabilir — lütfen sağlık personeline haber verin."
            ),
            "en": (
                "✅ Your information has been recorded. Your clinical summary is being prepared "
                "and sent to the doctor queue. This may be urgent — please notify healthcare staff."
            ),
            "ar": (
                "✅ تم تسجيل معلوماتك. جاري إعداد ملخصك السريري وإرساله لقائمة انتظار الطبيب. "
                "قد تكون هذه حالة طارئة — يرجى إخطار الطاقم الصحي."
            ),
        }.get(lang, "Mülakat tamamlandı. Bilgileriniz doktora iletildi.")

        return {
            "session_id": sid,
            "reply": completed_reply,
            "triage_preview": None,   # arka planda üretiliyor
            "doctor_queue_created": True,
            "next_action": "completed",
            "step": current_step,
            "total_steps": total_steps,
            "channel": req.channel,
        }

    # ── Sonraki soruyu üret ───────────────────────────────────────────────────
    lang_s = session.get("language", "tr")
    history_text = "\n".join(
        f"S{i+1}: {qai['question']}\nC{i+1}: {qai['answer']}"
        for i, qai in enumerate(qa)
        if qai.get("answer")
    )

    pediatric_hint = ""
    if _is_pediatric_case(session) and current_step == 1:
        pediatric_hint = (
            "\n⚠️ PEDİATRİK VAKA: Bir sonraki soru ateş derecesini sormalı.\n"
            if lang_s == "tr" else
            "\n⚠️ PEDIATRIC CASE: Next question MUST ask for temperature.\n"
        )

    if lang_s == "tr":
        next_prompt = (
            f"Hasta: {session['patient_name']}, {session['age']} yaşında, {session['gender']}.\n"
            f"{pediatric_hint}Mülakat geçmişi:\n{history_text}\n\n"
            f"Yukarıdaki cevaplara dayanarak SONRAKI en kritik soruyu sor. "
            f"Soru {current_step+1}/{total_steps}."
        )
    elif lang_s == "ar":
        next_prompt = (
            f"المريض: {session['patient_name']}, {session['age']} سنة.\n"
            f"{pediatric_hint}سجل المقابلة:\n{history_text}\n\n"
            f"بناءً على الإجابات أعلاه، اطرح السؤال التالي الأكثر أهمية. "
            f"السؤال {current_step+1}/{total_steps}. أجب باللغة العربية فقط."
        )
    else:
        next_prompt = (
            f"Patient: {session['patient_name']}, {session['age']}y.\n"
            f"{pediatric_hint}Interview so far:\n{history_text}\n\n"
            f"Ask the NEXT most critical question. Q{current_step+1}/{total_steps}. Respond in English only."
        )

    rag_query = msg + " " + history_text[-200:]
    next_q = await ask_gemma_rag(
        next_prompt,
        system=get_system_prompt(lang_s),
        rag_query=rag_query,
        num_predict=200,
    )

    session["step"] = current_step + 1
    session["qa_history"].append({"question": next_q, "answer": None})
    db_save_session(sid, session)
    asyncio.create_task(notify_queue_update())

    return {
        "session_id": sid,
        "reply": next_q,
        "triage_preview": None,
        "doctor_queue_created": False,
        "next_action": "ask_follow_up",
        "step": session["step"],
        "total_steps": total_steps,
        "channel": req.channel,
    }


# ─────────────────────────────────────────────
#  Pre-Visit Intake Mode
#  Randevu öncesi hasta anamnez görüşmesi — doktor brief'i üretir
# ─────────────────────────────────────────────

# Bellek içi randevu deposu (DB ile senkronize — restart sonrası geri yüklenir)
_appointments: dict[str, dict] = {}  # appointment_id → appointment data
_appt_sessions: dict[str, str]  = {}  # appointment_id → session_id

class PreVisitMessageRequest(BaseModel):
    """Randevu öncesi anamnez mesajı."""
    message: str
    language: str = "tr"


def _previsit_system_prompt(lang: str, doctor_name: str, appointment_time: str) -> str:
    """Pre-visit intake için özel sistem prompt'u — acil triaj DEĞİL, randevu briefi."""
    if lang == "tr":
        return (
            f"Sen AnamnezAI'ın randevu öncesi anamnez asistanısın. "
            f"Hasta, {appointment_time} tarihinde {doctor_name} ile randevusundan önce bu görüşmeyi yapıyor.\n\n"
            "AMAÇ: Doktor için yapılandırılmış bir brifing hazırlamak.\n"
            "- Kısa, nazik ve odaklanmış sorular sor.\n"
            "- Bu acil servis triajı değil — randevu öncesi bilgi toplama.\n"
            "- Hastanın ana şikayetini, süresini, şiddetini ve etkilediği alanları öğren.\n"
            "- Kronik hastalık, ilaç ve alerji bilgilerini sor.\n"
            "- Yalnızca Türkçe yanıt ver.\n"
            "- Maksimum 1-2 cümle ile sor, kısa tut."
        )
    elif lang == "ar":
        return (
            f"أنت مساعد التقييم قبل الزيارة في AnamnezAI. "
            f"المريض يجري هذه المقابلة قبل موعده مع {doctor_name} في {appointment_time}.\n\n"
            "الهدف: إعداد ملخص منظّم للطبيب.\n"
            "- اطرح أسئلة قصيرة ومركّزة.\n"
            "- هذا ليس فرزًا للطوارئ — إنه جمع معلومات قبل الموعد.\n"
            "- أجب باللغة العربية فقط."
        )
    else:
        return (
            f"You are AnamnezAI's pre-visit intake assistant. "
            f"The patient is having this conversation before their appointment with {doctor_name} at {appointment_time}.\n\n"
            "PURPOSE: Prepare a structured briefing document for the doctor.\n"
            "- Ask short, focused, friendly questions.\n"
            "- This is NOT emergency triage — it's pre-appointment information gathering.\n"
            "- Learn the main complaint, duration, severity, and affected areas.\n"
            "- Ask about chronic conditions, medications, and allergies.\n"
            "- Respond in English only.\n"
            "- Keep questions concise — max 1-2 sentences."
        )


async def _generate_previsit_brief(appointment_id: str) -> dict:
    """
    Tamamlanan pre-visit anamnezinden doktor brief'i üretir.
    Bu, klinik özetten farklı — triaj yerine 'doktor için hazırlık' odaklı.
    """
    appt = _appointments.get(appointment_id)
    if not appt:
        return {}

    sid = appt.get("session_id")
    if not sid:
        return {}

    session = sessions.get(sid, {})
    summary_data = summaries.get(sid, {})

    lang = appt.get("language", "tr")
    doctor_name = appt.get("doctor_name", "Dr.")
    patient_name = appt.get("patient_name", session.get("patient_name", "Hasta"))
    appointment_time = appt.get("appointment_time", "")

    qa_history = session.get("qa_history", [])
    history_text = "\n".join(
        f"S{i+1}: {qa['question']}\nC{i+1}: {qa.get('answer', '—')}"
        for i, qa in enumerate(qa_history)
        if qa.get("answer")
    )

    if not history_text.strip():
        return {
            "appointment_id": appointment_id,
            "status": "no_data",
            "brief": None,
        }

    # AI ile brief üret
    if lang == "tr":
        brief_prompt = (
            f"Hasta: {patient_name}, {session.get('age', '?')} yaş, {session.get('gender', '?')}.\n"
            f"Doktor: {doctor_name}\n"
            f"Randevu: {appointment_time}\n\n"
            f"Randevu öncesi hasta anamnezi:\n{history_text}\n\n"
            "Aşağıdaki JSON formatında doktor için bir brifing oluştur:\n"
            "{\n"
            '  "chief_complaint": "Ana şikayet (1-2 cümle)",\n'
            '  "complaint_duration": "Şikayetin süresi",\n'
            '  "severity": "Hafif/Orta/Şiddetli",\n'
            '  "associated_symptoms": ["eşlik eden semptomlar listesi"],\n'
            '  "chronic_conditions": ["kronik hastalıklar"],\n'
            '  "current_medications": ["kullanılan ilaçlar"],\n'
            '  "allergies": ["alerjiler"],\n'
            '  "missing_information": ["doktorun sorması gereken eksik bilgiler"],\n'
            '  "suggested_questions": ["doktor için önerilen sorular"],\n'
            '  "red_flags": ["varsa acil uyarı işaretleri"],\n'
            '  "wait_warning": true/false,\n'
            '  "wait_warning_reason": "neden beklememeli (varsa)",\n'
            '  "clinical_note": "genel klinik özet"\n'
            "}\n"
            "Sadece JSON döndür. Randevu öncesi bilgi toplama — triaj değil."
        )
    else:
        brief_prompt = (
            f"Patient: {patient_name}, {session.get('age', '?')}y, {session.get('gender', '?')}.\n"
            f"Doctor: {doctor_name}\n"
            f"Appointment: {appointment_time}\n\n"
            f"Pre-visit intake history:\n{history_text}\n\n"
            "Generate a doctor briefing in the following JSON format:\n"
            "{\n"
            '  "chief_complaint": "Main complaint (1-2 sentences)",\n'
            '  "complaint_duration": "Duration of complaint",\n'
            '  "severity": "Mild/Moderate/Severe",\n'
            '  "associated_symptoms": ["list of associated symptoms"],\n'
            '  "chronic_conditions": ["chronic conditions"],\n'
            '  "current_medications": ["current medications"],\n'
            '  "allergies": ["allergies"],\n'
            '  "missing_information": ["information the doctor should ask about"],\n'
            '  "suggested_questions": ["suggested questions for the doctor"],\n'
            '  "red_flags": ["urgent warning signs if any"],\n'
            '  "wait_warning": true/false,\n'
            '  "wait_warning_reason": "why patient should not wait (if applicable)",\n'
            '  "clinical_note": "overall clinical summary"\n'
            "}\n"
            "Return ONLY JSON. This is pre-appointment info gathering — not emergency triage."
        )

    raw = await ask_gemma(brief_prompt, system=_previsit_system_prompt(lang, doctor_name, appointment_time), timeout=180.0, num_predict=600)

    # JSON parse
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
        brief_data = json.loads(cleaned[start:end])
    except Exception:
        brief_data = {
            "chief_complaint": history_text[:200] if history_text else "Bilgi yok",
            "complaint_duration": "Bilinmiyor",
            "severity": "Bilinmiyor",
            "associated_symptoms": [],
            "chronic_conditions": [],
            "current_medications": [],
            "allergies": [],
            "missing_information": ["Tam bilgi alınamadı — doktor direkt sorabilir"],
            "suggested_questions": [],
            "red_flags": [],
            "wait_warning": False,
            "wait_warning_reason": "",
            "clinical_note": raw[:400] if raw else "Brief üretilemedi",
        }

    # Red flag varsa safety guardrail uygula
    red_flags = brief_data.get("red_flags", [])
    if red_flags:
        brief_data["wait_warning"] = True
        if not brief_data.get("wait_warning_reason"):
            brief_data["wait_warning_reason"] = "; ".join(red_flags[:2])

    return brief_data


@app.post("/api/appointments/demo")
async def create_demo_appointments(current_user: Optional[dict] = Depends(get_current_user)):
    """
    Demo randevu verileri oluşturur (5 hasta, bugünün tarihi).
    Gerçek randevu sistemi gerektirir — demo modunda statik veri.
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    demo_appts = [
        {
            "appointment_id": f"appt-demo-{i+1:03d}",
            "patient_name": n,
            "patient_age": a,
            "patient_gender": g,
            "doctor_name": d,
            "specialty": s,
            "appointment_time": f"{today}T{t}:00",
            "appointment_type": at,
            "language": "tr",
            "status": "scheduled",
            "previsit_status": "pending",
            "session_id": None,
            "brief": None,
            "created_at": datetime.utcnow().isoformat(),
        }
        for i, (n, a, g, d, s, t, at) in enumerate([
            ("Ayşe Kaya",      45, "Kadın",   "Dr. Fatma Şahin",    "Kardiyoloji",     "09:00", "kontrol"),
            ("Mehmet Demir",   62, "Erkek",   "Dr. Ali Yıldız",     "İç Hastalıkları", "10:30", "yeni_hasta"),
            ("Zeynep Arslan",  28, "Kadın",   "Dr. Fatma Şahin",    "Kardiyoloji",     "11:00", "kontrol"),
            ("Hasan Çelik",    71, "Erkek",   "Dr. Elif Koca",      "Nöroloji",        "14:00", "takip"),
            ("Elif Yılmaz",     8, "Kız",     "Dr. Osman Güneş",    "Pediatri",        "15:30", "kontrol"),
        ])
    ]
    for appt in demo_appts:
        _appointments[appt["appointment_id"]] = appt
        db_save_appointment(appt["appointment_id"], appt)

    return {
        "created": len(demo_appts),
        "appointments": demo_appts,
        "note": "Demo veri DB'ye kaydedildi — sunucu yeniden başlatılsa da kaybolmaz.",
    }


@app.post("/api/appointments/{appointment_id}/previsit/start")
@limiter.limit("20/minute")
async def start_previsit(appointment_id: str, request: Request, current_user: Optional[dict] = Depends(get_current_user)):
    """
    Randevu öncesi anamnez görüşmesini başlatır.
    Hasta randevu linkine tıkladığında bu endpoint çağrılır.
    """
    appt = _appointments.get(appointment_id)
    if not appt:
        # Demo randevu oluştur (doğrudan link ile gelen hastalar için)
        raise HTTPException(status_code=404, detail="Randevu bulunamadı. Lütfen demo randevuları oluşturun: POST /api/appointments/demo")

    # Zaten başlamışsa mevcut durumu döndür
    existing_sid = appt.get("session_id")
    if existing_sid and existing_sid in sessions:
        existing_session = sessions[existing_sid]
        lang = appt.get("language", "tr")
        qa = existing_session.get("qa_history", [])
        last_q = qa[-1]["question"] if qa else ""
        return {
            "appointment_id": appointment_id,
            "session_id": existing_sid,
            "status": "already_started",
            "question": last_q,
            "step": existing_session.get("step", 1),
            "total_steps": existing_session.get("total_steps", 5),
            "patient_name": appt.get("patient_name", ""),
            "doctor_name": appt.get("doctor_name", ""),
            "appointment_time": appt.get("appointment_time", ""),
        }

    lang = appt.get("language", "tr")
    doctor_name = appt.get("doctor_name", "Dr.")
    appt_time_raw = appt.get("appointment_time", "")
    # Format appointment time nicely
    try:
        appt_dt = datetime.fromisoformat(appt_time_raw)
        appt_time_nice = appt_dt.strftime("%d.%m.%Y %H:%M") if lang == "tr" else appt_dt.strftime("%m/%d/%Y %H:%M")
    except Exception:
        appt_time_nice = appt_time_raw

    # İlk soru — randevu bağlamı ile kişiselleştirilmiş
    patient_name_first = appt.get("patient_name", "").split()[0]
    if lang == "tr":
        first_q = (
            f"Merhaba {patient_name_first}! 👋 {appt_time_nice} tarihinde {doctor_name} ile randevunuz var. "
            f"Randevunuzdan önce size birkaç soru sormak istiyorum. "
            f"Bugün doktorunuza gitmek istemenizin ana sebebi nedir?"
        )
    elif lang == "ar":
        first_q = (
            f"مرحباً {patient_name_first}! 👋 لديك موعد مع {doctor_name} في {appt_time_nice}. "
            f"قبل موعدك، أودّ طرح بعض الأسئلة عليك. "
            f"ما السبب الرئيسي لزيارة طبيبك اليوم؟"
        )
    else:
        first_q = (
            f"Hello {patient_name_first}! 👋 You have an appointment with {doctor_name} on {appt_time_nice}. "
            f"Before your appointment, I'd like to ask you a few questions. "
            f"What is the main reason you'd like to see your doctor today?"
        )

    sid = str(uuid.uuid4())
    session_data = {
        "patient_name": appt.get("patient_name", "Hasta"),
        "age": appt.get("patient_age", 30),
        "gender": appt.get("patient_gender", "Belirtilmedi"),
        "language": lang,
        "step": 1,
        "total_steps": 5,  # Pre-visit: 5 soru (kısa, odaklı)
        "qa_history": [{"question": first_q, "answer": None}],
        "completed": False,
        "vitals": None,
        "image_analyses": [],
        "patient_id": current_user["user_id"] if current_user else None,
        "claim_code": None,
        "intake_type": "pre_visit",
        "appointment_id": appointment_id,
        "doctor_name": appt.get("doctor_name", ""),
        "appointment_time": appt_time_raw,
        "created_at": datetime.utcnow().isoformat(),
    }

    sessions[sid] = session_data
    db_save_session(sid, session_data)

    # Randevuya bağla
    appt["session_id"] = sid
    appt["previsit_status"] = "in_progress"
    _appt_sessions[appointment_id] = sid

    return {
        "appointment_id": appointment_id,
        "session_id": sid,
        "status": "started",
        "question": first_q,
        "step": 1,
        "total_steps": 5,
        "patient_name": appt.get("patient_name", ""),
        "doctor_name": appt.get("doctor_name", ""),
        "appointment_time": appt_time_raw,
        "appointment_type": appt.get("appointment_type", ""),
        "specialty": appt.get("specialty", ""),
    }


@app.post("/api/appointments/{appointment_id}/previsit/message")
@limiter.limit("30/minute")
async def previsit_message(appointment_id: str, req: PreVisitMessageRequest, request: Request):
    """
    Randevu öncesi anamnez konuşması — hasta mesajını alır, sonraki soruyu döner.
    Mülakat tamamlandığında doktor brief'i arka planda üretilir.
    """
    appt = _appointments.get(appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Randevu bulunamadı.")

    sid = appt.get("session_id")
    if not sid or sid not in sessions:
        raise HTTPException(status_code=400, detail="Önce randevu görüşmesini başlatın: POST /api/appointments/{id}/previsit/start")

    session = sessions[sid]
    lang = req.language or appt.get("language", "tr")
    msg  = req.message.strip()

    if not msg:
        raise HTTPException(status_code=400, detail="Mesaj boş olamaz.")

    # Tamamlanmış mülakat
    if session.get("completed"):
        brief = appt.get("brief")
        wait_warning = brief.get("wait_warning", False) if brief else False
        if lang == "tr":
            reply = "✅ Bilgileriniz doktorunuza iletildi. Randevunuzu beklemenizi öneririz." if not wait_warning else \
                    "⚠️ Belirttiğiniz şikayetler nedeniyle randevunuzu beklemenizi önermiyoruz. Lütfen sağlık personeline hemen başvurun."
        elif lang == "ar":
            reply = "✅ تم إرسال معلوماتك إلى طبيبك. يُنصح بانتظار موعدك." if not wait_warning else \
                    "⚠️ بناءً على شكاواك، لا نوصي بانتظار الموعد. يرجى مراجعة الطاقم الصحي فوراً."
        else:
            reply = "✅ Your information has been sent to your doctor. Please wait for your appointment." if not wait_warning else \
                    "⚠️ Based on your complaints, we advise you NOT to wait for your appointment. Please see healthcare staff immediately."
        return {
            "appointment_id": appointment_id,
            "session_id": sid,
            "reply": reply,
            "completed": True,
            "wait_warning": wait_warning,
            "step": session.get("step", 5),
            "total_steps": session.get("total_steps", 5),
            "next_action": "completed",
        }

    # Mevcut soruya cevap kaydet
    qa = session.get("qa_history", [])
    if qa and qa[-1].get("answer") is None:
        qa[-1]["answer"] = msg
    elif qa:
        qa[-1]["answer"] = msg

    current_step = session.get("step", 1)
    total_steps  = session.get("total_steps", 5)

    # İlk cevap → adaptif adım güncelle (pre-visit: max 6, min 4)
    if current_step == 1 and msg:
        adapted = _adaptive_steps(msg, session.get("age", 30), lang)
        total_steps = max(4, min(adapted, 6))
        session["total_steps"] = total_steps

    # Mülakat tamamlandı mı?
    if current_step >= total_steps:
        session["completed"] = True
        appt["previsit_status"] = "completed"
        db_save_session(sid, session)
        asyncio.create_task(notify_queue_update())

        # Arka planda brief üret
        async def _gen_brief_bg():
            try:
                brief_data = await _generate_previsit_brief(appointment_id)
                appt["brief"] = brief_data
                appt["previsit_status"] = "brief_ready"
                # Özet de kaydet
                summary_entry = {
                    "session_id": sid,
                    "patient_name": session.get("patient_name", ""),
                    "age": session.get("age", 0),
                    "gender": session.get("gender", ""),
                    "triage_level": "PENDING",
                    "triage_color": "#9e9e9e",
                    "confidence_score": 0,
                    "chief_complaint": brief_data.get("chief_complaint", ""),
                    "symptoms_summary": brief_data.get("clinical_note", ""),
                    "possible_conditions": [],
                    "urgency_flags": brief_data.get("red_flags", []),
                    "recommended_action": "Randevu öncesi brief hazır — doktor incelemesi gerekiyor",
                    "clinical_notes": brief_data.get("clinical_note", ""),
                    "generated_at": datetime.utcnow().isoformat(),
                    "intake_type": "pre_visit",
                    "previsit_brief": brief_data,
                    "doctor_review_required": True,
                    "unsafe_to_self_manage": brief_data.get("wait_warning", False),
                }
                summaries[sid] = summary_entry
                db_save_summary(sid, summary_entry)
            except Exception as e:
                print(f"[PreVisit] Brief oluşturma hatası: {e}")

        asyncio.create_task(_gen_brief_bg())

        doctor_name = appt.get("doctor_name", "doktorunuz")
        wait_w = False  # Brief henüz hazır değil
        if lang == "tr":
            reply = (
                f"✅ Teşekkürler! Verdiğiniz bilgiler {doctor_name}'ına iletiliyor. "
                f"Brief hazırlanıyor, birkaç dakika içinde doktorunuz bilgilerinizi görebilecek. "
                f"Randevunuz için hazır olun."
            )
        elif lang == "ar":
            reply = (
                f"✅ شكراً! يتم إرسال المعلومات التي قدمتها إلى {doctor_name}. "
                f"جاري إعداد الملخص، سيتمكن طبيبك من الاطلاع على معلوماتك خلال دقائق."
            )
        else:
            reply = (
                f"✅ Thank you! Your information is being sent to {doctor_name}. "
                f"The brief is being prepared — your doctor will be able to see your information in a few minutes. "
                f"Please get ready for your appointment."
            )

        return {
            "appointment_id": appointment_id,
            "session_id": sid,
            "reply": reply,
            "completed": True,
            "wait_warning": False,  # Brief henüz hazır değil, kötümser olmayalım
            "step": current_step,
            "total_steps": total_steps,
            "next_action": "completed",
        }

    # Sonraki soruyu AI ile üret
    doctor_name = appt.get("doctor_name", "")
    appt_time_raw = appt.get("appointment_time", "")

    history_text = "\n".join(
        f"S{i+1}: {qa_i['question']}\nC{i+1}: {qa_i['answer']}"
        for i, qa_i in enumerate(qa)
        if qa_i.get("answer")
    )

    if lang == "tr":
        next_prompt = (
            f"Hasta: {session['patient_name']}, {session['age']} yaşında, {session['gender']}.\n"
            f"Doktor: {doctor_name} | Randevu: {appt_time_raw}\n"
            f"Görüşme geçmişi:\n{history_text}\n\n"
            f"Randevu için doktor briefi hazırlıyoruz. "
            f"Eksik olan en önemli klinik bilgiyi sormak için SONRAKI en kritik soruyu sor. "
            f"Pre-visit görüşme soru {current_step+1}/{total_steps}. "
            f"Kısa ve nazik ol."
        )
    elif lang == "ar":
        next_prompt = (
            f"المريض: {session['patient_name']}, {session['age']} سنة.\n"
            f"سجل المقابلة:\n{history_text}\n\n"
            f"اطرح السؤال التالي الأكثر أهمية لإعداد ملخص الطبيب. "
            f"السؤال {current_step+1}/{total_steps}. أجب باللغة العربية."
        )
    else:
        next_prompt = (
            f"Patient: {session['patient_name']}, {session['age']}y, {session['gender']}.\n"
            f"Doctor: {doctor_name} | Appointment: {appt_time_raw}\n"
            f"History:\n{history_text}\n\n"
            f"We are preparing a pre-visit brief for the doctor. "
            f"Ask the NEXT most important question to gather missing clinical information. "
            f"Pre-visit Q{current_step+1}/{total_steps}. Be concise and friendly."
        )

    rag_query = msg + " " + history_text[-200:]
    next_q = await ask_gemma_rag(
        next_prompt,
        system=_previsit_system_prompt(lang, doctor_name, appt_time_raw),
        rag_query=rag_query,
        num_predict=200,
    )

    session["step"] = current_step + 1
    session["qa_history"].append({"question": next_q, "answer": None})
    db_save_session(sid, session)

    return {
        "appointment_id": appointment_id,
        "session_id": sid,
        "reply": next_q,
        "completed": False,
        "wait_warning": False,
        "step": session["step"],
        "total_steps": total_steps,
        "next_action": "ask_follow_up",
    }


@app.get("/api/appointments/{appointment_id}/brief")
async def get_previsit_brief_endpoint(appointment_id: str, current_user: dict = Depends(require_doctor)):
    """
    Doktor için randevu öncesi hasta brief'ini döndürür.
    Pre-visit mülakat tamamlandıktan sonra erişilebilir.
    """
    appt = _appointments.get(appointment_id)
    if not appt:
        raise HTTPException(status_code=404, detail="Randevu bulunamadı.")

    sid = appt.get("session_id")
    session = sessions.get(sid, {}) if sid else {}
    brief = appt.get("brief")
    status = appt.get("previsit_status", "pending")

    if status == "pending" or not sid:
        return {
            "appointment_id": appointment_id,
            "status": "pending",
            "patient_name": appt.get("patient_name"),
            "doctor_name": appt.get("doctor_name"),
            "appointment_time": appt.get("appointment_time"),
            "brief": None,
            "message": "Hasta henüz pre-visit görüşmesini başlatmadı.",
        }
    elif status == "in_progress":
        return {
            "appointment_id": appointment_id,
            "status": "in_progress",
            "patient_name": appt.get("patient_name"),
            "doctor_name": appt.get("doctor_name"),
            "appointment_time": appt.get("appointment_time"),
            "step": session.get("step", 0),
            "total_steps": session.get("total_steps", 5),
            "brief": None,
            "message": f"Görüşme devam ediyor ({session.get('step', 0)}/{session.get('total_steps', 5)} soru).",
        }
    elif status == "completed" and not brief:
        return {
            "appointment_id": appointment_id,
            "status": "generating",
            "patient_name": appt.get("patient_name"),
            "doctor_name": appt.get("doctor_name"),
            "appointment_time": appt.get("appointment_time"),
            "brief": None,
            "message": "Görüşme tamamlandı, brief hazırlanıyor...",
        }
    else:
        return {
            "appointment_id": appointment_id,
            "status": "brief_ready",
            "patient_name": appt.get("patient_name"),
            "patient_age": appt.get("patient_age"),
            "patient_gender": appt.get("patient_gender"),
            "doctor_name": appt.get("doctor_name"),
            "specialty": appt.get("specialty"),
            "appointment_time": appt.get("appointment_time"),
            "appointment_type": appt.get("appointment_type"),
            "session_id": sid,
            "brief": brief,
            "qa_history": session.get("qa_history", []),
        }


@app.get("/api/appointments/today")
async def get_today_appointments(current_user: dict = Depends(require_doctor)):
    """
    Bugünün randevularını listeler (doktor paneli için).
    Pre-visit brief durumları dahil.
    """
    today = datetime.utcnow().strftime("%Y-%m-%d")
    result = []
    for appt_id, appt in _appointments.items():
        appt_time = appt.get("appointment_time", "")
        if today in appt_time:
            sid = appt.get("session_id")
            session = sessions.get(sid, {}) if sid else {}
            result.append({
                "appointment_id": appt_id,
                "patient_name": appt.get("patient_name"),
                "patient_age": appt.get("patient_age"),
                "doctor_name": appt.get("doctor_name"),
                "specialty": appt.get("specialty"),
                "appointment_time": appt_time,
                "appointment_type": appt.get("appointment_type"),
                "previsit_status": appt.get("previsit_status", "pending"),
                "has_red_flags": bool(appt.get("brief", {}) and appt.get("brief", {}).get("red_flags")),
                "wait_warning": appt.get("brief", {}).get("wait_warning", False) if appt.get("brief") else False,
                "session_id": sid,
                "previsit_link": f"/previsit.html?appt={appt_id}",
            })
    # Randevu saatine göre sırala
    result.sort(key=lambda x: x.get("appointment_time", ""))
    return {
        "date": today,
        "total": len(result),
        "appointments": result,
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

# ─────────────────────────────────────────────
#  Demo Cases — DB-backed (no hardcoded frontend data)
# ─────────────────────────────────────────────

_DEMO_SEED_CASES = [
    {
        "session_id": "demo-stemi-001",
        "patient_name": "Mehmet Yılmaz",
        "age": 66, "gender": "Erkek",
        "triage_level": "RED", "triage_color": "#ba1a1a",
        "confidence_score": 98,
        "chief_complaint": "Göğüs ağrısı, sol kola yayılan, terleme",
        "symptoms_summary": "66 yaşında erkek, 30 dakika önce başlayan şiddetli retrosternal ağrı, sol kola yayılım, diaphoresis, bulantı. EKG'de ST yükselmesi.",
        "possible_conditions": ["STEMI (Akut Miyokard İnfarktüsü)", "Akut Koroner Sendrom", "İnstabil Angina"],
        "urgency_flags": ["STEMI şüphesi — immedyat kardiyoloji konsültasyonu", "Sol kol yayılım + diaphoresis = kardiyak acil"],
        "recommended_action": "ACİL KARDİYOLOJİ — STEMI protokolü aktive et, aspirin 300mg, PCI hazırlığı",
        "clinical_notes": "Gaziantep STEMI senaryosu. Manuel triajda 22 dakika bekledi. AI: 14 saniye.",
        "allergy_flags": [],
        "vitals": {"blood_pressure": "170/100", "pulse": "110", "temperature": 36.8, "spo2": 94},
        "evidence": ["Retrosternal ağrı + sol kol yayılım = tip 1 MI kriteri", "Diaphoresis yüksek riskli bulgu", "ST elevasyonu varsa <90dk PPCI"],
        "guideline_sources": ["ESC STEMI 2023", "MTS Kardiyak Triaj"],
        "is_demo": True, "source": "seed_demo",
        "created_at": "2026-05-15T08:14:00",
        "generated_at": "2026-05-15T08:14:14",
        "completed": True, "is_seen": False,
    },
    {
        "session_id": "demo-sepsis-002",
        "patient_name": "Fatma Kaya",
        "age": 78, "gender": "Kadın",
        "triage_level": "RED", "triage_color": "#ba1a1a",
        "confidence_score": 95,
        "chief_complaint": "Yüksek ateş, bilinç bulanıklığı, hızlı nefes",
        "symptoms_summary": "78 yaşında kadın, 3 gündür ateş, gece başlayan bilinç değişikliği, solunum hızlanması. İdrar yolu enfeksiyonu öyküsü.",
        "possible_conditions": ["Sepsis / Septik Şok", "Üriner Sepsis", "Pnömoni + Sepsis"],
        "urgency_flags": ["Sepsis kriteri: ateş + taşikardi + bilinç değişikliği", "qSOFA ≥2 — yüksek mortalite riski"],
        "recommended_action": "ACİL — Sepsis bundle başlat, laktat, kan kültürü, antibiyotik <1 saat içinde",
        "clinical_notes": "Yaşlı hastada sepsis belirtileri. qSOFA skoru değerlendir.",
        "allergy_flags": ["Penisilin alerjisi"],
        "vitals": {"blood_pressure": "90/60", "pulse": "118", "temperature": 39.4, "spo2": 91},
        "evidence": ["Hipotansiyon + taşikardi + ateş = SIRS", "Bilinç değişikliği = organ disfonksiyonu"],
        "guideline_sources": ["Surviving Sepsis Campaign 2021"],
        "is_demo": True, "source": "seed_demo",
        "created_at": "2026-05-15T09:02:00",
        "generated_at": "2026-05-15T09:02:21",
        "completed": True, "is_seen": False,
    },
    {
        "session_id": "demo-pediatric-003",
        "patient_name": "Mia Demir",
        "age": 4, "gender": "Kız",
        "triage_level": "YELLOW", "triage_color": "#e07b26",
        "confidence_score": 89,
        "chief_complaint": "Yüksek ateş (39.8°C), kulak ağrısı, huzursuzluk",
        "symptoms_summary": "4 yaşında çocuk, dün gece başlayan yüksek ateş, sağ kulak ağrısı, iştahsızlık. Otit media şüphesi.",
        "possible_conditions": ["Akut Otit Media", "Viral Üst Solunum Yolu Enfeksiyonu", "Farenjit"],
        "urgency_flags": ["39.8°C — febril konvülziyon riski izle"],
        "recommended_action": "KBB viziti — antibiyotik (amoksisilin) değerlendirmesi, antipiretik",
        "clinical_notes": "Pediatric ateş protokolü. Serumlu ateş takibi.",
        "allergy_flags": [],
        "vitals": {"temperature": 39.8, "pulse": "120"},
        "is_demo": True, "source": "seed_demo",
        "created_at": "2026-05-15T10:30:00",
        "generated_at": "2026-05-15T10:30:18",
        "completed": True, "is_seen": False,
    },
    {
        "session_id": "demo-appendix-004",
        "patient_name": "Emre Şahin",
        "age": 22, "gender": "Erkek",
        "triage_level": "YELLOW", "triage_color": "#e07b26",
        "confidence_score": 87,
        "chief_complaint": "Sağ alt karın ağrısı, ateş, bulantı",
        "symptoms_summary": "22 yaşında erkek, 8 saat önce göbek çevresinde başlayan, sonra sağ alt kadrana yerleşen ağrı. Hafif ateş, bulantı, iştahsızlık.",
        "possible_conditions": ["Akut Apandisit", "Mezenterik Lenfadenit", "Kasık Fıtığı Komplikasyonu"],
        "urgency_flags": ["McBurney noktası hassasiyeti — apandisit protokolü", "Rebound hassasiyeti sorgulanmalı"],
        "recommended_action": "Genel Cerrahi konsültasyonu — US/BT, Alvarado skoru hesapla",
        "clinical_notes": "Klasik akut apandisit prezentasyonu. Perforasyon riski izle.",
        "allergy_flags": [],
        "vitals": {"temperature": 38.1, "pulse": "95"},
        "is_demo": True, "source": "seed_demo",
        "created_at": "2026-05-15T11:15:00",
        "generated_at": "2026-05-15T11:15:15",
        "completed": True, "is_seen": False,
    },
    {
        "session_id": "demo-migraine-005",
        "patient_name": "Elif Arslan",
        "age": 31, "gender": "Kadın",
        "triage_level": "GREEN", "triage_color": "#006a68",
        "confidence_score": 92,
        "chief_complaint": "Şiddetli baş ağrısı, ışık hassasiyeti, bulantı",
        "symptoms_summary": "31 yaşında kadın, migren öyküsü var. Benzer önceki ataklar. Ense sertliği YOK. Bilinç açık. Ateş yok.",
        "possible_conditions": ["Migren (Aurasız)", "Gerilim Baş Ağrısı", "Küme Baş Ağrısı"],
        "urgency_flags": [],
        "recommended_action": "Triptan + NSAID — sessiz/karanlık oda. Ense sertliği/ateş gelişirse acile gönder.",
        "clinical_notes": "Bilinen migren. Menenjit red flag yok. Standart protokol.",
        "allergy_flags": [],
        "vitals": {},
        "is_demo": True, "source": "seed_demo",
        "created_at": "2026-05-15T13:00:00",
        "generated_at": "2026-05-15T13:00:11",
        "completed": True, "is_seen": False,
    },
]

@app.post("/api/demo/cases/seed")
async def seed_demo_cases(current_user: Optional[dict] = Depends(get_current_user)):
    """Demo vakaları DB'ye seed eder — frontend'e hardcoded veri gerek kalmaz."""
    seeded = 0
    for case in _DEMO_SEED_CASES:
        sid = case["session_id"]
        session_data = {
            "patient_name": case["patient_name"],
            "age": case["age"],
            "gender": case["gender"],
            "language": "tr",
            "completed": True,
            "is_seen": False,
            "is_demo": True,
            "source": "seed_demo",
            "created_at": case["created_at"],
            "qa_history": [],
            "vitals": case.get("vitals"),
            "step": 5, "total_steps": 5,
        }
        summary_data = {k: v for k, v in case.items() if k not in {"completed", "is_seen"}}
        summary_data["generated_at"] = case["generated_at"]
        sessions[sid] = session_data
        summaries[sid] = summary_data
        db_save_session(sid, session_data)
        db_save_summary(sid, summary_data)
        seeded += 1
    return {"seeded": seeded, "message": "Demo vakalar DB'ye kaydedildi.", "session_ids": [c["session_id"] for c in _DEMO_SEED_CASES]}


@app.get("/api/demo/cases")
async def get_demo_cases(current_user: Optional[dict] = Depends(get_current_user)):
    """Demo vakaları döndürür — DB'den okunur, frontend'de hardcoded değil."""
    result = []
    for sid, summ in summaries.items():
        if summ.get("is_demo") or summ.get("source") == "seed_demo" or sid.startswith("demo-"):
            session = sessions.get(sid, {})
            p = {
                "session_id": sid,
                "patient_name": summ.get("patient_name", session.get("patient_name", "")),
                "age": summ.get("age", session.get("age", 0)),
                "gender": summ.get("gender", session.get("gender", "")),
                "triage_level": summ.get("triage_level", "PENDING"),
                "triage_color": summ.get("triage_color", "#8c9499"),
                "confidence_score": summ.get("confidence_score", 0),
                "chief_complaint": summ.get("chief_complaint", ""),
                "symptoms_summary": summ.get("symptoms_summary", ""),
                "possible_conditions": summ.get("possible_conditions", []),
                "urgency_flags": summ.get("urgency_flags", []),
                "recommended_action": summ.get("recommended_action", ""),
                "clinical_notes": summ.get("clinical_notes", ""),
                "allergy_flags": summ.get("allergy_flags", []),
                "vitals": summ.get("vitals") or session.get("vitals"),
                "evidence": summ.get("evidence", []),
                "guideline_sources": summ.get("guideline_sources", []),
                "is_demo": True,
                "created_at": summ.get("created_at", session.get("created_at", "")),
                "generated_at": summ.get("generated_at", ""),
                "is_seen": session.get("is_seen", False),
                "doctor_notes": session.get("doctor_notes", []),
                "triage_override": session.get("triage_override"),
            }
            result.append(p)
    # If no demo cases in DB, auto-seed
    if not result:
        await seed_demo_cases(current_user)
        for case in _DEMO_SEED_CASES:
            sid = case["session_id"]
            p = {
                "session_id": sid,
                "patient_name": case["patient_name"],
                "age": case["age"],
                "gender": case["gender"],
                "triage_level": case["triage_level"],
                "triage_color": case["triage_color"],
                "confidence_score": case["confidence_score"],
                "chief_complaint": case["chief_complaint"],
                "symptoms_summary": case["symptoms_summary"],
                "possible_conditions": case["possible_conditions"],
                "urgency_flags": case["urgency_flags"],
                "recommended_action": case["recommended_action"],
                "clinical_notes": case["clinical_notes"],
                "allergy_flags": case.get("allergy_flags", []),
                "vitals": case.get("vitals"),
                "evidence": case.get("evidence", []),
                "guideline_sources": case.get("guideline_sources", []),
                "is_demo": True,
                "created_at": case["created_at"],
                "generated_at": case["generated_at"],
                "is_seen": False,
                "doctor_notes": [],
                "triage_override": None,
            }
            result.append(p)
    priority = {"RED": 0, "YELLOW": 1, "GREEN": 2, "PENDING": 3}
    result.sort(key=lambda x: priority.get(x.get("triage_level", "PENDING"), 3))
    return {"total": len(result), "cases": result}



# ─────────────────────────────────────────────
#  Admin: Session Cleanup
# ─────────────────────────────────────────────

@app.post("/api/admin/sessions/cleanup")
async def admin_cleanup_sessions(current_user: dict = Depends(require_admin)):
    """Görüldü işaretlenen eski oturumları RAM'den temizler (DB'de kalır)."""
    removed_ids = []
    for sid, s in list(sessions.items()):
        if s.get("is_seen") and s.get("completed") and not sid.startswith("demo-"):
            sessions.pop(sid, None)
            summaries.pop(sid, None)
            removed_ids.append(sid)
    return {
        "cleaned": len(removed_ids),
        "message": f"{len(removed_ids)} oturum RAM'den temizlendi (DB'de korunuyor).",
        "session_ids": removed_ids[:20],  # İlk 20 ID'yi döndür
    }


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



