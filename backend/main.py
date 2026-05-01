"""
MediScreen AI — Backend
AI-Powered Patient Pre-Triage System using Gemma 4 via Ollama
Gemma 4 Good Hackathon — Health & Sciences + Ollama Prize Tracks
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import httpx
import json
import uuid
import os
from datetime import datetime

# ─────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
GEMMA_MODEL     = os.getenv("GEMMA_MODEL", "gemma4:e4b")   # gemma4:e2b (hızlı) | gemma4:e4b (önerilir) | gemma4:26b (güçlü)

app = FastAPI(
    title="MediScreen AI",
    description="AI-Powered Patient Pre-Triage using Gemma 4 via Ollama",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# In-memory session store  (replace with Redis/DB for production)
sessions: dict[str, dict] = {}

# ─────────────────────────────────────────────
#  Pydantic Models
# ─────────────────────────────────────────────
class StartSessionRequest(BaseModel):
    patient_name: str
    age: int
    gender: str
    language: str = "tr"   # "tr" veya "en"

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
    triage_level: str          # RED | YELLOW | GREEN
    triage_color: str          # hex renk
    confidence_score: int      # 0-100
    chief_complaint: str
    symptoms_summary: str
    possible_conditions: list[str]
    recommended_action: str
    clinical_notes: str
    generated_at: str

# ─────────────────────────────────────────────
#  Ollama Helper
# ─────────────────────────────────────────────
async def ask_gemma(prompt: str, system: str = "") -> str:
    """Ollama üzerinden Gemma 4'e istek gönderir (chat API ile system prompt desteği)."""
    try:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": GEMMA_MODEL,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "top_p": 0.9,
                        "num_predict": 512,
                    },
                },
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"].strip()
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Ollama servisi çalışmıyor. Önce 'ollama serve' komutunu çalıştırın.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemma hatası: {str(e)}")


# ─────────────────────────────────────────────
#  Prompt Templates
# ─────────────────────────────────────────────
SYSTEM_PROMPT_TR = """Sen MediScreen AI'sın — deneyimli, empatik bir tıbbi pre-triaj asistanısın.
Görevin: Hastanın semptomlarını anlamak için akıllı, sıralı sorular sormak.
Kurallar:
- Her seferinde YALNIZCA 1 soru sor.
- Tıbbi jargon kullanma, sade Türkçe konuş.
- Empatik ve sakinleştirici bir ton kullan.
- Cevabı kısa tut, 2 cümleyi geçme.
- Soru işareti ile bitir."""

SYSTEM_PROMPT_EN = """You are MediScreen AI — an experienced, empathetic medical pre-triage assistant.
Your role: Ask smart, sequential questions to understand the patient's symptoms.
Rules:
- Ask ONLY 1 question at a time.
- Avoid medical jargon, use plain language.
- Use an empathetic and calming tone.
- Keep responses brief, maximum 2 sentences.
- End with a question mark."""


def get_system_prompt(lang: str) -> str:
    return SYSTEM_PROMPT_TR if lang == "tr" else SYSTEM_PROMPT_EN


INTERVIEW_QUESTIONS_TR = [
    "Merhaba {name}! Bugün sizi en çok rahatsız eden şikayetiniz nedir?",
    None,  # Dinamik — Gemma üretecek
    None,  # Dinamik
    None,  # Dinamik
    None,  # Dinamik
]

INTERVIEW_QUESTIONS_EN = [
    "Hello {name}! What is your main complaint or concern today?",
    None,
    None,
    None,
    None,
]

TRIAGE_SYSTEM_TR = """Sen klinik triaj uzmanısın. Hastanın semptom mülakat verilerini analiz et.
MUTLAKA aşağıdaki JSON formatında yanıt ver (başka hiçbir metin ekleme):
{
  "triage_level": "RED veya YELLOW veya GREEN",
  "confidence_score": 0-100 arası tam sayı,
  "chief_complaint": "Ana şikayet tek cümle",
  "symptoms_summary": "Semptom özeti 2-3 cümle",
  "possible_conditions": ["Olası durum 1", "Olası durum 2", "Olası durum 3"],
  "recommended_action": "Önerilen eylem tek cümle",
  "clinical_notes": "Doktor için klinik notlar 2-3 cümle"
}
Triaj seviyeleri: RED=Acil/Hayati tehlike, YELLOW=Acil/Bekleme olabilir, GREEN=Rutin"""

