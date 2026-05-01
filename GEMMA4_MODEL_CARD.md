# 🏆 Gemma 4 Good Hackathon — Model Usage & Technical Card

## ✅ Gemma 4 Usage Verification

This document proves that **Gemma 4** is the core AI model powering MediScreen AI, running locally via **Ollama**.

---

## Model Details

| Property | Value |
|---|---|
| **Model Family** | Gemma 4 |
| **Model ID** | `gemma4:e4b` |
| **Provider** | Google DeepMind |
| **Runtime** | Ollama (local inference) |
| **Ollama Model Page** | https://ollama.com/library/gemma4 |
| **HuggingFace** | https://huggingface.co/google/gemma-4 |

---

## How Gemma 4 is Used

MediScreen AI uses Gemma 4 for **three distinct medical NLP tasks**:

### Task 1 — Dynamic Interview Question Generation
```python
# backend/main.py — ask_gemma() function
POST http://localhost:11434/api/chat
{
  "model": "gemma4:e4b",
  "messages": [
    {"role": "system", "content": "Sen MediScreen AI'sın..."},
    {"role": "user",   "content": "Hastanın semptomları..."}
  ]
}
```
Gemma 4 receives the patient's symptom history and **generates the next most clinically relevant question** — this is NOT a static form.

### Task 2 — Clinical Summary & Triage Classification
```python
# Structured JSON output extraction
{
  "triage_level": "RED | YELLOW | GREEN",
  "confidence_score": 94,
  "chief_complaint": "...",
  "possible_conditions": ["...", "..."],
  "recommended_action": "..."
}
```
Gemma 4 analyzes a 5-turn patient interview and produces a **structured clinical report** with triage priority.

### Task 3 — Bilingual Medical Communication
Gemma 4 handles both **Turkish** and **English** medical conversations with appropriate tone and terminology adaptation.

---

## Ollama Integration Code

```python
# backend/main.py (lines ~75-100)
async def ask_gemma(prompt: str, system: str = "") -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            "http://localhost:11434/api/chat",   # Ollama API
            json={
                "model": "gemma4:e4b",           # Gemma 4
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.3}
            },
        )
    return resp.json()["message"]["content"].strip()
```

---

## Verification Steps for Judges

To verify Gemma 4 is running:

```bash
# 1. Check Ollama is serving Gemma 4
curl http://localhost:11434/api/tags
# → {"models": [{"name": "gemma4:e4b", ...}]}

# 2. Check MediScreen health endpoint
curl http://localhost:8000/health
# → {"status":"ok","gemma_model":"gemma4:e4b","gemma_available":true}

# 3. Run the Kaggle notebook
# notebooks/mediscreen_ai_kaggle.ipynb
# → Cell outputs show Gemma 4 generating clinical summaries
```

---

## Why Ollama + Gemma 4?

| Requirement | How MediScreen Meets It |
|---|---|
| Uses Gemma 4 | `gemma4:e4b` via Ollama API |
| Local inference | Ollama runs on-device, no cloud |
| Demonstrable output | Full patient interview + clinical report |
| Novel use case | Medical pre-triage (not a chatbot) |
| Health & Sciences | Democratizes triage in underserved areas |

---

## Reproducibility

```bash
# Anyone can reproduce this exact setup:
ollama pull gemma4:e4b
ollama serve
cd backend && pip install -r requirements.txt
python main.py

# Then open: frontend/index.html
```

---

## Competition Compliance

- ✅ Uses **Gemma 4** (not Gemma 3 or other models)
- ✅ Runs **locally via Ollama** (Ollama Prize Track)
- ✅ Real-world **health impact** (Health & Sciences Track)
- ✅ Open source under **CC-BY 4.0**
- ✅ Full source code provided for reproduction
- ✅ No proprietary datasets used

