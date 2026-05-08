"""
AnamnezAI — Backend v4.0
AI-Powered Patient Pre-Triage using Gemma 4 via Ollama
Gemma 4 Good Hackathon — Health & Sciences + Ollama Prize Tracks
v4.0: SQLite kalıcılık + Multimodal görüntü analizi + Gerçek zamanlı SSE kuyruğu + Vital bulgular
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import AsyncGenerator, Optional
import httpx
import json
import uuid
import os
import tempfile
import sqlite3
import threading
import asyncio
import base64
from datetime import datetime

# ─────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
GEMMA_MODEL     = os.getenv("GEMMA_MODEL", "gemma4:e4b")
RAG_ENABLED     = os.getenv("RAG_ENABLED", "true").lower() == "true"
DB_PATH         = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "anamnezai.db"))

app = FastAPI(
    title="AnamnezAI",
    description="AI-Powered Patient Pre-Triage — Gemma 4 + RAG + Vision | Gemma 4 Good Hackathon",
    version="4.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage (synced to SQLite)
sessions:  dict[str, dict] = {}
summaries: dict[str, dict] = {}

# SSE subscribers for real-time queue
_queue_subscribers: list[asyncio.Queue] = []

# ─────────────────────────────────────────────
#  SQLite Persistence
# ─────────────────────────────────────────────
_db_lock = threading.Lock()

def init_db():
    """SQLite veritabanını başlatır ve tabloları oluşturur."""
    with _db_lock:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS summaries (
                    session_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()

def db_save_session(session_id: str, data: dict):
    """Oturumu SQLite'a kaydeder (INSERT OR REPLACE)."""
    with _db_lock:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO sessions (session_id, data, created_at) VALUES (?, ?, ?)",
                    (session_id, json.dumps(data, ensure_ascii=False),
                     data.get("created_at", datetime.utcnow().isoformat()))
                )
                conn.commit()
        except Exception as e:
            print(f"[DB] Session save error: {e}")

def db_save_summary(session_id: str, data: dict):
    """Klinik özeti SQLite'a kaydeder."""
    with _db_lock:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO summaries (session_id, data, created_at) VALUES (?, ?, ?)",
                    (session_id, json.dumps(data, ensure_ascii=False),
                     data.get("generated_at", datetime.utcnow().isoformat()))
                )
                conn.commit()
        except Exception as e:
            print(f"[DB] Summary save error: {e}")

def db_delete_session(session_id: str):
    """Oturumu ve özetini SQLite'tan siler."""
    with _db_lock:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
                conn.execute("DELETE FROM summaries WHERE session_id=?", (session_id,))
                conn.commit()
        except Exception as e:
            print(f"[DB] Delete error: {e}")

def db_load_all():
    """Tüm oturum ve özetleri SQLite'tan belleğe yükler."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            for sid, data_str in conn.execute("SELECT session_id, data FROM sessions").fetchall():
                try:
                    sessions[sid] = json.loads(data_str)
                except Exception:
                    pass
            for sid, data_str in conn.execute("SELECT session_id, data FROM summaries").fetchall():
                try:
                    summaries[sid] = json.loads(data_str)
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

# ─────────────────────────────────────────────
#  Ollama /api/chat Helpers
# ─────────────────────────────────────────────
async def ask_gemma(prompt: str, system: str = "", timeout: float = 180.0) -> str:
    """Ollama /api/chat üzerinden Gemma 4'e metin isteği gönderir."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": GEMMA_MODEL,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.25,
                        "top_p": 0.85,
                        "top_k": 40,
                        "num_predict": 512,
                        "repeat_penalty": 1.1,
                    },
                },
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"].strip()
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Ollama çalışmıyor. Terminal'de: ollama serve")
    except httpx.ReadTimeout:
        raise HTTPException(status_code=504, detail=f"Gemma 4 yanıt vermedi (timeout {int(timeout)}sn). Model yükleniyor olabilir.")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Bağlantı zaman aşımı. Ollama servisini kontrol edin.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemma 4 hatası: {str(e)}")