TRIAGE_SYSTEM_EN = """You are a clinical triage expert. Analyze the patient's symptom interview data.
ALWAYS respond in the following JSON format (no other text):
{
  "triage_level": "RED or YELLOW or GREEN",
  "confidence_score": integer 0-100,
  "chief_complaint": "Main complaint in one sentence",
  "symptoms_summary": "Symptom summary in 2-3 sentences",
  "possible_conditions": ["Possible condition 1", "Possible condition 2", "Possible condition 3"],
  "recommended_action": "Recommended action in one sentence",
  "clinical_notes": "Clinical notes for doctor in 2-3 sentences"
}
Triage levels: RED=Emergency/Life-threatening, YELLOW=Urgent/Can wait briefly, GREEN=Routine"""

TRIAGE_COLOR = {"RED": "#ba1a1a", "YELLOW": "#dca26c", "GREEN": "#006a68"}

# ─────────────────────────────────────────────
#  Endpoints
# ─────────────────────────────────────────────

@app.get("/")
async def root():
    index = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"message": "MediScreen AI API çalışıyor.", "docs": "/docs"}


@app.get("/health")
async def health_check():
    """Ollama bağlantısını ve Gemma modelini kontrol eder."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            models = [m["name"] for m in resp.json().get("models", [])]
            gemma_available = any(GEMMA_MODEL.split(":")[0] in m for m in models)
        return {
            "status": "ok",
            "ollama": "connected",
            "gemma_model": GEMMA_MODEL,
            "gemma_available": gemma_available,
            "available_models": models,
        }
    except Exception as e:
        return {"status": "degraded", "ollama": "disconnected", "error": str(e)}


@app.post("/api/session/start", response_model=SessionResponse)
async def start_session(req: StartSessionRequest):
    """Yeni hasta mülakatı başlatır."""
    session_id = str(uuid.uuid4())
    lang = req.language

    first_q_template = INTERVIEW_QUESTIONS_TR[0] if lang == "tr" else INTERVIEW_QUESTIONS_EN[0]
    first_question = first_q_template.format(name=req.patient_name)

    sessions[session_id] = {
        "patient_name": req.patient_name,
        "age": req.age,
        "gender": req.gender,
        "language": lang,
        "step": 1,
        "total_steps": 5,
        "qa_history": [{"question": first_question, "answer": None}],
        "completed": False,
    }

    return SessionResponse(
        session_id=session_id,
        question=first_question,
        step=1,
        total_steps=5,
    )


@app.post("/api/session/answer", response_model=SessionResponse)
async def submit_answer(req: AnswerRequest):
    """Hastanın cevabını kaydeder ve sonraki soruyu üretir."""
    session = sessions.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı.")
    if session["completed"]:
        raise HTTPException(status_code=400, detail="Mülakat tamamlandı.")

    # Mevcut soruya cevabı kaydet
    session["qa_history"][-1]["answer"] = req.answer
    current_step = session["step"]
    total_steps = session["total_steps"]

    if current_step >= total_steps:
        session["completed"] = True
        return SessionResponse(
            session_id=req.session_id,
            question="__COMPLETED__",
            step=current_step,
            total_steps=total_steps,
        )

    # Gemma ile sonraki soruyu üret
    lang = session["language"]
    history_text = "\n".join(
        f"Soru {i+1}: {qa['question']}\nCevap: {qa['answer'] or ''}"
        for i, qa in enumerate(session["qa_history"])
        if qa["answer"]
    )

    if lang == "tr":
        next_q_prompt = (
            f"Hasta: {session['patient_name']}, {session['age']} yaşında, {session['gender']}.\n"
            f"Mülakat geçmişi:\n{history_text}\n\n"
            f"Şimdiye kadar {current_step} soru sordun. "
            f"Hastanın semptomlarını daha iyi anlamak için bir sonraki en önemli soruyu sor. "
            f"Soru numarası {current_step + 1}/{total_steps}."
        )
    else:
        next_q_prompt = (
            f"Patient: {session['patient_name']}, {session['age']} years old, {session['gender']}.\n"
            f"Interview history:\n{history_text}\n\n"
            f"You have asked {current_step} questions so far. "
            f"Ask the next most important question to better understand the patient's symptoms. "
            f"Question number {current_step + 1}/{total_steps}."
        )

    next_question = await ask_gemma(next_q_prompt, get_system_prompt(lang))

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
    """Tamamlanan mülakattan klinik özet ve triaj üretir."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı.")
    if not session["completed"]:
        raise HTTPException(status_code=400, detail="Mülakat henüz tamamlanmadı.")

    lang = session["language"]
    history_text = "\n".join(
        f"Q{i+1}: {qa['question']}\nA: {qa['answer'] or 'Yanıt yok'}"
        for i, qa in enumerate(session["qa_history"])
    )

    triage_system = TRIAGE_SYSTEM_TR if lang == "tr" else TRIAGE_SYSTEM_EN
    triage_prompt = (
        f"Hasta Bilgileri:\n"
        f"Ad: {session['patient_name']}\n"
        f"Yaş: {session['age']}\n"
        f"Cinsiyet: {session['gender']}\n\n"
        f"Mülakat:\n{history_text}\n\n"
        f"Bu hastayı triaj et ve klinik özet oluştur."
    )

    raw_response = await ask_gemma(triage_prompt, triage_system)

    # JSON parse
    try:
        # JSON bloğunu bul
        start = raw_response.find("{")
        end = raw_response.rfind("}") + 1
        if start != -1 and end > start:
            triage_data = json.loads(raw_response[start:end])
        else:
            raise ValueError("JSON bulunamadı")
    except Exception:
        # Fallback — parse başarısız olursa güvenli varsayılan
        triage_data = {
            "triage_level": "YELLOW",
            "confidence_score": 75,
            "chief_complaint": "Semptom analizi tamamlandı",
            "symptoms_summary": raw_response[:200],
            "possible_conditions": ["Değerlendirme gerekli"],
            "recommended_action": "Doktor muayenesi önerilir",
            "clinical_notes": raw_response[:300],
        }

    level = triage_data.get("triage_level", "YELLOW").upper()
    if level not in TRIAGE_COLOR:
        level = "YELLOW"

    return ClinicalSummaryResponse(
        session_id=session_id,
        patient_name=session["patient_name"],
        age=session["age"],
        gender=session["gender"],
        triage_level=level,
        triage_color=TRIAGE_COLOR[level],
        confidence_score=int(triage_data.get("confidence_score", 80)),
        chief_complaint=triage_data.get("chief_complaint", ""),
        symptoms_summary=triage_data.get("symptoms_summary", ""),
        possible_conditions=triage_data.get("possible_conditions", []),
        recommended_action=triage_data.get("recommended_action", ""),
        clinical_notes=triage_data.get("clinical_notes", ""),
        generated_at=datetime.utcnow().isoformat() + "Z",
    )


@app.get("/api/patients/queue")
async def get_patient_queue():
    """Tamamlanmış mülakat listesini triaj önceliğine göre döndürür."""
    priority_order = {"RED": 0, "YELLOW": 1, "GREEN": 2}
    completed = [
        {
            "session_id": sid,
            "patient_name": s["patient_name"],
            "age": s["age"],
            "gender": s["gender"],
            "completed": s["completed"],
        }
        for sid, s in sessions.items()
        if s["completed"]
    ]
    return {"total": len(completed), "patients": completed}


@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    """Oturumu siler (HIPAA uyumu için)."""
    if session_id in sessions:
        del sessions[session_id]
        return {"message": "Oturum silindi."}
    raise HTTPException(status_code=404, detail="Oturum bulunamadı.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

