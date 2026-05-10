# AnamnezAI — Evaluation Results

> **Note:** Run `python evaluation/run_eval.py --verbose` against a live instance to generate real metrics.

## Summary (Pre-run Estimates Based on Architecture)

| Metric | Target | Notes |
|--------|--------|-------|
| Triage exact match | ≥ 80% | gemma4:e4b with MTS system prompt |
| Red flag recall | ≥ 90% | Emergency keyword detection + AI |
| JSON validity | 100% | Pydantic schema enforced server-side |
| Avg latency (CPU) | ~8–15s | Depends on hardware |
| Evidence fields populated | ≥ 90% | Trust layer in triage prompt |

## Test Cases

15 synthetic clinical cases covering:

| Category | Cases | Triage Level |
|----------|-------|-------------|
| Cardiac (chest pain, AMI pattern) | 2 | RED |
| Stroke / Neurological | 1 | RED |
| Anaphylaxis | 1 | RED |
| Respiratory distress / COPD | 1 | RED |
| Hypertensive urgency | 1 | YELLOW |
| Abdominal pain | 1 | YELLOW |
| Syncope | 1 | YELLOW |
| Pediatric fever | 1 | YELLOW |
| Diabetic hypoglycemia | 1 | YELLOW |
| Burns (second degree) | 1 | YELLOW |
| Elderly acute confusion | 1 | YELLOW |
| URTI (upper respiratory) | 1 | GREEN |
| Sprained ankle | 1 | GREEN |
| Chronic back pain | 1 | GREEN |
| Migraine (known diagnosis) | 1 | GREEN |

## Running Evaluation

```bash
# Start the backend first
cd mediscreen && docker compose up -d

# Run evaluation
python evaluation/run_eval.py --verbose

# Limit to first 5 cases for quick check
python evaluation/run_eval.py --cases 5 --verbose
```

## Disclaimer

These are **synthetic evaluation cases** designed for development and demonstration purposes.
Real-world clinical validation requires trials with licensed healthcare professionals.

**AnamnezAI is not a diagnostic or treatment system.** All AI outputs require physician review.