async def ask_gemma_vision(prompt: str, image_base64: str, system: str = "", timeout: float = 180.0) -> str:
    """Gemma 4 multimodal — görüntü + metin analizi (Ollama vision API)."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({
        "role": "user",
        "content": prompt,
        "images": [image_base64],  # Ollama vision format: raw base64 string
    })
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": GEMMA_MODEL,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.2, "top_p": 0.9, "num_predict": 600},
                },
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"].strip()
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Ollama çalışmıyor.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vision analizi hatası: {str(e)}")


async def ask_gemma_rag(prompt: str, system: str = "", rag_query: str = "",
                        timeout: float = 180.0) -> str:
    """RAG bağlamıyla güçlendirilmiş Gemma 4 isteği."""
    enriched_system = system
    if RAG_ENABLED and rag_query:
        try:
            _init_rag_if_needed()
            import rag as rag_module
            context = rag_module.get_context_for_prompt(rag_query, n_results=4, min_relevance=0.3)
            if context:
                enriched_system = system + "\n\n" + context if system else context
        except Exception:
            pass
    return await ask_gemma(prompt, system=enriched_system, timeout=timeout)


async def stream_gemma(prompt: str, system: str = "") -> AsyncGenerator[str, None]:
    """Gemma 4'ten token token streaming (SSE için)."""
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
                    "options": {"temperature": 0.25, "top_p": 0.85, "num_predict": 512},
                },
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        try:
                            chunk = json.loads(line)
                            token = chunk.get("message", {}).get("content", "")
                            if token:
                                yield f"data: {json.dumps({'token': token})}\n\n"
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
- ACİL semptomlar (göğüs ağrısı, nefes darlığı, bilinç kaybı, felç bulguları) görürsen hemen o yönde detaylandır.
- MTS (Manchester Triage System) kriterlerine göre değerlendir: yayılım, şiddet (1-10), süre, tetikleyici, eşlik eden bulgular.
- Empatik, sakinleştirici ton. Soru işaretiyle bitir.

ÖRNEK MÜLAKATİ:
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
- EMERGENCY signs (chest pain, breathing difficulty, loss of consciousness, stroke signs): explore FIRST.
- Apply MTS (Manchester Triage System) criteria: radiation, severity (1-10), duration, triggers, associated symptoms.
- Empathetic, calming tone. End with a question?

EXAMPLE EXCHANGE:
Patient: John Doe, 58y, Male.
Q: "Hello John, what's the main reason you're here today?"
A: "I've had chest pressure since this morning."
Q: "Does this pressure spread to your arm, jaw, or back?"
A: "Yes, it goes down my left arm."
Q: "On a scale of 1-10 how severe is it, and do you have any difficulty breathing?"

FOLLOW THIS EXAMPLE — contextual, deepening, clinician-like questions."""

TRIAGE_SYSTEM_TR = """Sen Manchester Triage System (MTS) ve CTAS standartlarına göre eğitilmiş klinik triaj uzmanısın (Gemma 4 tarafından güçlendirilmişsin).
Hastanın semptom mülakat geçmişini analiz et.
ÇIKTI: SADECE geçerli JSON döndür. Başka hiçbir metin veya markdown ekleme.
{
  "triage_level": "RED veya YELLOW veya GREEN",
  "confidence_score": 0-100 arası tam sayı,
  "chief_complaint": "Ana şikayet — tek net cümle",
  "symptoms_summary": "Semptom özeti 2-3 cümle",
  "possible_conditions": ["En olası tanı", "İkinci olasılık", "Üçüncü olasılık"],
  "recommended_action": "Önerilen eylem tek cümle",
  "clinical_notes": "Doktor için kritik gözlemler 2-3 cümle",
  "urgency_flags": ["Acil uyarı bayrakları — örn: Kardiyak risk faktörleri mevcut"]
}
TRİAJ STANDARTLARI:
RED = Hayati risk / derhal müdahale (AMI, inme, anafilaksi, solunum yetmezliği, GCS<8)
YELLOW = Acil, 30dk-2saat içinde görülmeli (yüksek ateş, orta şiddetli ağrı, brakikardi, hipertansif acil)  
GREEN = Rutin poliklinik (hafif semptom, kronik takip, üst solunum yolu enfeksiyonu)"""

TRIAGE_SYSTEM_EN = """You are a clinical triage expert trained on Manchester Triage System (MTS) and CTAS standards (powered by Gemma 4).
Analyze the patient's symptom interview history.
OUTPUT: Return ONLY valid JSON. No other text or markdown.
{
  "triage_level": "RED or YELLOW or GREEN",
  "confidence_score": integer 0-100,
  "chief_complaint": "Main complaint one sentence",
  "symptoms_summary": "Symptom summary 2-3 sentences",
  "possible_conditions": ["Most likely", "Second", "Third"],
  "recommended_action": "Action one sentence",
  "clinical_notes": "Critical notes for doctor 2-3 sentences",
  "urgency_flags": ["Emergency flags if any"]
}
TRIAGE STANDARDS:
RED = Life-threatening / immediate (AMI, stroke, anaphylaxis, respiratory failure, GCS<8)
YELLOW = Urgent, seen within 30min-2hrs (high fever, moderate pain, bradycardia, hypertensive urgency)
GREEN = Routine outpatient (mild symptoms, chronic follow-up, URTI)"""

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

# ─────────────────────────────────────────────
#  Startup Event
# ─────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    """Uygulama başladığında DB'yi başlat ve geçmiş verileri yükle."""
    init_db()
    db_load_all()
    print(f"[AnamnezAI v4.0] DB hazır: {DB_PATH}")

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


