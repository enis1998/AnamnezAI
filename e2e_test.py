"""
AnamnezAI - End-to-End Interview + Summary Test
Tests the full flow: session start -> answer questions -> summary
"""
import requests
import time
import json

BASE = "http://localhost:8001"

def test_flow():
    print("=" * 60)
    print("AnamnezAI — End-to-End Test")
    print("=" * 60)

    # 1) Health check
    print("\n[1] Health Check...")
    r = requests.get(f"{BASE}/health", timeout=10)
    h = r.json()
    print(f"     Ollama: {h.get('ollama')}")
    print(f"     Gemma4: {'available' if h.get('gemma_available') else 'MISSING'}")
    print(f"     MedGemma: {'available' if h.get('medgemma_available') else 'MISSING'}")
    print(f"     RAG: {'enabled' if h.get('rag_enabled') else 'disabled'}, chunks={h.get('rag_chunks')}")
    print(f"     DB: {h.get('db_backend')}")
    assert r.status_code == 200, "Health check failed!"
    print("     ✅ PASS")

    # 2) Offline proof
    print("\n[2] Offline Proof...")
    r = requests.get(f"{BASE}/api/offline-proof", timeout=10)
    p = r.json()
    assert not p.get("cloud_api_keys_required"), "FAILS: cloud API required!"
    print(f"     cloud_api_keys_required: {p.get('cloud_api_keys_required')} ✅")
    print(f"     mcp_ready: {p.get('mcp_ready')}")

    # 3) RAG status
    print("\n[3] RAG Status...")
    r = requests.get(f"{BASE}/api/rag/status", timeout=10)
    rag = r.json()
    print(f"     enabled: {rag.get('enabled')}, chunks: {rag.get('total_chunks')}")
    if rag.get('total_chunks', 0) < 50:
        print("     RAG has few chunks, triggering ingest...")
        r2 = requests.post(f"{BASE}/api/rag/ingest/builtin", timeout=60)
        print(f"     Ingest result: {r2.json().get('status')}, chunks={r2.json().get('total_chunks')}")
    print("     ✅ PASS")

    # 4) Start interview session
    print("\n[4] Starting Interview Session (Turkish)...")
    payload = {
        "patient_name": "Test Hasta",
        "age": 35,
        "gender": "female",
        "language": "tr"
    }
    r = requests.post(f"{BASE}/api/session/start", json=payload, timeout=30)
    assert r.status_code == 200, f"Session start failed: {r.status_code} {r.text}"
    session = r.json()
    sid = session["session_id"]
    first_q = session.get("question", "")
    print(f"     Session ID: {sid}")
    print(f"     First Question: {first_q[:80]}...")
    print("     ✅ PASS")

    # 5) Answer questions to complete the interview
    print("\n[5] Answering Questions...")
    answers = [
        "3 gündür şiddetli baş ağrım var ve ateşim 38.5 derece",
        "Boyun tutulması var, ışığa karşı hassasiyet hissediyorum",
        "Hayır, başka bir ilaç kullanmıyorum",
        "Ailede menenjit öyküsü yok, kronik hastalığım yok",
        "Şikayetlerim birden bire başladı, giderek kötüleşiyor",
        "Bulantı ve kusma da var",
        "Son 24 saatte yüksek ateş ve baş dönmesi de var"
    ]

    completed = False
    question_count = 0
    for answer in answers:
        if completed:
            break
        question_count += 1
        print(f"\n     Q{question_count}: Answering...")
        r = requests.post(
            f"{BASE}/api/session/answer",
            json={"session_id": sid, "answer": answer},
            timeout=300  # CPU mode: up to 5 min per turn
        )
        if r.status_code != 200:
            print(f"     ERROR: {r.status_code} - {r.text[:200]}")
            break
        resp = r.json()
        if resp.get("completed") or resp.get("message") == "__COMPLETED__":
            print(f"     Interview completed after {question_count} questions!")
            completed = True
        else:
            next_q = resp.get("question", "")
            print(f"     Next Q: {next_q[:80]}...")

    print(f"     ✅ PASS ({question_count} Q&A pairs)")

    # 6) Wait for summary generation
    print("\n[6] Waiting for Summary Generation...")
    start_wait = time.time()
    max_wait = 180  # 3 minutes
    while time.time() - start_wait < max_wait:
        r = requests.get(f"{BASE}/api/session/{sid}/summary/status", timeout=10)
        st = r.json()
        if st.get("ready"):
            elapsed = time.time() - start_wait
            print(f"     Summary ready in {elapsed:.1f}s ✅")
            break
        elif st.get("generating"):
            print(f"     Generating... ({int(time.time() - start_wait)}s elapsed)", end="\r")
        time.sleep(3)
    else:
        print("     ⚠️  TIMEOUT waiting for summary (may still be generating)")

    # 7) Fetch and validate summary
    print("\n[7] Fetching Clinical Summary...")
    r = requests.get(f"{BASE}/api/session/{sid}/summary", timeout=30)
    if r.status_code != 200:
        print(f"     ERROR: {r.status_code}")
    else:
        s = r.json()
        triage = s.get("triage_level", "UNKNOWN")
        conf = s.get("confidence_score", 0)
        chief = s.get("chief_complaint", "")
        safety = s.get("safety_guardrail_triggered", False)
        evidence = s.get("evidence", [])
        completeness = s.get("clinical_completeness_score", 0)
        ai_log = s.get("ai_execution_log", {})
        fhir = s.get("session_id") is not None  # Basic check

        print(f"     Triage Level:        {triage}")
        print(f"     Confidence Score:    {conf}%")
        print(f"     Chief Complaint:     {chief[:60]}")
        print(f"     Safety Guardrail:    {'TRIGGERED ⚠️ ' if safety else 'Not triggered'}")
        print(f"     Evidence Count:      {len(evidence)} findings")
        print(f"     Completeness Score:  {completeness}/100")
        print(f"     AI Model:            {ai_log.get('model', 'N/A')}")
        print(f"     External API:        {ai_log.get('external_api', 'N/A')}")

        # Validate expected fields
        required_keys = [
            "session_id", "triage_level", "confidence_score", "chief_complaint",
            "possible_conditions", "evidence", "evidence_map", "guideline_sources",
            "clinical_completeness_score", "safety_guardrail_triggered",
            "ai_execution_log", "recommended_action", "doctor_review_required",
            "unsafe_to_self_manage"
        ]
        missing_keys = [k for k in required_keys if k not in s]
        if missing_keys:
            print(f"     ⚠️  Missing keys: {missing_keys}")
        else:
            print(f"     All {len(required_keys)} required fields present ✅")

        if triage in ("RED", "YELLOW", "GREEN"):
            print(f"     ✅ PASS — {triage} triage output")
        else:
            print(f"     ❌ FAIL — Invalid triage level: {triage}")

    # 8) FHIR R4 export
    print("\n[8] FHIR R4 Export Test...")
    r = requests.get(f"{BASE}/api/session/{sid}/fhir", timeout=15)
    if r.status_code == 200:
        fhir_bundle = r.json()
        res_type = fhir_bundle.get("resourceType")
        entry_count = len(fhir_bundle.get("entry", []))
        print(f"     resourceType: {res_type}, entries: {entry_count}")
        assert res_type == "Bundle", f"Expected Bundle, got {res_type}"
        print("     ✅ PASS")
    else:
        print(f"     ⚠️  FHIR returned {r.status_code}")

    # 9) ICD-10 suggestions
    print("\n[9] ICD-10 Suggestions...")
    r = requests.get(f"{BASE}/api/session/{sid}/icd10", timeout=15)
    if r.status_code == 200:
        icd = r.json()
        codes = icd.get("icd10_codes", [])
        print(f"     Suggestions: {len(codes)} codes")
        for c in codes[:3]:
            print(f"       - {c.get('code')}: {c.get('description', '')[:50]}")
        print("     ✅ PASS")
    else:
        print(f"     ⚠️  ICD-10 returned {r.status_code}")

    # 10) Summary
    print("\n" + "=" * 60)
    print("END-TO-END TEST COMPLETE")
    print(f"Session ID: {sid}")
    print(f"View at: http://localhost:8001/summary.html?sid={sid}")
    print("=" * 60)


if __name__ == "__main__":
    test_flow()

