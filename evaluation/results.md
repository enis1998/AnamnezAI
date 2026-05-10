# AnamnezAI — Evaluation Results

> Generated: 2026-05-10 (live GPU run — Gemma 4 e4b on RTX 8 GB VRAM)
> Model: gemma4:e4b | Ollama local | RAG: ChromaDB 92 chunks

## Summary

| Metric | Value |
|--------|-------|
| Overall score | **86%** (13/15 tests passed) |
| RAG retrieval accuracy | **5/6** (83%) |
| Triage decision accuracy | **5/5** (100%) |
| Interview question quality | **2/3** (67%) |
| RAG + Triage integration | **1/1** (100%) |
| Avg inference latency | ~11–39s (GPU, thinking disabled) |
| ChromaDB chunks loaded | **92** |

## Triage Decision Results (5/5 correct)

| Case | Expected | Got | Confidence | Match |
|------|----------|-----|-----------|-------|
| 🔴 AMI — Acute Cardiac Emergency | RED | RED | 100% | ✅ |
| 🟡 High Fever Child (39.5°C) | YELLOW | YELLOW | 90% | ✅ |
| 🟢 Simple URTI | GREEN | GREEN | 95% | ✅ |
| 🔴 Stroke Suspicion | RED | RED | 98% | ✅ |
| 🟡 Abdominal Pain — Appendicitis | YELLOW | YELLOW | 90% | ✅ |

## RAG Retrieval Results (5/6 correct)

| Query | Expected Source | Found | Pass |
|-------|----------------|-------|------|
| Chest pain, radiation to left arm | Cardiac_Emergency, MTS | ENT_Emergency (miss) | ❌ |
| Infant 2 months fever 38.5 | Pediatric | Pediatric_Triage (0.581) | ✅ |
| Sudden severe headache neck stiffness | Neurological | Neurological_Emerg (0.789) | ✅ |
| Lower back pain, urinary retention | Orthopedic, Urology | Orthopedic_Triage (0.470) | ✅ |
| Rash fever petechiae | Dermatology | Dermatology_Triage (0.588) | ✅ |
| Ear pain child | ENT | ENT_Emergency (0.651) | ✅ |

## RAG + Triage Integration Test

- Query: chest pain, radiation to left arm, sweating, cardiac emergency
- Result: **RED @ 98% confidence** ✅ (RAG context correctly augmented model)
- Context size: 5541 characters from ChromaDB

## Interview Question Quality (2/3)

| Scenario | Question Asked | Clinically Relevant? |
|----------|---------------|---------------------|
| Chest pain (55M) | "Bu ağrı ne zaman başladı ve şiddeti 1-10 skalasında kaç? Ağrı göğsünün neresinde daha çok hissediliyor ve bu ağrı yayılıyor mu?" | ✅ (OPQRST, radiation) |
| Dizziness (42M) | "Bu baş dönmesi ne zaman başladı ve bu dönme hissi sürekli mi yoksa gelip geçici mi oluyor? Baş dönmesiyle birlikte mide bulantısı, kusma veya göğüs ağrısı gibi başka belirtiler var mı?" | ✅ (onset, associated sx) |
| Child fever (3F) | "Bu ateş ve halsizlik ne zamandır var, ve bu sırada kızınızın nefes almakta zorlandığı, göğsünde ağrı hissettiği veya bilinç bulanıklığı gibi acil belirtileri var mı?" | ❌ (should ask temperature first) |

## Key Findings

- **GPU inference works**: RTX 8 GB VRAM supports Gemma 4 e4b (7.9 GB loaded)
- **Triage is 100% accurate** on 5 clinical scenarios including critical RED flags (AMI, stroke)
- **RAG slightly weak** on cardiac chest pain retrieval — ENT chunk scored higher than Cardiac chunk
- **`think: false`** is essential — thinking model consumes all tokens without producing output

## Disclaimer

These are **synthetic evaluation cases** for development purposes.
Real-world accuracy requires clinical validation with licensed healthcare professionals.
AnamnezAI is not a diagnostic system — all outputs require physician review.