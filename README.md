# 🏥 AnamnezAI — MediScreen

> **AI-Powered Patient Pre-Triage System** — Gemma 4 running locally via Ollama

[![Gemma 4](https://img.shields.io/badge/Powered%20by-Gemma%204-4285F4?logo=google)](https://ollama.com/library/gemma4)
[![Ollama](https://img.shields.io/badge/Runtime-Ollama%20Local-black?logo=ollama)](https://ollama.com)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688)](https://fastapi.tiangolo.com)
[![License: CC-BY 4.0](https://img.shields.io/badge/License-CC--BY%204.0-green)](https://creativecommons.org/licenses/by/4.0/)
[![Hackathon](https://img.shields.io/badge/Gemma%204%20Good%20Hackathon-Health%20%26%20Ollama-orange)](https://www.kaggle.com/competitions/gemma-4-good-hackathon)

---

## 🎯 The Problem

Every year, **millions of patients** in rural clinics, community health centers, and overwhelmed hospitals wait — sometimes critically — before a doctor even learns their symptoms. Traditional triage forms are static, cold, and provide zero clinical intelligence. When a 42-year-old woman says “my chest hurts,” a paper form cannot ask: *“Does it radiate to your left arm?”*

**Doctors spend 15–20 minutes per patient just on history-taking** — time stolen from diagnosis.

---

## 💡 The Solution: AnamnezAI

AnamnezAI deploys **Gemma 4 entirely on-device via Ollama** to conduct intelligent, empathetic pre-triage interviews *before* the patient reaches the doctor.

```
Patient                Gemma 4 (Local)           Doctor
  │                         │                       │
  ├── Enters symptoms ──────►│                       │
  │                         ├── Dynamic Q1 ─────────►│? (generated)
  │◄── Contextual Q2 ───────┤                       │
  ├── Answers ──────────────►│                       │
  │         ... 5 turns ...  │                       │
  │                         ├── Clinical Summary ───►│
  │                         └── Triage: 🔴 RED ─────►│ (priority queue)
```

**Key innovations:**
- 🧠 **Contextual AI interview** — Gemma 4 reads all previous answers and generates the next most clinically relevant question (not a static form)
- 🔴 **Intelligent triage** — RED / YELLOW / GREEN with AI confidence score and urgency flags
- 🏙️ **Voice input** — Web Speech API for elderly/low-literacy patients
- 🔒 **100% local** — Gemma 4 runs on-device via Ollama; no patient data ever touches a cloud server
- 🌍 **Bilingual** — Turkish and English (expandable to any language)

---

## 🏆 Hackathon Tracks

| Track | Prize | How AnamnezAI qualifies |
|---|---|---|
| **🏥 Health & Sciences** | $10,000 | Democratizes medical triage in underserved clinics |
| **🦙 Ollama Prize** | $10,000 | Gemma 4 (`gemma4:e4b`) runs entirely locally via Ollama |

---

## 🔒 Privacy-First Architecture

```
┌──────────────────────────────────────────────────────┐
│              AnamnezAI — Local Deployment              │
│                                                        │
│  Browser ──► FastAPI Backend ──► Ollama Server         │
│                                       │                │
│                               Gemma 4 (gemma4:e4b)     │
│                                 On-device inference    │
│                                                        │
│  ✅ Zero data leaves the hospital network              │
│  ✅ Works fully offline                                │
│  ✅ HIPAA-friendly (no cloud dependencies)             │
│  ✅ Free at scale (one-time hardware cost)             │
└──────────────────────────────────────────────────────┘
```

| Feature | Cloud AI (e.g. ChatGPT API) | AnamnezAI (Ollama) |
|---|---|---|
| Patient data privacy | ❌ Sent to cloud | ✅ 100% local |
| Works offline | ❌ | ✅ |
| HIPAA compliance | ⚠️ Complex contracts | ✅ Simplified |
| Rural / low-connectivity | ❌ | ✅ Edge-ready |
| Cost at scale | 💸 Per API call | ✅ Free after hardware |

---

## 🚀 Quick Start

### Prerequisites
- [Ollama](https://ollama.com) installed
- Python 3.11+

### 1. Pull Gemma 4 & Start Ollama
```bash
# Pull Gemma 4 (choose based on your hardware)
ollama pull gemma4:e4b    # ~5GB — recommended (balanced speed/quality)
ollama pull gemma4:e2b    # ~3GB — fastest (lower RAM)
ollama pull gemma4:26b    # ~20GB — highest quality (powerful GPU)

# Ollama starts automatically, or run manually:
ollama serve
```

### 2. Run with Setup Script (Windows)
```powershell
cd AnamnezAI
.\setup.ps1
# Auto-installs dependencies, checks Ollama, opens browser
```

### 3. Manual Setup
```bash
cd backend
pip install -r requirements.txt
python main.py
# API → http://localhost:8000
# Docs → http://localhost:8000/docs
```

### 4. Open the App
```
frontend/index.html   → Patient Interview
frontend/doctor.html  → Doctor Dashboard
```

### Environment Variables
```bash
GEMMA_MODEL=gemma4:e4b          # Change model here
OLLAMA_BASE_URL=http://localhost:11434
```

---

## 📁 Project Structure

```
AnamnezAI/
├── README.md
├── GEMMA4_MODEL_CARD.md          # Gemma 4 usage verification
├── setup.ps1                     # One-click Windows setup
│
├── backend/
│   ├── main.py                   # FastAPI + Gemma 4 via Ollama (v2)
│   └── requirements.txt
│
├── frontend/
│   ├── index.html                # Patient interview UI (voice + text, TR/EN)
│   ├── summary.html              # AI clinical summary with triage ring
│   └── doctor.html               # Doctor dashboard with priority queue
│
└── notebooks/
    └── mediscreen_ai_kaggle.ipynb  # Kaggle submission notebook
```

---

## 🧠 How Gemma 4 is Used

### 3 Core AI Tasks

#### 1. Dynamic Interview Question Generation
Every question is generated by Gemma 4 based on the full conversation history — not a static form:
```python
# Gemma 4 sees ALL previous Q&A pairs and generates next question
next_question = await ask_gemma(
    f"Interview history:\n{history_text}\n\n"
    f"Ask the NEXT most critical question to clarify the diagnosis.",
    system=SYSTEM_PROMPT_TR
)
```

#### 2. Clinical Summary + Triage Classification
After 5 turns, Gemma 4 produces a structured JSON report:
```json
{
  "triage_level": "RED",
  "confidence_score": 94,
  "chief_complaint": "Acute chest pain radiating to left arm",
  "possible_conditions": ["Myocardial Infarction", "Unstable Angina", "Pulmonary Embolism"],
  "recommended_action": "Immediate cardiology consultation, ECG, troponin panel",
  "urgency_flags": ["Cardiac risk factors present", "Classic MI presentation"]
}
```

#### 3. Streaming Clinical Narrative (SSE)
Gemma 4 streams a human-readable clinical summary token-by-token for the doctor dashboard.

### Triage Classification
| Level | Meaning | Examples |
|---|---|---|
| 🔴 **RED** | Life-threatening — immediate | Chest pain + arm radiation, stroke signs, respiratory failure |
| 🟡 **YELLOW** | Urgent — seen within 2 hours | High fever, moderate pain, persistent symptoms |
| 🟢 **GREEN** | Routine — outpatient referral | Mild symptoms, chronic follow-up, common cold |

---

## 📌 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Ollama + Gemma 4 status check |
| `POST` | `/api/session/start` | Start interview (Gemma 4 generates Q1) |
| `POST` | `/api/session/answer` | Submit answer → Gemma 4 generates next Q |
| `GET` | `/api/session/{id}/summary` | Generate clinical report (JSON) |
| `GET` | `/api/session/{id}/stream-summary` | Stream clinical narrative (SSE) |
| `GET` | `/api/patients/queue` | Prioritized patient queue |
| `DELETE` | `/api/session/{id}` | Delete session (HIPAA compliance) |

---

## 📊 Impact

| Metric | Impact |
|---|---|
| Doctor time saved | 15–20 min per patient on history-taking |
| Triage accuracy | AI confidence score + urgency flags guide priority |
| Accessibility | Voice input for elderly / low-literacy patients |
| Deployment | Works in clinics with no internet (fully offline) |
| Cost | $0 marginal cost per patient after hardware |
| Languages | Turkish + English (any language via Gemma 4) |

**Real-world scenario:** A rural clinic in Turkey with 1 doctor and 40 patients/day. AnamnezAI runs on a laptop, pre-triages all patients before the doctor arrives, and surfaces the 3 critical cases immediately.

---

## 🎨 Design System

**“The Empathetic Guardian”** — A high-end editorial design language for medical tech:
- Colors: Deep navy (`#002f40`) + healing teal (`#006a68`) — WCAG 2.1 AA compliant
- Typography: Manrope (headlines) + Inter (body)
- Patterns: Glassmorphism, tonal layering, no harsh borders
- Accessibility: Touch targets ≥ 48dp, contrast ratio ≥ 4.5:1
- Philosophy: “One Task Per Screen” — reduces cognitive load in stressful medical situations

---

## 🔬 Reproducing Results

```bash
# 1. Pull Gemma 4
ollama pull gemma4:e4b

# 2. Verify model
curl http://localhost:8000/health
# Expected: {"gemma_model":"gemma4:e4b","gemma_available":true}

# 3. Run full demo
# Open: notebooks/mediscreen_ai_kaggle.ipynb
# All cell outputs show Gemma 4 generating real clinical summaries
```

---

## 📜 License

**CC-BY 4.0** — Free to use, modify, and distribute with attribution.

---

## ⚠️ Medical Disclaimer

AnamnezAI is a **clinical decision support tool** for pre-triage only. It does not replace professional medical diagnosis. All AI-generated content must be reviewed by a qualified healthcare provider before clinical decisions are made.

[![Ollama](https://img.shields.io/badge/Runtime-Ollama-black)](https://ollama.com)
[![License: CC-BY 4.0](https://img.shields.io/badge/License-CC--BY%204.0-green)](https://creativecommons.org/licenses/by/4.0/)
