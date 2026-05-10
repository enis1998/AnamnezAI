#!/usr/bin/env python3
"""
AnamnezAI — Hızlı Kalite Testi
Sadece 3 kritik vakayı test eder ve soruların/yanıtların mantığını gösterir.
"""
import asyncio
import httpx
import json
import time

BASE_URL = "http://localhost:8000"

# Test vakları: Göğüs ağrısı (RED), Üst yol enfeksiyonu (GREEN), Çocuk ateş (YELLOW)
QUICK_CASES = [
    {
        "case_id": "🔴 göğüs_ağrısı_58yaş_erkek",
        "patient": {"patient_name": "Ahmet Yılmaz", "age": 58, "gender": "Erkek", "language": "tr"},
        "answers": [
            "Sabahtan beri göğsümde ezici bir baskı hissediyorum",
            "Sol koluma ve çeneme yayılıyor",
            "10 üzerinden 9, çok şiddetli",
            "Evet nefes almakta zorlanıyorum, ter dökütüyorum",
            "Hipertansiyon ve diyabet hastasıyım",
        ],
        "expected": "RED"
    },
    {
        "case_id": "🟢 soğuk_algınlığı_25yaş_kadın",
        "patient": {"patient_name": "Elif Demir", "age": 25, "gender": "Kadın", "language": "tr"},
        "answers": [
            "2 gündür burun akıntısı ve hafif boğaz ağrısı var",
            "37.2 ateşim var, çok hafif",
            "Öksürük de var ama hafif, balgam yok",
            "Genel olarak yorgunum ama normal aktivitemi yapabiliyorum",
        ],
        "expected": "GREEN"
    },
    {
        "case_id": "🟡 çocuk_karın_ağrısı_10yaş",
        "patient": {"patient_name": "Can Yıldız (anne anlatıyor)", "age": 10, "gender": "Erkek", "language": "tr"},
        "answers": [
            "Oğlumun karın ağrısı var, sağ alt tarafı",
            "Dün gece başladı ve giderek artıyor",
            "37.8 ateş var, iştahsız",
            "Bulantı var, 1 kez kustu",
            "Hamilelik ihtimali yok, erkek çocuk",
        ],
        "expected": "YELLOW"
    }
]

async def run_quick_case(client: httpx.AsyncClient, case: dict) -> dict:
    start = time.monotonic()
    print(f"\n{'='*60}")
    print(f"VAKA: {case['case_id']}")
    print(f"Beklenen: {case['expected']}")
    print('='*60)

    # Session başlat
    r = await client.post(f"{BASE_URL}/api/session/start", json=case["patient"], timeout=60.0)
    r.raise_for_status()
    sd = r.json()
    sid = sd["session_id"]

    print(f"\n📋 SORU 1 (AI'nın açılış sorusu):")
    print(f"  → {sd['question']}")

    # Yanıtları gönder
    for i, ans in enumerate(case["answers"]):
        print(f"\n👤 HASTA CEVABI {i+1}: {ans}")
        r = await client.post(f"{BASE_URL}/api/session/answer",
                               json={"session_id": sid, "answer": ans}, timeout=60.0)
        r.raise_for_status()
        resp = r.json()
        if resp.get("question") == "__COMPLETED__":
            print(f"  ✅ Mülakat tamamlandı ({resp['step']}/{resp['total_steps']} soru)")
            break
        print(f"\n🤖 AI SORUSU {i+2}:")
        print(f"  → {resp['question']}")

    # Özet al
    print(f"\n{'─'*40}")
    print("🔬 KLİNİK DEĞERLENDIRME:")
    r = await client.get(f"{BASE_URL}/api/session/{sid}/summary", timeout=120.0)
    r.raise_for_status()
    summary = r.json()

    triage = summary.get("triage_level", "?")
    confidence = summary.get("confidence_score", 0)
    complaint = summary.get("chief_complaint", "?")
    conditions = summary.get("possible_conditions", [])
    flags = summary.get("urgency_flags", [])
    notes = summary.get("clinical_notes", "?")
    evidence = summary.get("evidence", [])

    match = "✅" if triage == case["expected"] else "❌"
    elapsed = time.monotonic() - start

    print(f"  Triaj: {match} {triage} (Beklenen: {case['expected']})")
    print(f"  Güven: %{confidence}")
    print(f"  Şikayet: {complaint}")
    print(f"  Olası tanılar: {', '.join(conditions[:3])}")
    if flags:
        print(f"  Acil bayraklar:")
        for f in flags:
            print(f"    ⚠️  {f}")
    print(f"  Klinik notlar: {notes}")
    if evidence:
        print(f"  Kanıt:")
        for e in evidence[:3]:
            print(f"    • {e}")
    print(f"  Süre: {elapsed:.1f}s")

    return {
        "case_id": case["case_id"],
        "expected": case["expected"],
        "got": triage,
        "match": triage == case["expected"],
        "confidence": confidence,
        "conditions": conditions,
        "flags": flags,
        "elapsed": elapsed,
    }


async def main():
    print("\n🧪 AnamnezAI — Hızlı Kalite Testi")
    print("Soruların ve triaj kararlarının mantığını doğruluyor...")

    # Health check
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{BASE_URL}/health", timeout=10.0)
        h = r.json()
        print(f"\n✅ Backend: {h.get('status')} | Model: {h.get('gemma_model')} | RAG chunks: {h.get('rag_chunks', 0)}")

        results = []
        for case in QUICK_CASES:
            try:
                result = await run_quick_case(client, case)
                results.append(result)
            except Exception as e:
                print(f"\n❌ HATA [{case['case_id']}]: {e}")
                results.append({"case_id": case["case_id"], "match": False, "error": str(e)})

    # Sonuç özeti
    print(f"\n{'='*60}")
    print("📊 SONUÇ ÖZETİ")
    print('='*60)
    matched = sum(1 for r in results if r.get("match"))
    total = len(results)
    print(f"Triaj doğruluk: {matched}/{total} = %{matched/total*100:.0f}")
    for r in results:
        icon = "✅" if r.get("match") else ("💥" if "error" in r else "❌")
        print(f"  {icon} {r['case_id']} | Beklenen: {r.get('expected','?')} | Alınan: {r.get('got','ERR')}")


if __name__ == "__main__":
    asyncio.run(main())

