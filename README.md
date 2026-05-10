# AnamnezAI — AI-Powered Medical Pre-Triage Platform

> **Gemma 4 Good Hackathon 2026 — Health & Sciences ($10K) + Ollama Prize ($10K)**

AnamnezAI automates hospital pre-triage using **Gemma 4 (gemma4:e4b)** running fully locally via **Ollama**. Patients complete a 5-turn AI interview; doctors receive a prioritised triage queue with structured clinical reports — all without a single byte of patient data leaving the device.

---

## ⚠️ Safety Disclaimer

**AnamnezAI is not a diagnostic or treatment system.** All AI-generated outputs are decision-support tools and must be reviewed by a licensed healthcare professional before any clinical action is taken.

---

## ✨ Key Features

| Feature | Detail |
|---------|--------|
| **AI Interview** | 5-turn context-aware symptom interview powered by Gemma 4 |
| **Triage Classification** | Manchester Triage System (MTS) — RED / YELLOW / GREEN |
| **Trust Layer** | Clinical evidence list, guideline sources (MTS/CTAS), `doctor_review_required` flag |
| **RAG Context** | ChromaDB + all-MiniLM-L6-v2 — ~810 chunks of medical guidelines |
| **FHIR R4 Export** | Machine-readable clinical report export |
| **ICD-10 Auto-coding** | Suggested diagnostic codes per session |
| **Medical Image Analysis** | MedGemma Vision (`medgemma:4b`) — ECG, X-ray, skin conditions |
| **SSE Streaming** | Real-time clinical summary streamed to doctor panel |
| **Kiosk Mode** | Touch-optimised walk-in screen with QR queue ticket |
| **Offline PWA** | Service Worker — works without internet after first load |
| **4-Role Auth** | JWT — patient / doctor / nurse / admin + Google OAuth2 |
| **Bilingual** | Turkish 🇹🇷 and English 🇬🇧 throughout |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER LAYER                              │
│  ┌──────────┐  ┌───────────┐  ┌───────────────┐  ┌──────────┐  │
│  │   Web    │  │   Kiosk   │  │    Doctor     │  │  Admin   │  │
│  │ (Patient)│  │  TR / EN  │  │  SSE Queue    │  │Analytics │  │
│  │ PWA+TTS  │  │ QR+touch  │  │  Override     │  │ Chart.js │  │
│  └────┬─────┘  └─────┬─────┘  └───────┬───────┘  └────┬─────┘  │
│       └──────────────┴────────────────┴───────────────┘        │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP / SSE
┌────────────────────────────▼────────────────────────────────────┐
│                   FastAPI Backend v5.0                          │
│   JWT Auth │ Rate Limit (200/min) │ Audit Log │ SSE │ FHIR R4  │
└──────────┬───────────────┬──────────────────┬───────────────────┘
           │               │                  │
┌──────────▼────┐  ┌───────▼──────────┐  ┌───▼──────────────────┐
│    Ollama     │  │    ChromaDB      │  │       SQLite         │
│  gemma4:e4b   │  │  ~810 chunks     │  │  sessions            │
│  medgemma:4b  │  │  all-MiniLM-L6   │  │  summaries           │
│  (optional)   │  │  MTS / ICD-10    │  │  users + roles       │
│               │  │  top-k cosine    │  │  audit_log           │
└───────────────┘  └──────────────────┘  └──────────────────────┘
⚡ All models run LOCALLY via Ollama — Zero API cost
⚡ Patient data never leaves the device — KVKK / GDPR compliant
```

---

## 🚀 Quick Start

### Prerequisites
- [Docker](https://docker.com) + Docker Compose
- [Ollama](https://ollama.com) installed and running

```bash
# 1. Pull the model (~9.6 GB)
ollama pull gemma4:e4b

# Optional — medical image analysis
# ollama pull medgemma:4b

# 2. Clone and start
git clone https://github.com/enis1998/AnamnezAI.git
cd AnamnezAI/mediscreen
docker compose up --build -d

