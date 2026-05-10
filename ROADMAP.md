# AnamnezAI — Roadmap

> **Competition:** Gemma 4 Good Hackathon — Health & Sciences ($10K) + Ollama Prize ($10K)  
> **Model:** `gemma4:e4b` (primary) + `medgemma:4b` (Vision — optional)  
> **Last Updated:** May 2026

---

## ✅ Implemented Features

| Feature | Status |
|---------|--------|
| FastAPI + Ollama/Gemma 4 backend, MTS system prompt, SSE streaming | ✅ |
| Glassmorphism UI, animated SVG confidence ring, triage colour cards, Docker | ✅ |
| Kiosk mode, QR queue ticket, Kaggle notebook | ✅ |
| Mobile responsive UI, patient dashboard, bottom-sheet nav | ✅ |
| `clinical_review.html` — FHIR R4 export, ICD-10 table, doctor notes | ✅ |
| RAG: ChromaDB + all-MiniLM-L6-v2 + PDF ingest API + dynamic context | ✅ |
| Rate limiting (slowapi), session TTL, audit log, Kubernetes manifests | ✅ |
| JWT auth — 4 roles, Google OAuth2, clinic code, demo users | ✅ |
| Web Speech TTS/STT, Service Worker (offline PWA), Chart.js analytics | ✅ |
| MedGemma Vision — `/api/analyze-image`, image_findings, fallback | ✅ |
| Profile SPA merged into patient_dashboard | ✅ |
| Demo reliability: warmup, session cleanup, think-block buffer | ✅ |
| Gemma 4 thinking-mode animation, model status card | ✅ |
| RAG: expanded Turkish medical guidelines, ICD-10 TR coding guide | ✅ |
| Admin panel: RAG document management, model test tab | ✅ |
| Trust Layer: `evidence[]`, `guideline_sources[]`, `doctor_review_required` | ✅ |
| `/api/offline-proof` endpoint, CI syntax check, smoke tests (9) | ✅ |
| Evaluation suite — 15 synthetic triage cases | ✅ |

---

## 🛠️ System Architecture

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

## 📊 Hackathon Score Estimate

```
Technical Depth      ████████████ 9/10  — RAG + FHIR + SSE + Vision
Gemma 4 Usage        ████████████ 9/10  — e4b primary + MedGemma optional
Ollama Compliance    ████████████ 10/10 — Fully local, zero API cost
Real-world Impact    ████████████ 9/10  — Turkey public health, 117M annual visits
Demo Quality         █████████░░░ 9/10  — Stable demo, Trust Layer
Code & Docs          ████████████ 9/10  — Tests, eval suite, full English docs
─────────────────────────────────────────────────────────
ESTIMATED TOTAL      ████████████ ~9.2/10 → 🏆 Top 3 potential
```

---

## 🌍 Post-Hackathon Vision

| Period | Goal |
|--------|------|
| **Q3 2026** | Turkey Ministry of Health pilot (2 primary care clinics) |
| **Q3 2026** | Arabic + Kurdish language support via Gemma 4 multilingual capacity |
| **Q4 2026** | PostgreSQL migration — multi-clinic shared data |
| **Q4 2026** | Doctor mobile app (React Native) — SSE queue on phone |
| **Q1 2027** | Full FHIR R4 API server — hospital HIS system integration |
| **Q1 2027** | Gemma 4 fine-tuning on Turkish clinical dataset |
| **2027** | Middle East / Central Asia — low-resource healthcare system partners |

---

## ⚡ Quick Start

```bash
# 1. Pull the model (~9.6 GB)
ollama pull gemma4:e4b
# Optional: Vision analysis
# ollama pull medgemma:4b

# 2. Start the project
cd mediscreen
docker compose up --build -d

# 3. Open in browser
# http://localhost:8000              → Patient interview
# http://localhost:8000/doctor.html → Doctor panel
# http://localhost:8000/kiosk.html  → Kiosk mode
```

## 👤 Demo Users

| Role | Email | Password | Scope |
|------|-------|----------|-------|
| Doctor | `doctor@anamnezai.tr` | `doctor123` | Triage queue, clinical review, override |
| Admin | `admin@anamnezai.tr` | `admin123` | Analytics, audit log, CSV export, RAG |
| New Doctor | Any email | — | Clinic code: **DEMO2026** |
| Patient | Register at `register.html` | — | Interview, history, profile |

---

*AnamnezAI — Gemma 4 Good Hackathon 2026 | Health & Sciences ($10K) + Ollama Prize ($10K)*
