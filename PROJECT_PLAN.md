# AnamnezAI — Technical Project Plan
## Gemma 4 Good Hackathon — Health & Sciences + Ollama Prize Tracks

> **Last Updated:** May 2026  
> **GitHub:** https://github.com/enis1998/AnamnezAI  
> **Competition:** https://www.kaggle.com/competitions/gemma-4-good-hackathon

---

## 🎯 Project Overview

**AnamnezAI** is an AI-powered medical pre-triage platform that automates patient anamnesis collection before a hospital visit, using Gemma 4 running fully locally via Ollama.

- **Patient Side:** 5-turn contextual symptom interview  
- **Doctor Side:** Triage-prioritised patient queue + structured clinical summary  
- **AI Model:** Gemma 4 via Ollama — 100% local, data never leaves the device  
- **Triage Standard:** Manchester Triage System (MTS) + CTAS criteria

---

## 🎨 Design System

### "The Empathetic Guardian" — Creative North Star
Rejects the cold, clinical, overwhelming look of existing health tech.  
**High-quality editorial** approach: Medical authority + Premium wellness brand aesthetics.

### Colour Palette (Material Design Tonal)
| Token | Hex | Usage |
|-------|-----|-------|
| `primary` | `#002f40` | Primary actions, critical text |
| `primary-container` | `#00475e` | Hero areas, nav |
| `secondary` | `#006a68` | Health, progress, success states |
| `secondary-container` | `#a0f1ed` | Semantic highlights |
| `surface` | `#f8fafb` | App background |
| `error` | `#ba1a1a` | RED triage, critical alert |
| `tertiary` (Orange) | `#e07b26` | YELLOW triage, caution |

### Typography
- **Headings:** Manrope (Geometric, editorial feel)
- **Body/Label:** Inter (Accessibility, readability)

### Design Rules
- **"No-Line" Rule:** Use colour shift instead of borders
- **"Glass & Gradient":** Navigation bar → glassmorphism (backdrop-blur: 20px)
- **Minimum touch target:** 48×48dp (accessibility for elderly users)
- **Single Task Per Screen** — Reduce cognitive load

---

## 🏆 Hackathon Goals

| Prize Track | Value | Requirement |
|-------------|-------|-------------|
| Health & Sciences Impact | $10,000 | Gemma 4 usage in healthcare |
| Ollama Special Track | $10,000 | Gemma 4 running via Ollama |
| General ($50K) | $50,000 | Most innovative use |

**Gemma 4 Usage Proof:**
- Every API request to `/api/chat` calls the Ollama endpoint
- Model name `gemma4:e4b` — directly within the Gemma 4 family
- All triage decisions, question generation, and clinical summaries are produced by Gemma 4
- Kaggle notebook demo included (`notebooks/mediscreen_ai_kaggle.ipynb`)

---

## 📁 Project Structure

```
mediscreen/
├── backend/
│   ├── main.py              ← FastAPI + Gemma 4 integration (v5.0)
│   ├── rag.py               ← ChromaDB RAG engine
│   ├── auth.py              ← JWT + Google OAuth2
│   └── requirements.txt
├── frontend/
│   ├── index.html           ← Patient interview (chat UI + landing)
│   ├── summary.html         ← Clinical report card (Trust Layer)
│   ├── doctor.html          ← Doctor triage panel (sidebar + detail)
│   ├── clinical_review.html ← Full clinical review + FHIR export
│   ├── kiosk.html           ← Kiosk touch mode + QR ticket
│   ├── admin.html           ← Admin dashboard
│   └── patient_dashboard.html ← Patient history + profile SPA
├── evaluation/
│   ├── triage_cases.jsonl   ← 15 synthetic test cases
│   └── run_eval.py          ← Evaluation runner
├── notebooks/
│   └── mediscreen_ai_kaggle.ipynb
├── kubernetes/
│   └── deployment.yaml
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── README.md
├── ROADMAP.md
├── PROJECT_PLAN.md
└── GEMMA4_MODEL_CARD.md
```

---

## 🚀 Quick Start

```bash
# 1. Pull Ollama and download Gemma 4
ollama pull gemma4:e4b
# Optional — Vision analysis:
# ollama pull medgemma:4b

# 2. Start Ollama (background)
ollama serve

# 3. Install backend dependencies
cd mediscreen/backend
pip install -r requirements.txt

# 4. Start backend
python main.py
# http://localhost:8000       ← Frontend
# http://localhost:8000/docs  ← Swagger UI
```

With Docker:
```bash
cd mediscreen
docker compose up --build
```

---

## 🔌 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Ollama + Gemma 4 connection status |
| POST | `/api/warmup` | Pre-warm Gemma 4 model |
| POST | `/api/session/start` | Start new patient interview |
| POST | `/api/session/answer` | Submit answer, receive next question |
| GET | `/api/session/{id}/summary` | Clinical summary + triage (JSON) |
| GET | `/api/session/{id}/stream-summary` | SSE streaming clinical summary |
| GET | `/api/patients/queue` | Triage queue (doctor panel) |
| GET | `/api/offline-proof` | Proves offline / local operation |
| POST | `/api/analyze-image` | MedGemma medical image analysis |
| DELETE | `/api/session/{id}` | Delete session (GDPR right to erasure) |

---

## 🧠 Gemma 4 Flow

```
PATIENT                  GEMMA 4 (via Ollama)              DOCTOR
───────                  ────────────────────               ──────
[Start]   → /start   → generate first question (MTS system prompt)
[Answer]  → /answer  → generate context-aware next question
... × 5 turns ...
[Done]    → /summary → produce MTS triage JSON
          → /stream  → SSE streaming clinical summary
                                                   ← [Sees Queue]
                                                   ← [Reads Report]
```

### Triage Levels
| Level | Colour | Meaning | Examples |
|-------|--------|---------|---------|
| RED | `#ba1a1a` | Life-threatening | AMI, stroke, anaphylaxis, GCS<8 |
| YELLOW | `#e07b26` | Urgent | High fever, moderate pain, hypertensive crisis |
| GREEN | `#006a68` | Routine | Mild symptoms, chronic follow-up, URTI |

---

## 🔒 Trust Layer

Every triage response includes clinical transparency fields:

```json
{
  "evidence": ["Chest pain radiating to left arm", "Diaphoresis"],
  "guideline_sources": ["MTS — Chest Pain Protocol", "CTAS Level 1"],
  "doctor_review_required": true,
  "unsafe_to_self_manage": true
}
```

---

## 📝 Important Notes

- **Data Privacy:** All data stays in memory for the session duration — nothing written to remote storage
- **License:** CC-BY 4.0 (required if competition winner)
- **Fine-tuning:** Not required for hackathon — zero-shot is sufficient
- **Legal:** California law applies (competition rules)