# 3. Open in browser
# http://localhost:8000              → Patient interview
# http://localhost:8000/doctor.html → Doctor triage panel
# http://localhost:8000/kiosk.html  → Kiosk mode
# http://localhost:8000/admin.html  → Admin dashboard
# http://localhost:8000/docs        → Swagger UI
```

### Without Docker

```bash
cd mediscreen/backend
pip install -r requirements.txt
python main.py
```

---

## 👤 Demo Accounts

| Role | Email | Password | Access |
|------|-------|----------|--------|
| Doctor | `doctor@anamnezai.tr` | `doctor123` | Triage queue, clinical review, override |
| Admin | `admin@anamnezai.tr` | `admin123` | Analytics, audit log, CSV export, RAG |
| New Doctor | Any email | — | Clinic code: **DEMO2026** |
| Patient | Register at `/register.html` | — | Interview, history, profile |

---

## 🔌 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Ollama + Gemma 4 connection status |
| `POST` | `/api/warmup` | Pre-warm Gemma 4 model |
| `POST` | `/api/session/start` | Start a new patient interview |
| `POST` | `/api/session/answer` | Submit answer, receive next question |
| `GET` | `/api/session/{id}/summary` | Clinical summary + triage (JSON) |
| `GET` | `/api/session/{id}/stream-summary` | SSE streaming clinical summary |
| `GET` | `/api/patients/queue` | Doctor triage queue |
| `GET` | `/api/offline-proof` | Proves fully offline operation |
| `POST` | `/api/analyze-image` | MedGemma medical image analysis |
| `DELETE` | `/api/session/{id}` | Delete session (GDPR right to erasure) |

---

## 🔒 Trust Layer

Every clinical summary includes structured evidence fields for transparency:

```json
{
  "triage_level": "RED",
  "confidence_score": 94,
  "evidence": ["Chest pain radiating to left arm", "Diaphoresis", "Hypotension"],
  "guideline_sources": ["MTS — Chest Pain Protocol", "CTAS Level 1"],
  "doctor_review_required": true,
  "unsafe_to_self_manage": true
}
```

---

## 🧪 Evaluation & Testing

```bash
# Smoke tests (9 tests)
cd mediscreen
pytest backend/tests/test_smoke.py -v

# Triage evaluation (15 synthetic clinical cases)
python evaluation/run_eval.py --verbose
```

Target metrics: ≥ 80% triage accuracy, ≥ 90% red-flag recall, 100% JSON validity.

---

## 🌍 Post-Hackathon Roadmap

| Period | Goal |
|--------|------|
| **Q3 2026** | Turkey Ministry of Health pilot (2 primary care clinics) |
| **Q3 2026** | Arabic + Kurdish language support via Gemma 4 multilingual |
| **Q4 2026** | PostgreSQL migration — multi-clinic shared data |
| **Q4 2026** | Doctor mobile app (React Native) — SSE queue on phone |
| **Q1 2027** | Full FHIR R4 API server — hospital HIS integration |
| **Q1 2027** | Gemma 4 fine-tuning on Turkish clinical dataset |
| **2027** | Middle East / Central Asia — low-resource healthcare partners |

---

## 📁 Project Structure

```
mediscreen/
├── backend/
│   ├── main.py              ← FastAPI + Gemma 4 (RAG, Auth, SSE, FHIR)
│   ├── rag.py               ← ChromaDB RAG engine
│   ├── auth.py              ← JWT + Google OAuth2
│   └── requirements.txt
├── frontend/
│   ├── index.html           ← Patient interview (chat UI + landing)
│   ├── summary.html         ← Clinical report card (Trust Layer)
│   ├── doctor.html          ← Doctor triage panel
│   ├── clinical_review.html ← Full clinical review + FHIR export
│   ├── kiosk.html           ← Kiosk touch mode
│   ├── admin.html           ← Admin dashboard (RAG, analytics, model test)
│   └── patient_dashboard.html ← Patient history + profile
├── evaluation/
│   ├── triage_cases.jsonl   ← 15 synthetic test cases
│   └── run_eval.py          ← Evaluation runner
├── notebooks/
│   └── mediscreen_ai_kaggle.ipynb ← Kaggle demo notebook
├── kubernetes/
│   └── deployment.yaml      ← K8s deployment + HPA + Ingress
├── Dockerfile
├── docker-compose.yml
├── .env.example             ← Environment variable template
├── GEMMA4_MODEL_CARD.md     ← Model usage verification for judges
├── PROJECT_PLAN.md          ← Technical specification
└── ROADMAP.md               ← Feature roadmap
```

---

## 🏆 Hackathon Compliance

- ✅ **Gemma 4** (`gemma4:e4b`) is the sole AI model for triage, interview, and reports
- ✅ Runs **locally via Ollama** — qualifies for Ollama Prize Track
- ✅ Real-world **health impact** — qualifies for Health & Sciences Track
- ✅ **MedGemma Vision** (`medgemma:4b`) for medical image analysis (optional)
- ✅ Open source — **CC-BY 4.0**
- ✅ No proprietary datasets or external AI APIs

---

## 📄 License

[CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/) — AnamnezAI, Gemma 4 Good Hackathon 2026

