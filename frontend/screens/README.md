# AnamnezAI — Demo Screenshots

This folder contains demo screenshots of AnamnezAI.

## Expected Files

| File | Content |
|------|---------|
| `interview.png` | AI interview screen (chest pain scenario, context-aware question) |
| `triage_result.png` | RED triage card (animated SVG, 94% confidence, urgency flags) |
| `icd10.png` | ICD-10 auto-coding table |
| `vision_analysis.png` | MedGemma ECG analysis result |
| `doctor_queue.png` | SSE live triage queue (RED/YELLOW/GREEN) |
| `clinical_review.png` | Full clinical review + FHIR export button |
| `kiosk.png` | Kiosk touch mode (QR ticket visible) |
| `admin_analytics.png` | Chart.js analytics dashboard |
| `patient_dashboard.png` | Patient overview panel |
| `patient_profile.png` | Medical profile SPA section |

## Demo Steps (Taking Screenshots)

```bash
# 1. Start the application
cd mediscreen
docker compose up --build -d

# 2. Open http://localhost:8000 in browser
# 3. Run through a chest pain scenario interview
# 4. Take a screenshot of each screen
# 5. Save to this folder
```

> Real screenshots should be added to this folder during the demo session.
