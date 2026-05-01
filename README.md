# ğŸ¥ AnamnezAI â€” MediScreen

> **AI-Powered Patient Pre-Triage System** â€” Gemma 4 running locally via Ollama

[![Gemma 4](https://img.shields.io/badge/Powered%20by-Gemma%204-4285F4?logo=google)](https://ollama.com/library/gemma4)
[![Ollama](https://img.shields.io/badge/Runtime-Ollama%20Local-black?logo=ollama)](https://ollama.com)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688)](https://fastapi.tiangolo.com)
[![License: CC-BY 4.0](https://img.shields.io/badge/License-CC--BY%204.0-green)](https://creativecommons.org/licenses/by/4.0/)
[![Hackathon](https://img.shields.io/badge/Gemma%204%20Good%20Hackathon-Health%20%26%20Ollama-orange)](https://www.kaggle.com/competitions/gemma-4-good-hackathon)

---

## ğŸ¯ The Problem

Every year, **millions of patients** in rural clinics, community health centers, and overwhelmed hospitals wait â€” sometimes critically â€” before a doctor even learns their symptoms. Traditional triage forms are static, cold, and provide zero clinical intelligence. When a 42-year-old woman says "my chest hurts," a paper form cannot ask: *"Does it radiate to your left arm?"*

**Doctors spend 15â€“20 minutes per patient just on history-taking** â€” time stolen from diagnosis.

---

## ğŸ’¡ The Solution: AnamnezAI

AnamnezAI deploys **Gemma 4 entirely on-device via Ollama** to conduct intelligent, empathetic pre-triage interviews *before* the patient reaches the doctor.

```
Patient                Gemma 4 (Local)           Doctor
  â”‚                         â”‚                       â”‚
  â”œâ”€â”€ Enters symptoms â”€â”€â”€â”€â”€â”€â–ºâ”‚                       â”‚
  â”‚                         â”œâ”€â”€ Dynamic Q1 â”€â”€â”€â”€â”€â”€â”€â”€â”€â–ºâ”‚? (generated)
  â”‚â—„â”€â”€ Contextual Q2 â”€â”€â”€â”€â”€â”€â”€â”¤                       â”‚
  â”œâ”€â”€ Answers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â–ºâ”‚                       â”‚
  â”‚         ... 5 turns ...  â”‚                       â”‚
  â”‚                         â”œâ”€â”€ Clinical Summary â”€â”€â”€â–ºâ”‚
  â”‚                         â””â”€â”€ Triage: ğŸ”´ RED â”€â”€â”€â”€â”€â–ºâ”‚ (priority queue)
```

**Key innovations:**
- ğŸ§  **Contextual AI interview** â€” Gemma 4 reads all previous answers and generates the next most clinically relevant question (not a static form)
- ğŸ”´ **Intelligent triage** â€” RED / YELLOW / GREEN with AI confidence score and urgency flags
- ğŸ™ï¸ **Voice input** â€” Web Speech API for elderly/low-literacy patients
- ğŸ”’ **100% local** â€” Gemma 4 runs on-device via Ollama; no patient data ever touches a cloud server
- ğŸŒ **Bilingual** â€” Turkish and English (expandable to any language)

---

## ğŸ† Hackathon Tracks

| Track | Prize | How AnamnezAI qualifies |
|---|---|---|
| **ğŸ¥ Health & Sciences** | $10,000 | Democratizes medical triage in underserved clinics |
| **ğŸ¦™ Ollama Prize** | $10,000 | Gemma 4 (`gemma4:e4b`) runs entirely locally via Ollama |

---

## ğŸ”’ Privacy-First Architecture

```
â”Œâ”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”
â”‚              AnamnezAI â€” Local Deployment              â”‚
â”‚                                                        â”‚
â”‚  Browser â”€â”€â–º FastAPI Backend â”€â”€â–º Ollama Server         â”‚
â”‚                                       â”‚                â”‚
â”‚                               Gemma 4 (gemma4:e4b)     â”‚
â”‚                                 On-device inference    â”‚
â”‚                                                        â”‚
â”‚  âœ… Zero data leaves the hospital network              â”‚
â”‚  âœ… Works fully offline                                â”‚
â”‚  âœ… HIPAA-friendly (no cloud dependencies)             â”‚
â”‚  âœ… Free at scale (one-time hardware cost)             â”‚
â””â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”˜
```

| Feature | Cloud AI (e.g. ChatGPT API) | AnamnezAI (Ollama) |
|---|---|---|
| Patient data privacy | âŒ Sent to cloud | âœ… 100% local |
| Works offline | âŒ | âœ… |
| HIPAA compliance | âš ï¸ Complex contracts | âœ… Simplified |
| Rural / low-connectivity | âŒ | âœ… Edge-ready |
| Cost at scale | ğŸ’¸ Per API call | âœ… Free after hardware |

---

## ğŸš€ Quick Start

### Prerequisites
- [Ollama](https://ollama.com) installed
- Python 3.11+

### 1. Pull Gemma 4 & Start Ollama
```bash
# Pull Gemma 4 (choose based on your hardware)
ollama pull gemma4:e4b    # ~5GB â€” recommended (balanced speed/quality)
ollama pull gemma4:e2b    # ~3GB â€” fastest (lower RAM)
ollama pull gemma4:26b    # ~20GB â€” highest quality (powerful GPU)

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
# API â†’ http://localhost:8000
# Docs â†’ http://localhost:8000/docs
```

### 4. Open the App
```
frontend/index.html   â†’ Patient Interview
frontend/doctor.html  â†’ Doctor Dashboard
```

### Environment Variables
```bash
GEMMA_MODEL=gemma4:e4b          # Change model here
OLLAMA_BASE_URL=http://localhost:11434
```

---

## ğŸ“ Project Structure

```
AnamnezAI/
â”œâ”€â”€ README.md
â”œâ”€â”€ GEMMA4_MODEL_CARD.md          # Gemma 4 usage verification
â”œâ”€â”€ setup.ps1                     # One-click Windows setup
â”‚
â”œâ”€â”€ backend/
â”‚   â”œâ”€â”€ main.py                   # FastAPI + Gemma 4 via Ollama (v2)
â”‚   â””â”€â”€ requirements.txt
â”‚
â”œâ”€â”€ frontend/
â”‚   â”œâ”€â”€ index.html                # Patient interview UI (voice + text, TR/EN)
â”‚   â”œâ”€â”€ summary.html              # AI clinical summary with triage ring
â”‚   â””â”€â”€ doctor.html               # Doctor dashboard with priority queue
â”‚
â””â”€â”€ notebooks/
    â””â”€â”€ mediscreen_ai_kaggle.ipynb  # Kaggle submission notebook
```

---

## ğŸ§  How Gemma 4 is Used

### 3 Core AI Tasks

#### 1. Dynamic Interview Question Generation
Every question is generated by Gemma 4 based on the full conversation history â€” not a static form:
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
| ğŸ”´ **RED** | Life-threatening â€” immediate | Chest pain + arm radiation, stroke signs, respiratory failure |
| ğŸŸ¡ **YELLOW** | Urgent â€” seen within 2 hours | High fever, moderate pain, persistent symptoms |
| ğŸŸ¢ **GREEN** | Routine â€” outpatient referral | Mild symptoms, chronic follow-up, common cold |

---

## ğŸ”Œ API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Ollama + Gemma 4 status check |
| `POST` | `/api/session/start` | Start interview (Gemma 4 generates Q1) |
| `POST` | `/api/session/answer` | Submit answer â†’ Gemma 4 generates next Q |
| `GET` | `/api/session/{id}/summary` | Generate clinical report (JSON) |
| `GET` | `/api/session/{id}/stream-summary` | Stream clinical narrative (SSE) |
| `GET` | `/api/patients/queue` | Prioritized patient queue |
| `DELETE` | `/api/session/{id}` | Delete session (HIPAA compliance) |

---

## ğŸ“Š Impact

| Metric | Impact |
|---|---|
| Doctor time saved | 15â€“20 min per patient on history-taking |
| Triage accuracy | AI confidence score + urgency flags guide priority |
| Accessibility | Voice input for elderly / low-literacy patients |
| Deployment | Works in clinics with no internet (fully offline) |
| Cost | $0 marginal cost per patient after hardware |
| Languages | Turkish + English (any language via Gemma 4) |

**Real-world scenario:** A rural clinic in Turkey with 1 doctor and 40 patients/day. AnamnezAI runs on a laptop, pre-triages all patients before the doctor arrives, and surfaces the 3 critical cases immediately.

---

## ğŸ¨ Design System

**"The Empathetic Guardian"** â€” A high-end editorial design language for medical tech:
- Colors: Deep navy (`#002f40`) + healing teal (`#006a68`) â€” WCAG 2.1 AA compliant
- Typography: Manrope (headlines) + Inter (body)
- Patterns: Glassmorphism, tonal layering, no harsh borders
- Accessibility: Touch targets â‰¥ 48dp, contrast ratio â‰¥ 4.5:1
- Philosophy: "One Task Per Screen" â€” reduces cognitive load in stressful medical situations

---

## ğŸ”¬ Reproducing Results

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

## ğŸ“œ License

**CC-BY 4.0** â€” Free to use, modify, and distribute with attribution.

---

## âš ï¸ Medical Disclaimer

AnamnezAI is a **clinical decision support tool** for pre-triage only. It does not replace professional medical diagnosis. All AI-generated content must be reviewed by a qualified healthcare provider before clinical decisions are made.

[![Ollama](https://img.shields.io/badge/Runtime-Ollama-black)](https://ollama.com)
[![License: CC-BY 4.0](https://img.shields.io/badge/License-CC--BY%204.0-green)](https://creativecommons.org/licenses/by/4.0/)

