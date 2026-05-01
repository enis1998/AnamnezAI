# 🏥 AnamnezAI — MediScreen

> **AI-Powered Patient Pre-Triage System** — Gemma 4 running locally via Ollama

[![Gemma 4](https://img.shields.io/badge/Powered%20by-Gemma%204-4285F4?logo=google)](https://ollama.com/library/gemma4)
[![Ollama](https://img.shields.io/badge/Runtime-Ollama%20Local-black?logo=ollama)](https://ollama.com)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688)](https://fastapi.tiangolo.com)
[![License: CC-BY 4.0](https://img.shields.io/badge/License-CC--BY%204.0-green)](https://creativecommons.org/licenses/by/4.0/)
[![Hackathon](https://img.shields.io/badge/Gemma%204%20Good%20Hackathon-Health%20%26%20Ollama-orange)](https://www.kaggle.com/competitions/gemma-4-good-hackathon)

---

## 🎯 The Problem

Every year, **millions of patients** in rural clinics, community health centers, and overwhelmed hospitals wait — sometimes critically — before a doctor even learns their symptoms. Traditional triage forms are static, cold, and provide zero clinical intelligence. When a 42-year-old woman says "my chest hurts," a paper form cannot ask: *"Does it radiate to your left arm?"*

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
- 🎙️ **Voice input** — Web Speech API for elderly/low-literacy patients
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

## 🔌 API Reference

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

**"The Empathetic Guardian"** — A high-end editorial design language for medical tech:
- Colors: Deep navy (`#002f40`) + healing teal (`#006a68`) — WCAG 2.1 AA compliant
- Typography: Manrope (headlines) + Inter (body)
- Patterns: Glassmorphism, tonal layering, no harsh borders
- Accessibility: Touch targets ≥ 48dp, contrast ratio ≥ 4.5:1
- Philosophy: "One Task Per Screen" — reduces cognitive load in stressful medical situations

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


[![Gemma 4](https://img.shields.io/badge/Powered%20by-Gemma%204-blue)](https://ollama.com/library/gemma3)
[![Ollama](https://img.shields.io/badge/Runtime-Ollama-black)](https://ollama.com)
[![License: CC-BY 4.0](https://img.shields.io/badge/License-CC--BY%204.0-green)](https://creativecommons.org/licenses/by/4.0/)

---

## 🎯 Problem

Healthcare systems face a critical bottleneck: patients wait too long before a doctor even knows their symptoms. In rural and underserved areas, this delay can be life-threatening. Traditional triage forms are static, slow, and provide no AI insight to the doctor.

## 💡 Solution

**MediScreen AI** runs **Gemma 4 locally via Ollama** to:

1. Conduct intelligent **conversational pre-triage interviews** (voice + text)
2. Generate **AI clinical summaries** with triage priority (RED / YELLOW / GREEN)
3. Present doctors a **prioritized patient queue** with ready-made reports

```
Patient → AI Interview (Gemma 4) → Clinical Summary → Doctor Dashboard
```

## 🔒 Privacy-First Architecture

All processing happens **100% locally** via Ollama. No patient data ever leaves the hospital network.

| Feature | Cloud AI | MediScreen AI (Ollama) |
|---|---|---|
| Patient data privacy | ❌ Sent to cloud | ✅ 100% local |
| Works offline | ❌ | ✅ Edge-ready |
| HIPAA-friendly | ⚠️ Complex | ✅ Simplified |
| Rural deployment | ❌ Needs internet | ✅ Works anywhere |
| Cost at scale | 💸 Per API call | ✅ Free after hardware |

---

## 🏆 Hackathon Prize Tracks

| Track | Prize | Why MediScreen qualifies |
|---|---|---|
| **Health & Sciences** | $10,000 | Democratizes medical triage globally |
| **Ollama Prize** | $10,000 | Gemma 4 runs entirely locally via Ollama |

---

## 🚀 Quick Start

### Prerequisites
- [Ollama](https://ollama.com) installed
- Python 3.11+

### 1. Install & Run Ollama
```bash
# Pull Gemma 4 model
ollama pull gemma3:12b      # ~8GB — recommended
# or for low-resource devices:
ollama pull gemma3:4b       # ~3GB — faster

# Start Ollama server
ollama serve
```

### 2. Backend Setup
```bash
cd mediscreen/backend
pip install -r requirements.txt
python main.py
# → API running at http://localhost:8000
# → Docs at http://localhost:8000/docs
```

### 3. Open Frontend
```
Open mediscreen/frontend/index.html in your browser
```

### 4. Environment Variables (optional)
```bash
OLLAMA_BASE_URL=http://localhost:11434   # default
GEMMA_MODEL=gemma3:12b                   # or gemma3:4b / gemma3:27b
```

---

## 📁 Project Structure

```
mediscreen/
├── backend/
│   ├── main.py              # FastAPI + Ollama integration
│   └── requirements.txt
├── frontend/
│   ├── index.html           # Patient interview UI
│   ├── summary.html         # Clinical summary view
│   └── doctor.html          # Doctor dashboard
└── notebooks/
    └── mediscreen_ai_kaggle.ipynb   # Kaggle submission notebook
```

---

## 🔌 API Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Ollama connection check |
| POST | `/api/session/start` | Start patient interview |
| POST | `/api/session/answer` | Submit answer → get next question |
| GET | `/api/session/{id}/summary` | Generate clinical summary |
| GET | `/api/patients/queue` | Get prioritized patient queue |
| DELETE | `/api/session/{id}` | Delete session (HIPAA) |

---

## 🧠 How It Works

### Interview Flow
```
1. Patient enters name, age, gender
2. POST /api/session/start → first question
3. Patient answers (text or voice)
4. POST /api/session/answer → Gemma 4 generates next question
5. Repeat 5 times
6. GET /api/session/{id}/summary → Gemma 4 generates clinical report
```

### Gemma 4 Prompt Strategy
- **Interview mode**: Dynamic follow-up questions based on conversation history
- **Triage mode**: Structured JSON output with confidence scoring
- **Bilingual**: Turkish (TR) and English (EN) support

### Triage Classification
| Level | Color | Meaning |
|---|---|---|
| 🔴 RED | `#ba1a1a` | Emergency — immediate attention |
| 🟡 YELLOW | `#dca26c` | Urgent — can wait briefly |
| 🟢 GREEN | `#006a68` | Routine — standard queue |

---

## 🎨 UI Design System

Design system: **"The Empathetic Guardian"**
- Colors: Deep blues + healing teals (WCAG 2.1 AA compliant)
- Fonts: Manrope (headlines) + Inter (body)
- Pattern: Glassmorphism, tonal layering, no harsh borders
- Accessibility: Touch targets ≥ 48dp, contrast ratio ≥ 4.5:1

---

## 📊 Impact

- **Doctors save 15-20 min** per patient on history-taking
- **AI triage** ensures critical patients seen first
- **Voice input** makes it accessible for elderly/low-literacy patients
- **Offline-first** design works in resource-constrained clinics
- **Multi-language** support enables global deployment

---

## 📜 License

**CC-BY 4.0** — Free to use, modify, and distribute with attribution.

---

## ⚠️ Medical Disclaimer

MediScreen AI is a **pre-triage assistance tool** only. It does not replace professional medical diagnosis. Always consult a qualified healthcare provider for medical decisions.

