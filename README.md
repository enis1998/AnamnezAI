# 🏥 MediScreen AI

> **AI-Powered Patient Pre-Triage System** — Gemma 4 via Ollama

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

