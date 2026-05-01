"""
AnamnezAI — Backend v3.0
AI-Powered Patient Pre-Triage using Gemma 4 via Ollama
Gemma 4 Good Hackathon — Health & Sciences + Ollama Prize Tracks
v3.0: RAG (Retrieval-Augmented Generation) ile tıbbi bilgi tabanı entegrasyonu
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
from datetime import datetime

# ─────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
GEMMA_MODEL     = os.getenv("GEMMA_MODEL", "gemma4:e4b")
RAG_ENABLED     = os.getenv("RAG_ENABLED", "true").lower() == "true"

app = FastAPI(
    title="AnamnezAI",
    description="AI-Powered Patient Pre-Triage using Gemma 4 via Ollama + RAG — Gemma 4 Good Hackathon",
    version="3.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage (Redis/DB for production)
sessions:  dict[str, dict] = {}
summaries: dict[str, dict] = {}   # session_id → full clinical summary cache

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
                # İlk başlatma: yerleşik bilgi tabanını yükle
                rag_module.ingest_builtin_knowledge()
            _rag_initialized = True
    except Exception as e:
        print(f"[RAG] Başlatma atlandı: {e}")

# ─────────────────────────────────────────────
#  Pydantic Models
# ─────────────────────────────────────────────
class StartSessionRequest(BaseModel):
    patient_name: str
    age: int
    gender: str
    language: str = "tr"

class AnswerRequest(BaseModel):
    session_id: str
    answer: str

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
    generated_at: str

# ─────────────────────────────────────────────
#  Ollama /api/chat Helper
# ─────────────────────────────────────────────
async def ask_gemma(prompt: str, system: str = "", timeout: float = 180.0) -> str:
    """Ollama /api/chat üzerinden Gemma 4'e istek gönderir."""
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
        raise HTTPException(status_code=504, detail=f"Gemma 4 yanıt vermedi (timeout {int(timeout)}sn). Model yükleniyor olabilir, lütfen tekrar deneyin.")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Bağlantı zaman aşımı. Ollama servisini kontrol edin.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemma 4 hatası: {str(e)}")


async def ask_gemma_rag(prompt: str, system: str = "", rag_query: str = "",
                        timeout: float = 180.0) -> str:
    """RAG bağlamıyla güçlendirilmiş Gemma 4 isteği.

    rag_query ile ilgili tıbbi referanslar otomatik olarak system prompt'a eklenir.
    RAG mevcut değilse veya kayıt yoksa normal ask_gemma gibi davranır.
    """
    enriched_system = system
    if RAG_ENABLED and rag_query:
        try:
            _init_rag_if_needed()
            import rag as rag_module
            context = rag_module.get_context_for_prompt(rag_query, n_results=4, min_relevance=0.3)
            if context:
                enriched_system = system + "\n\n" + context if system else context
        except Exception:
            pass  # RAG başarısız olursa sessizce devam et

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

# Triage renk palet
TRIAGE_COLOR = {"RED": "#ba1a1a", "YELLOW": "#e07b26", "GREEN": "#006a68"}


def get_system_prompt(lang: str) -> str:
    return SYSTEM_PROMPT_TR if lang == "tr" else SYSTEM_PROMPT_EN


def get_triage_system(lang: str) -> str:
    return TRIAGE_SYSTEM_TR if lang == "tr" else TRIAGE_SYSTEM_EN

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
                json={
                    "model": GEMMA_MODEL,
                    "prompt": "Hi",
                    "stream": False,
                    "options": {"num_predict": 1},
                },
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
    """RAG bilgi tabanı durumunu döndürür."""
    if not RAG_ENABLED:
        return {"enabled": False, "reason": "RAG_ENABLED=false"}
    try:
        import rag as rag_module
        if not rag_module.is_rag_available():
            return {"enabled": False, "reason": "chromadb veya sentence-transformers kurulu değil"}
        _init_rag_if_needed()
        stats = rag_module.get_db_stats()
        return {
            "enabled": True,
            "initialized": _rag_initialized,
            **stats,
        }
    except Exception as e:
        return {"enabled": False, "error": str(e)}


@app.post("/api/rag/ingest/text")
async def rag_ingest_text(body: dict):
    """Ham metin veya Q&A çiftlerini bilgi tabanına ekler."""
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
        raise HTTPException(status_code=503, detail="RAG bileşenleri kurulu değil. pip install chromadb sentence-transformers")


