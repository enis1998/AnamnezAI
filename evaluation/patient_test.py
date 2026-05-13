"""
AnamnezAI — Hasta Simulasyonu Testi
Senaryo: Mehmet Yilmaz, 55 yas, Erkek — Gogus agrisi (AMI suphesi)
"""
import httpx, json, time, asyncio, sys, io

# Windows cp1254 encoding sorununu coz
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE = "http://localhost:8000"

# ─── Hasta cevapları — gerçekçi klinik senaryo ───────────────────────────────
HASTA = {
    "patient_name": "Mehmet Yılmaz",
    "age": 55,
    "gender": "Erkek",
    "language": "tr"
}

# Hasta önceden bilinen cevapları (doğal dil, kısa)
CEVAPLAR = [
    "Göğsümde şiddetli bir baskı hissi var, sol koluma da yayılıyor",             # Q1 → ana şikayet
    "Yarım saattir var, dinlenince de geçmiyor. 8/10 şiddetinde diyebilirim",      # Q2
    "Evet, terleme başladı ve biraz nefes darlığım var",                           # Q3
    "Tansiyon hastasıyım, metoprolol kullanıyorum. Sigara içiyorum, 20 yıldır",   # Q4
    "Hayır şu an bulantı yok ama baş dönmesi hafif var",                           # Q5
    "Babam kalp krizi geçirmişti, 60 yaşında",                                     # Q6 (eğer sorulursa)
    "Hiç böyle bir ağrım olmamıştı daha önce",                                     # Q7 (eğer sorulursa)
]

async def run():
    print("\n" + "="*62)
    print("  AnamnezAI -- Gercek Hasta Simulasyonu")
    print("  Senaryo: Mehmet Yılmaz, 55E -- Gogus Agrisi")
    print("="*62)

    async with httpx.AsyncClient(timeout=180.0, base_url=BASE) as c:

        # -- ADIM 1: Oturum baslat --
        t0 = time.time()
        r = await c.post("/api/session/start", json=HASTA)
        t1 = time.time()
        d = r.json()
        sid = d["session_id"]
        print(f"\n[{t1-t0:.2f}s] Q1 (hardcoded -- AI cagirisi YOK):")
        print(f"[AI]  {d['question']}")
        print(f"      [Adim: {d['step']}/{d['total_steps']}]")

        step = 1
        total_latency = 0.0
        ai_calls = 0
        toplam_baslangic = time.time()

        for i, cevap in enumerate(CEVAPLAR):
            print(f"\n[HASTA]  {cevap}")

            t0 = time.time()
            r = await c.post("/api/session/answer", json={
                "session_id": sid,
                "answer": cevap
            })
            t1 = time.time()
            elapsed = t1 - t0
            d2 = r.json()

            step = d2.get("step", step+1)
            total_steps = d2.get("total_steps", 5)
            q = d2.get("question", "")
            ai_calls += 1
            total_latency += elapsed

            if q == "__COMPLETED__":
                print(f"\n[{elapsed:.2f}s]  *** Mulakat tamamlandi! ({step}/{total_steps} soru) ***")
                break
            else:
                print(f"[{elapsed:.2f}s] Q{step} (AI yaniti):")
                print(f"[AI]  {q}")
                print(f"      [Adim: {step}/{total_steps}]")

        toplam_sure = time.time() - toplam_baslangic

        # -- Ozet uret --
        print(f"\n{'--'*31}")
        print(f"[...] Klinik ozet uretiliyor (AI triage)...")
        t0 = time.time()
        r = await c.get(f"/api/session/{sid}/summary")
        t1 = time.time()
        elapsed_sum = t1 - t0
        s = r.json()

        lv = s.get("triage_level", "?")
        col = {"RED":"[KIRMIZI]","YELLOW":"[SARI]","GREEN":"[YESIL]"}.get(lv, "[?]")
        conf = s.get("confidence_score", 0)
        complaint = s.get("chief_complaint", "")
        symptoms = s.get("symptoms_summary", "")
        conditions = s.get("possible_conditions", [])
        flags = s.get("urgency_flags", [])
        action = s.get("recommended_action", "")
        missing = s.get("missing_information", [])
        doctor_qs = s.get("recommended_next_questions", [])
        completeness = s.get("clinical_completeness_score", 0)
        guardrail = s.get("safety_guardrail_triggered", False)
        guardrail_rules = s.get("guardrail_rules_fired", [])

        print(f"\n{'='*62}")
        print(f"  KLINIK OZET -- {col} {lv}  ({conf}% guven)")
        print(f"{'='*62}")
        print(f"\n[Ana Sikayet]")
        print(f"  {complaint}")
        print(f"\n[Semptom Ozeti]")
        print(f"  {symptoms}")
        if conditions:
            print(f"\n[Olasi Tanilar]")
            for c2 in conditions[:4]:
                print(f"  * {c2}")
        if flags:
            print(f"\n[Acil Bayraklar] !!!")
            for f in flags[:5]:
                print(f"  !! {f}")
        print(f"\n[Onerilen Eylem]")
        print(f"  {action}")
        print(f"\n[Klinik Butunluk Skoru] {completeness}/100")
        if missing:
            print(f"[Eksik Bilgi] {', '.join(missing[:3])}")
        if doctor_qs:
            print(f"[Doktor Icin Sorular] {'; '.join(doctor_qs[:2])}")
        if guardrail:
            print(f"\n[!!!] SAFETY GUARDRAIL TETIKLENDI!")
            for rule in guardrail_rules[:3]:
                print(f"  >> {rule}")

        print(f"\n{'='*62}")
        print(f"  PERFORMANS OZETI")
        print(f"{'='*62}")
        print(f"  Q1 (hardcoded)            : ~0.00 sn")
        print(f"  AI cagri sayisi           : {ai_calls} soru + 1 ozet")
        print(f"  Ort. soru gecikmesi       : {total_latency/max(ai_calls,1):.1f} sn/soru")
        print(f"  Ozet uretim suresi        : {elapsed_sum:.1f} sn")
        print(f"  TOPLAM MULAKAT (AI suresi): {toplam_sure:.1f} sn")
        print(f"  Hasta girdi suresi dahil  : ~{(toplam_sure + step*20)/60:.1f} dakika")
        print(f"{'='*62}\n")

if __name__ == "__main__":
    asyncio.run(run())
