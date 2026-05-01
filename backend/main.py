"""
MediScreen AI — Backend v2
AI-Powered Patient Pre-Triage using Gemma 4 via Ollama
Gemma 4 Good Hackathon — Health & Sciences + Ollama Prize Tracks

Sprint 2: Streaming SSE, bağlamsal mülakat, gelişmiş triaj
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, AsyncGenerator, AsyncGenerator
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
    description="AI-Powered Patient Pre-Triage using Gemma 4 via Ollama — Gemma 4 Good Hackathon",
    version="2.0.0",
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
    triage_level: str
    triage_color: str
    confidence_score: int
    chief_complaint: str
    symptoms_summary: str
    possible_conditions: list[str]
    recommended_action: str
    clinical_notes: str
    urgency_flags: list[str]
    generated_at: str

# ─────────────────────────────────────────────
#  Ollama / Gemma 4 Core
# ─────────────────────────────────────────────
async def ask_gemma(prompt: str, system: str = "") -> str:
    """Ollama /api/chat endpoint üzerinden Gemma 4'e istek gönderir."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
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
                        "num_predict": 768,
                        "repeat_penalty": 1.1,
                    },
                },
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"].strip()
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Ollama çalışmıyor. Terminal'de: ollama serve",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemma 4 hatası: {str(e)}")


async def stream_gemma(prompt: str, system: str = "") -> AsyncGenerator[str, None]:
    """Gemma 4'ten token token streaming yanıt alır (SSE için)."""
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
SYSTEM_PROMPT_TR = """Sen MediScreen AI — deneyimli, empatik bir tıbbi pre-triaj asistanısın.
Gemma 4 tarafından güçlendiriliyorsun ve tamamen yerel (Ollama) çalışıyorsun.

GÖREV: Hastanın semptomlarını anlamak için klinik açıdan değerli, bağlamsal sorular sor.

KURALLAR:
- Her seferinde SADECE 1 soru sor.
- Önceki cevapları dikkate alarak soru üret (bağlamsal mülakat).
- Tıbbi jargon kullanma, halkın anlayacağı dil kullan.
- Acil semptomlar (göğüs ağrısı, nefes darlığı, bilinç kaybı) görürsen önce detaylandır.
- Empatik, sakinleştirici ton. Maksimum 2 cümle. Soru işaretiyle bitir."""

SYSTEM_PROMPT_EN = """You are MediScreen AI — an experienced, empathetic medical pre-triage assistant.
Powered by Gemma 4, running 100% locally via Ollama.

TASK: Ask clinically relevant, contextual questions to understand the patient's symptoms.

RULES:
- Ask ONLY ONE question at a time.
- Generate questions based on previous answers (contextual interview).
- Avoid medical jargon, use plain patient-friendly language.
- If emergency signs present (chest pain, difficulty breathing), prioritize those.
- Empathetic, calming tone. Max 2 sentences. End with a question mark."""

TRIAGE_SYSTEM_TR = """Sen klinik triaj uzmanısın (Gemma 4 tarafından güçlendirilmişsin).
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
  "urgency_flags": ["Acil uyarı bayrakları — örn: 'Kardiyak risk faktörleri mevcut'"]
}

TRİAJ: RED=Hayati risk/derhal, YELLOW=Acil 30dk-2saat, GREEN=Rutin poliklinik"""

TRIAGE_SYSTEM_EN = """You are a clinical triage expert (powered by Gemma 4).
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

TRIAGE: RED=Life-threatening/immediate, YELLOW=Urgent 30min-2hrs, GREEN=Routine outpatient"""

TRIAGE_COLOR = {"RED": "#ba1a1a", "YELLOW": "#dca26c", "GREEN": "#006a68"}

def get_system_prompt(lang: str) -> str:
    return SYSTEM_PROMPT_TR if lang == "tr" else SYSTEM_PROMPT_EN

def get_triage_system(lang: str) -> str:
    return TRIAGE_SYSTEM_TR if lang == "tr" else TRIAGE_SYSTEM_EN

# ─────────────────────────────────────────────
#  Endpoints
# ─────────────────────────────────────────────

@app.get("/")
async def root():
    index = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"message": "MediScreen AI v2 çalışıyor.", "docs": "/docs", "model": GEMMA_MODEL}


@app.get("/health")
async def health_check():
    """Ollama bağlantısı ve Gemma 4 model durumunu kontrol eder."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            models = [m["name"] for m in resp.json().get("models", [])]
            model_base = GEMMA_MODEL.split(":")[0]
            gemma_available = any(model_base in m for m in models)
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
    """Yeni hasta mülakatı başlatır — ilk soruyu Gemma 4 üretir."""
    session_id = str(uuid.uuid4())
    lang = req.language

    # İlk soru da Gemma 4 tarafından dinamik üretiliyor
    opening_prompt = (
        f"Hasta: {req.patient_name}, {req.age} yaşında, {req.gender}.\n"
        f"Bu ilk görüşme. Hastanın bugünkü ana şikayetini öğrenmek için samimi, "
        f"empatik bir açılış sorusu sor. Soru 1/5."
    ) if lang == "tr" else (
        f"Patient: {req.patient_name}, {req.age}y, {req.gender}.\n"
        f"First visit. Ask a warm, empathetic opening question to learn their main complaint. Q1/5."
    )

    first_question = await ask_gemma(opening_prompt, get_system_prompt(lang))

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

    return SessionResponse(
        session_id=session_id,
        question=first_question,
        step=1,
        total_steps=5,
    )


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

    next_question = await ask_gemma(next_prompt, get_system_prompt(lang))
    session["step"] += 1
    session["qa_history"].append({"question": next_question, "answer": None})

    return SessionResponse(
        session_id=req.session_id,
        question=next_question,
        step=session["step"],
        total_steps=total_steps,
    )


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


@app.get("/api/session/{session_id}/summary", response_model=ClinicalSummaryResponse)
async def get_clinical_summary(session_id: str):
    """Tamamlanan mülakattan Gemma 4 ile klinik özet ve triaj üretir."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Oturum bulunamadı.")
    if not session["completed"]:
        raise HTTPException(status_code=400, detail="Mülakat henüz tamamlanmadı.")

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

    # JSON parse — ```json blokları da temizle
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

    return ClinicalSummaryResponse(
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
        recommended_action=triage_data.get("recommended_action", ""),
        clinical_notes=triage_data.get("clinical_notes", ""),
        urgency_flags=triage_data.get("urgency_flags", []),
        generated_at=datetime.utcnow().isoformat() + "Z",
    )


@app.get("/api/patients/queue")
async def get_patient_queue():
    """Tamamlanmış hasta listesini döndürür."""
    completed = [
        {
            "session_id": sid,
            "patient_name": s["patient_name"],
            "age": s["age"],
            "gender": s["gender"],
            "completed": s["completed"],
            "created_at": s.get("created_at", ""),
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
    print(f"\n{'='*55}")
    print(f"  MediScreen AI v2 — Gemma 4 Medical Pre-Triage")
    print(f"  Model  : {GEMMA_MODEL} (via Ollama)")
    print(f"  Ollama : {OLLAMA_BASE_URL}")
    print(f"  API    : http://localhost:8000")
    print(f"  Docs   : http://localhost:8000/docs")
    print(f"{'='*55}\n")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