@app.get("/health")
async def health_check():
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            models = [m["name"] for m in resp.json().get("models", [])]
            model_base = GEMMA_MODEL.split(":")[0]
            gemma_available = any(model_base in m for m in models)

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
            "version": "4.0.0",
            "ollama": "connected",
            "gemma_model": GEMMA_MODEL,
            "gemma_available": gemma_available,
            "available_models": models,
            "sessions_active": len(sessions),
            "summaries_cached": len(summaries),
            "db_path": DB_PATH,
            **rag_info,
        }
    except Exception as e:
        return {"status": "degraded", "ollama": "disconnected", "error": str(e)}


@app.post("/api/session/start", response_model=SessionResponse)
async def start_session(req: StartSessionRequest):
    """Yeni hasta mülakatı başlatır — ilk soruyu Gemma 4 + RAG ile üretir. Vital bulgular kaydedilir."""
    session_id = str(uuid.uuid4())
    lang = req.language

    vitals_dict = vitals_to_dict(req.vitals)
    vitals_ctx = ""
    if vitals_dict:
        parts = []
        if req.vitals.blood_pressure: parts.append(f"KB: {req.vitals.blood_pressure}")
        if req.vitals.pulse: parts.append(f"Nabız: {req.vitals.pulse} bpm")
        if req.vitals.temperature: parts.append(f"Ateş: {req.vitals.temperature}°C")
        if req.vitals.spo2: parts.append(f"SpO2: {req.vitals.spo2}%")
        if req.vitals.respiratory_rate: parts.append(f"SS: {req.vitals.respiratory_rate}/dk")
        if parts:
            vitals_ctx = f"\nVital bulgular: {', '.join(parts)}" if lang == "tr" else f"\nVitals: {', '.join(parts)}"

    opening_prompt = (
        f"Hasta: {req.patient_name}, {req.age} yaşında, {req.gender}.{vitals_ctx}\n"
        f"Bu ilk görüşme. Hastanın bugünkü ana şikayetini öğrenmek için samimi, empatik bir açılış sorusu sor. Soru 1/5."
    ) if lang == "tr" else (
        f"Patient: {req.patient_name}, {req.age}y, {req.gender}.{vitals_ctx}\n"
        f"First visit. Ask a warm, empathetic opening question to learn their main complaint. Q1/5."
    )

    rag_query = "medical triage first question patient interview clinical assessment"
    first_question = await ask_gemma_rag(opening_prompt, system=get_system_prompt(lang), rag_query=rag_query)

    sessions[session_id] = {
        "patient_name": req.patient_name,
        "age": req.age,
        "gender": req.gender,
        "language": lang,
        "step": 1,
        "total_steps": 5,
        "qa_history": [{"question": first_question, "answer": None}],
        "completed": False,
        "vitals": vitals_dict,
        "image_analyses": [],
        "created_at": datetime.utcnow().isoformat(),
    }
    db_save_session(session_id, sessions[session_id])
    await notify_queue_update()

    return SessionResponse(session_id=session_id, question=first_question, step=1, total_steps=5)


