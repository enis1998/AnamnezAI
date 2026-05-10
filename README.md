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
| **AI Interview** | 5–7 turn adaptive symptom interview powered by Gemma 4 |
| **Triage Classification** | Manchester Triage System (MTS) — RED / YELLOW / GREEN |
| **Trust Layer** | Clinical evidence list, guideline sources (MTS/CTAS), `doctor_review_required` flag |
| **RAG Context** | ChromaDB + multilingual-MiniLM-L12-v2 — **92 built-in medical guideline chunks** (MTS, ICD-10, Cardiac, Neuro, Pediatric, ENT, Dermatology, emergency protocols) |
| **Fully Offline Frontend** | No CDN dependencies — jsPDF & html2canvas bundled locally in `frontend/vendor/` |
| **FHIR R4 Export** | Machine-readable clinical report export |
| **ICD-10 Auto-coding** | Suggested diagnostic codes per session |
| **Medical Image Analysis** | MedGemma Vision (`medgemma:4b`) — ECG, X-ray, skin conditions |
| **SSE Streaming** | Real-time clinical summary streamed to doctor panel |
| **Kiosk Mode** | Touch-optimised walk-in screen with QR queue ticket |
| **Offline PWA** | Service Worker — works without internet after first load |
| **4-Role Auth** | JWT — patient / doctor / staff / admin + Google OAuth2 |
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
│  gemma4:e4b   │  │  92 chunks       │  │  sessions            │
│  medgemma:4b  │  │  MiniLM-L12-v2  │  │  summaries           │
│  (optional)   │  │  MTS / ICD-10   │  │  users + roles       │
│               │  │  top-k cosine   │  │  audit_log           │
└───────────────┘  └──────────────────┘  └──────────────────────┘
⚡ All models run LOCALLY via Ollama — Zero API cost
⚡ Patient data never leaves the device — KVKK / GDPR compliant
⚡ Frontend JS libs bundled locally — zero CDN dependency for PDF export
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

### Without Docker (GPU recommended)

```bash
cd mediscreen/backend
pip install -r requirements.txt

# Set env vars and run (GPU inference via Ollama)
$env:OLLAMA_BASE_URL="http://localhost:11434"
$env:GEMMA_MODEL="gemma4:e4b"
$env:RAG_ENABLED="true"
$env:SECRET_KEY="your-secret-key"
python main.py
```

> **Note:** Gemma 4 e4b requires ~6.7 GiB of memory. With an 8 GB VRAM GPU and Ollama, it runs fully on GPU — no RAM pressure.

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
| `POST` | `/api/rag/ingest/builtin` | Load 92-chunk medical knowledge base |
| `GET` | `/api/rag/status` | RAG status + chunk count |
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

## 📊 Live Evaluation Results

Tested on Gemma 4 e4b via Ollama (GPU, `think: false`):

| Test Suite | Score | Detail |
|-----------|-------|--------|
| **Overall** | **86% (13/15)** | Live GPU run — RTX 8 GB VRAM |
| Triage decision accuracy | **5/5 (100%)** | AMI → RED@100%, Stroke → RED@98%, URTI → GREEN@95% |
| RAG retrieval accuracy | **5/6 (83%)** | Neurological 0.789, ENT 0.651, Dermatology 0.588 |
| Interview question quality | **2/3 (67%)** | OPQRST adherence confirmed |
| RAG + Triage integration | **1/1 (100%)** | Cardiac case → RED@98% with context augmentation |

```bash
# Run full evaluation (~15 min on GPU)
cd mediscreen
python evaluation/test_ai_quality.py

# Quick 3-case smoke test (~3 min)
python evaluation/quick_test.py
```

---

## ✅ Evidence Checklist

Every claim in this README can be verified independently:

| Claim | How to Verify |
|-------|---------------|
| Local Gemma 4 (no cloud) | `GET /api/offline-proof` → `cloud_api_keys_required: false` |
| RAG enabled (92 chunks) | `GET /api/rag/status` → `total_chunks: 92`, `enabled: true` |
| FHIR R4 export | `GET /api/session/{id}/fhir` → FHIR Bundle JSON |
| ICD-10 auto-coding | `GET /api/session/{id}/icd10` → `icd10_suggestions[]` |
| Doctor triage override | `/clinical_review.html` → Override panel (doctor login) |
| 4-role JWT auth | `POST /auth/login` with doctor / admin / patient accounts |
| Google OAuth2 | Click **Sign in with Google** on login page |
| Trust Layer (evidence) | `GET /api/session/{id}/summary` → `evidence[]`, `guideline_sources[]` |
| Offline PWA | Chrome DevTools → Network → Offline → reload page |
| Fully offline frontend | `frontend/vendor/` — jsPDF + html2canvas bundled, no CDN |
| Evaluation results | `python evaluation/test_ai_quality.py` — 86% score |

---

## 🧪 Evaluation & Testing

```bash
# Unit smoke tests (10 tests, no Ollama required)
cd mediscreen
pytest backend/tests/test_smoke.py -v

# Full AI quality test (4 suites: RAG, Triage, Questions, Integration)
python evaluation/test_ai_quality.py

# Quick 3-case triage sanity check
python evaluation/quick_test.py

# 15-case synthetic triage evaluation
python evaluation/run_eval.py --verbose
```

Target metrics: ≥ 80% triage accuracy ✅, ≥ 90% red-flag recall ✅, 100% JSON validity ✅

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
│   ├── rag.py               ← ChromaDB RAG engine (92 medical chunks)
│   ├── auth.py              ← JWT + Google OAuth2
│   └── requirements.txt
├── frontend/
│   ├── index.html           ← Patient interview (chat UI + landing)
│   ├── summary.html         ← Clinical report card (Trust Layer + PDF export)
│   ├── doctor.html          ← Doctor triage panel
│   ├── clinical_review.html ← Full clinical review + FHIR export
│   ├── kiosk.html           ← Kiosk touch mode
│   ├── admin.html           ← Admin dashboard (RAG, analytics, model test)
│   ├── patient_dashboard.html ← Patient history + profile
│   └── vendor/              ← Locally bundled JS (no CDN dependency)
│       ├── jspdf.umd.min.js     ← PDF export (2.5.1)
│       └── html2canvas.min.js   ← Canvas capture for PDF (1.4.1)
├── evaluation/
│   ├── triage_cases.jsonl   ← 15 synthetic test cases
│   ├── run_eval.py          ← 15-case evaluation runner
│   ├── quick_test.py        ← 3-case quick quality check
│   ├── test_ai_quality.py   ← Full AI quality suite (4 modules)
│   └── results.md           ← Latest evaluation results (86% / 13/15)
├── notebooks/
│   └── mediscreen_ai_kaggle.ipynb ← Kaggle demo notebook
├── kubernetes/
│   └── deployment.yaml      ← K8s deployment + HPA + Ingress
├── Dockerfile
├── docker-compose.yml
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
- ✅ **Fully offline** — no external AI APIs, no CDN JS dependencies, no data egress
- ✅ Open source — **CC-BY 4.0**
- ✅ No proprietary datasets or external AI APIs
- ✅ Live evaluation: **86% accuracy** (13/15 tests) on GPU hardware

---

## 📄 License

[CC-BY 4.0](https://creativecommons.org/licenses/by/4.0/) — AnamnezAI, Gemma 4 Good Hackathon 2026