@app.post("/api/rag/ingest/pdf")
async def rag_ingest_pdf(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    """PDF dosyasını yükler ve bilgi tabanına ekler (arka planda)."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Sadece PDF dosyası kabul edilir.")

    try:
        import rag as rag_module
        contents = await file.read()
        # Geçici dosyaya yaz
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        def _ingest():
            try:
                _init_rag_if_needed()
                count = rag_module.ingest_pdf(tmp_path, source_name=file.filename[:40])
                import os
                os.unlink(tmp_path)
                print(f"[RAG] PDF yüklendi: {file.filename} — {count} chunk")
            except Exception as e:
                print(f"[RAG] PDF hatası: {e}")

        if background_tasks:
            background_tasks.add_task(_ingest)
            return {"status": "processing", "filename": file.filename,
                    "message": "PDF arka planda işleniyor. /api/rag/status ile kontrol edin."}
        else:
            _ingest()
            stats = rag_module.get_db_stats()
            return {"status": "done", "filename": file.filename, "total_chunks": stats.get("total_chunks")}

    except ImportError:
        raise HTTPException(status_code=503, detail="RAG bileşenleri kurulu değil.")


@app.post("/api/rag/ingest/builtin")
async def rag_ingest_builtin():
    """Yerleşik tıbbi bilgi tabanını (MTS, kardiyak, nörolojik vb.) yükler."""
    try:
        import rag as rag_module
        added = rag_module.ingest_builtin_knowledge()
        stats = rag_module.get_db_stats()
        return {
            "added_chunks": added,
            "total_chunks": stats.get("total_chunks", 0),
            "sources": stats.get("sources", {}),
        }
    except ImportError:
        raise HTTPException(status_code=503, detail="RAG bileşenleri kurulu değil.")


@app.get("/api/rag/query")
async def rag_query(q: str, n: int = 4):
    """RAG retrieval test endpoint — hangi bağlamın alındığını gösterir."""
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
    """Ollama bağlantısı ve Gemma 4 model durumunu kontrol eder."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            models = [m["name"] for m in resp.json().get("models", [])]
            model_base = GEMMA_MODEL.split(":")[0]
            gemma_available = any(model_base in m for m in models)

        # RAG durumu
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
                    rag_info["rag_note"] = "pip install chromadb sentence-transformers"
            except Exception:
                rag_info["rag_available"] = False

        return {
            "status": "ok",
            "ollama": "connected",
            "gemma_model": GEMMA_MODEL,
            "gemma_available": gemma_available,
            "available_models": models,
            "sessions_active": len(sessions),
            "summaries_cached": len(summaries),
            **rag_info,
        }
    except Exception as e:
        return {"status": "degraded", "ollama": "disconnected", "error": str(e)}


@app.post("/api/session/start", response_model=SessionResponse)
async def start_session(req: StartSessionRequest):
    """Yeni hasta mülakatı başlatır — ilk soruyu Gemma 4 + RAG ile üretir."""
    session_id = str(uuid.uuid4())
    lang = req.language

    opening_prompt = (
        f"Hasta: {req.patient_name}, {req.age} yaşında, {req.gender}.\n"
        f"Bu ilk görüşme. Hastanın bugünkü ana şikayetini öğrenmek için samimi, "
        f"empatik bir açılış sorusu sor. Soru 1/5."
    ) if lang == "tr" else (
        f"Patient: {req.patient_name}, {req.age}y, {req.gender}.\n"
        f"First visit. Ask a warm, empathetic opening question to learn their main complaint. Q1/5."
    )

    # RAG ile açılış sorusu — genel triaj bilgisi ile güçlendir
    rag_query = f"medical triage first question patient interview clinical assessment"
    first_question = await ask_gemma_rag(
        opening_prompt,
        system=get_system_prompt(lang),
        rag_query=rag_query,
    )

    sessions[session_id] = {
        "patient_name": req.patient_name,
        "age": req.age,
        "gender": req.gender,
        "language": lang,
        "step": 1,
        "total_steps": 5,
        "qa_history": [{"question": first_question, "answer": None}],
        "completed": False,
        "created_at": datetime.utcnow().isoformat(),
    }

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
        return SessionResponse(
            session_id=req.session_id,
            question="__COMPLETED__",
            step=current_step,
            total_steps=total_steps,
        )

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

    # Hastanın cevaplarından RAG sorgu metni oluştur (semptom kelimelerini çıkar)
    rag_query = req.answer + " " + history_text[-300:]  # Son 300 karakter
    next_question = await ask_gemma_rag(
        next_prompt,
        system=get_system_prompt(lang),
        rag_query=rag_query,
    )
    session["step"] += 1
    session["qa_history"].append({"question": next_question, "answer": None})

    return SessionResponse(
        session_id=req.session_id,
        question=next_question,
        step=session["step"],
        total_steps=total_steps,
    )


@app.get("/api/session/{session_id}/summary", response_model=ClinicalSummaryResponse)
async def get_clinical_summary(session_id: str):
    """Tamamlanan mülakattan Gemma 4 ile klinik özet ve triaj üretir."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı.")
    if not session["completed"]:
        raise HTTPException(status_code=400, detail="Mülakat henüz tamamlanmadı.")

    # Return cached if exists
    if session_id in summaries:
        return ClinicalSummaryResponse(**summaries[session_id])

    lang = session["language"]
    history_text = "\n".join(
        f"Q{i+1}: {qa['question']}\nA: {qa.get('answer', 'Yanıt yok')}"
        for i, qa in enumerate(session["qa_history"])
    )

    triage_prompt = (
        f"HASTA: {session['patient_name']}, {session['age']} yaş, {session['gender']}\n\n"
        f"5 TURLU MÜLAKAT:\n{history_text}\n\n"
        f"Bu hastayı triaj et. Sadece JSON döndür."
    ) if lang == "tr" else (
        f"PATIENT: {session['patient_name']}, {session['age']}y, {session['gender']}\n\n"
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
                cleaned = part[4:].strip()
                break
            elif "{" in part:
                cleaned = part.strip()
                break
    try:
        start = cleaned.find("{")
        end   = cleaned.rfind("}") + 1
        triage_data = json.loads(cleaned[start:end])
    except Exception:
        triage_data = {
            "triage_level": "YELLOW",
            "confidence_score": 70,
            "chief_complaint": "Değerlendirme tamamlandı",
            "symptoms_summary": raw[:300],
            "possible_conditions": ["Doktor değerlendirmesi gerekli"],
            "recommended_action": "Doktor muayenesi önerilir",
            "clinical_notes": raw[:400],
            "urgency_flags": [],
        }

    level = triage_data.get("triage_level", "YELLOW").upper()
    if level not in TRIAGE_COLOR:
        level = "YELLOW"

    flags = [f for f in triage_data.get("urgency_flags", [])
             if f and len(f) > 3 and "boş" not in f.lower() and "empty" not in f.lower()]

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
        generated_at=datetime.utcnow().isoformat() + "Z",
    )

    # Cache for doctor queue
    summaries[session_id] = result.model_dump()
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
    prompt = (
        f"Hasta: {session['patient_name']}, {session['age']} yaş, {session['gender']}.\n"
        f"Mülakat:\n{history_text}\n\nDoktor için kısa klinik özet yaz (3-4 cümle)."
    ) if lang == "tr" else (
        f"Patient: {session['patient_name']}, {session['age']}y, {session['gender']}.\n"
        f"Interview:\n{history_text}\n\nWrite a brief clinical summary for the doctor (3-4 sentences)."
    )
    return StreamingResponse(
        stream_gemma(prompt, get_system_prompt(lang)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
                "triage_level": "PENDING",
                "triage_color": "#8c9499",
                "confidence_score": 0,
                "chief_complaint": "Özet bekleniyor...",
                "urgency_flags": [],
                "recommended_action": "",
                "symptoms_summary": "",
                "possible_conditions": [],
                "clinical_notes": "",
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


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    """Oturumu siler (HIPAA uyumu için)."""
    if session_id in sessions:
        del sessions[session_id]
        summaries.pop(session_id, None)
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
    print(f"\n{'='*55}")
    print(f"  AnamnezAI v3 — Gemma 4 Medical Pre-Triage + RAG")
    print(f"  Model  : {GEMMA_MODEL} (via Ollama)")
    print(f"  Ollama : {OLLAMA_BASE_URL}")
    print(f"  RAG    : {'Aktif' if RAG_ENABLED else 'Devre Disi'}")
    print(f"  API    : http://localhost:8000")
    print(f"  Docs   : http://localhost:8000/docs")
    print(f"{'='*55}\n")

    # RAG bilgi tabanını arka planda yükle (ilk başlatmada)
    if RAG_ENABLED:
        try:
            import rag as rag_module
            if rag_module.is_rag_available():
                stats = rag_module.get_db_stats()
                if stats.get("total_chunks", 0) == 0:
                    print("  RAG: Yerlesik tibbi bilgi tabani yukleniyor...")
                    rag_module.ingest_builtin_knowledge()
                    print(f"  RAG: HAZIR ({rag_module.get_db_stats().get('total_chunks')} chunk)")
                else:
                    print(f"  RAG: HAZIR ({stats.get('total_chunks')} chunk, {len(stats.get('sources', {}))} kaynak)")
            else:
                print("  RAG: chromadb/sentence-transformers kurulu degil (pip install ile eklenebilir)")
        except Exception as e:
            print(f"  RAG: Atıldı — {e}")

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