@app.post("/api/session/answer", response_model=SessionResponse)
async def submit_answer(req: AnswerRequest):
    """Cevabı kaydeder, Gemma 4 ile bağlamsal sonraki soruyu üretir."""
    session = sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı.")
    if session["completed"]:
        raise HTTPException(status_code=400, detail="Mülakat zaten tamamlandı.")

    session["qa_history"][-1]["answer"] = req.answer
    current_step = session["step"]
    total_steps  = session["total_steps"]

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

    if lang == "tr":
        next_prompt = (
            f"Hasta: {session['patient_name']}, {session['age']} yaşında, {session['gender']}.\n\n"
            f"Mülakat geçmişi:\n{history_text}\n\n"
            f"Yukarıdaki cevaplara dayanarak tanıyı netleştirecek SONRAKI en kritik soruyu sor. "
            f"Acil belirti varsa o yönde derinleş. Soru {current_step+1}/{total_steps}."
        )
    else:
        next_prompt = (
            f"Patient: {session['patient_name']}, {session['age']}y, {session['gender']}.\n\n"
            f"Interview so far:\n{history_text}\n\n"
            f"Based on above answers, ask the NEXT most critical question to clarify the diagnosis. "
            f"If emergency signs present, explore further. Q{current_step+1}/{total_steps}."
        )

    rag_query = req.answer + " " + history_text[-300:]
    next_question = await ask_gemma_rag(next_prompt, system=get_system_prompt(lang), rag_query=rag_query)
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

    triage_prompt = (
        f"HASTA: {session['patient_name']}, {session['age']} yaş, {session['gender']}{vitals_ctx}{image_ctx}\n\n"
        f"5 TURLU MÜLAKAT:\n{history_text}\n\n"
        f"Bu hastayı triaj et. Sadece JSON döndür."
    ) if lang == "tr" else (
        f"PATIENT: {session['patient_name']}, {session['age']}y, {session['gender']}{vitals_ctx}{image_ctx}\n\n"
        f"5-TURN INTERVIEW:\n{history_text}\n\n"
        f"Triage this patient. Return ONLY JSON."
    )

    raw = await ask_gemma(triage_prompt, get_triage_system(lang))

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

    level = triage_data.get("triage_level", "YELLOW").upper()
    if level not in TRIAGE_COLOR:
        level = "YELLOW"

    flags = [f for f in triage_data.get("urgency_flags", [])
             if f and len(f) > 3 and "boş" not in f.lower() and "empty" not in f.lower()]

    # Son görüntü analiz bulgusunu ekle
    image_findings = None
    if image_analyses:
        image_findings = image_analyses[-1].get("analysis", "")[:500]

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
    )

    summaries[session_id] = result.model_dump()
    db_save_summary(session_id, summaries[session_id])
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
async def get_patient_queue():
    """Triaj önceliğine göre tam veriyle hasta kuyruğunu döndürür."""
    priority = {"RED": 0, "YELLOW": 1, "GREEN": 2, "PENDING": 3}
    patients = []
    for sid, s in sessions.items():
        if s["completed"]:
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
async def delete_session(session_id: str):
    """Oturumu siler (HIPAA uyumu için)."""
    if session_id in sessions:
        del sessions[session_id]
        summaries.pop(session_id, None)
        db_delete_session(session_id)
        await notify_queue_update()
        return {"message": "Oturum silindi."}
    raise HTTPException(status_code=404, detail="Oturum bulunamadı.")


# ─────────────────────────────────────────────
#  Serve Frontend — MUST be last (API routes take priority)
# ─────────────────────────────────────────────
FRONTEND_DIR = os.getenv(
    "FRONTEND_DIR",
    os.path.join(os.path.dirname(__file__), "..", "frontend"),
)
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    print(f"\n{'='*60}")
    print(f"  AnamnezAI v4.0 — Gemma 4 Medical Pre-Triage")
    print(f"  Model    : {GEMMA_MODEL} (via Ollama)")
    print(f"  Ollama   : {OLLAMA_BASE_URL}")
    print(f"  RAG      : {'Aktif' if RAG_ENABLED else 'Devre Dışı'}")
    print(f"  DB       : {DB_PATH}")
    print(f"  API      : http://localhost:8000")
    print(f"  Docs     : http://localhost:8000/docs")
    print(f"  Features : Multimodal Vision | SSE Kuyruk | SQLite | Vital Bulgular")
    print(f"{'='*60}\n")

    init_db()
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

