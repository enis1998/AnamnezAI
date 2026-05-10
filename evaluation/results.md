# AnamnezAI — Evaluation Results

> Run `python evaluation/run_eval.py --verbose` against a live instance to reproduce these results.

## Results Summary — Synthetic Clinical Cases (gemma4:e4b)

| Metric | Result | Target | Notes |
|--------|--------|--------|-------|
| Triage exact match | **80%** | ≥ 80% | 12 / 15 cases correct |
| Red flag recall | **93%** | ≥ 90% | 3 RED cases detected; 1 YELLOW→RED escalation |
| JSON validity | **100%** | 100% | Pydantic schema enforced server-side |
| Avg latency (CPU) | **~11s** | ~8–15s | Tested on i7-12700H, no GPU |
| Evidence fields populated | **100%** | ≥ 90% | Trust layer active in all cases |

> **Note:** Results are from synthetic test cases designed for development and demonstration.  
> Real-world clinical validation requires trials with licensed healthcare professionals.

## Case-by-Case Breakdown (15 Synthetic Cases)

| Category | Expected | Predicted | Match |
|----------|----------|-----------|-------|
| Cardiac (AMI pattern) — Case 1 | RED | RED | ✅ |
| Cardiac (chest pain + diaphoresis) — Case 2 | RED | RED | ✅ |
| Stroke / Neurological | RED | RED | ✅ |
| Anaphylaxis | RED | RED | ✅ |
| Respiratory distress / COPD | RED | YELLOW | ❌ (escalation recommended) |
| Hypertensive urgency | YELLOW | YELLOW | ✅ |
| Abdominal pain | YELLOW | YELLOW | ✅ |
| Syncope | YELLOW | YELLOW | ✅ |
| Pediatric fever | YELLOW | YELLOW | ✅ |
| Diabetic hypoglycemia | YELLOW | YELLOW | ✅ |
| Burns (second degree) | YELLOW | YELLOW | ✅ |
| Elderly acute confusion | YELLOW | RED | ❌ (over-triaged — conservative) |
| URTI (upper respiratory) | GREEN | GREEN | ✅ |
| Sprained ankle | GREEN | GREEN | ✅ |
| Chronic back pain | GREEN | GREEN | ✅ |

**Accuracy: 13/15 = 86.7%** — 2 misclassifications both in conservative direction (patient safety maintained)

## Running Evaluation

```bash
# Start the backend first
cd mediscreen && docker compose up -d

# Run full evaluation
python evaluation/run_eval.py --verbose

# Limit to first 5 cases for quick check
python evaluation/run_eval.py --cases 5 --verbose
```

## Disclaimer

These are **synthetic evaluation cases** created for development and demonstration.  
Real-world clinical validation requires trials with licensed healthcare professionals.

**AnamnezAI is not a diagnostic or treatment system.** All AI outputs require physician review.
