"""
AnamnezAI — Gerçek AI Kalite Testi
===================================
Ollama + Gemma4 üzerinde çalışan canlı testler.
Hem RAG retrieval hem de model cevapları test edilir.

Çalıştırmak için:
  cd mediscreen
  python evaluation/test_ai_quality.py
"""

import sys, os, json, time, httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'backend'))

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
MODEL      = os.getenv("GEMMA_MODEL", "gemma4:e4b")

# ─── Renk kodları ────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):  print(f"  {GREEN}✅ {msg}{RESET}")
def fail(msg):print(f"  {RED}❌ {msg}{RESET}")
def info(msg):print(f"  {CYAN}ℹ  {msg}{RESET}")
def warn(msg):print(f"  {YELLOW}⚠  {msg}{RESET}")

# ─── Yardımcı: Gemma4'e direkt istek ───────────────────────
def ask_model(prompt: str, system: str = "", timeout: float = 120.0) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = httpx.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": MODEL,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {"temperature": 0.2, "top_p": 0.85, "num_predict": 600, "repeat_penalty": 1.3},
        },
        timeout=timeout,
    )
    return resp.json()["message"]["content"].strip()

# ─── 1. BÖLÜM: RAG Retrieval Kalitesi ───────────────────────
def test_rag_retrieval():
    print(f"\n{BOLD}{'═'*60}{RESET}")
    print(f"{BOLD}1. RAG Retrieval Kalitesi{RESET}")
    print(f"{'═'*60}")

    try:
        import rag
        rag.ingest_builtin_knowledge()
        count = rag._get_collection().count()
        info(f"ChromaDB toplam chunk: {count}")
    except Exception as e:
        fail(f"RAG başlatılamadı: {e}")
        return

    test_cases = [
        ("göğüs ağrısı sol kola yayılıyor terleme",
         ["Cardiac_Emergency", "MTS"],
         "Kardiyak acil chunk'ları gelmeli"),
        ("bebek 2 aylık ateş 38.5",
         ["Pediatric"],
         "Pediatrik triaj chunk'ları gelmeli"),
        ("ani baş ağrısı şiddetli ense sertliği",
         ["Neurological"],
         "Nörolojik acil chunk'ları gelmeli"),
        ("bel ağrısı idrar yapamıyor",
         ["Orthopedic", "Urology"],
         "Ortopedi/Üroloji chunk'ları gelmeli"),
        ("döküntü ateş peteşi",
         ["Dermatology"],
         "Dermatoloji chunk'ları gelmeli"),
        ("kulak ağrısı çocuk",
         ["ENT"],
         "KBB chunk'ları gelmeli"),
    ]

    passed = 0
    for query, expected_sources, desc in test_cases:
        hits = rag.retrieve(query, n_results=6)
        relevant = [h for h in hits if h["relevance"] >= 0.30]
        sources_found = [h["source"] for h in relevant]
        sources_str = ", ".join(set(sources_found))

        matched = any(
            any(exp.lower() in s.lower() for s in sources_found)
            for exp in expected_sources
        )
        top_relevance = hits[0]["relevance"] if hits else 0

        if matched and top_relevance >= 0.35:
            ok(f"{desc}")
            info(f"   Top relevance: {top_relevance:.3f} | Kaynaklar: {sources_str[:80]}")
            passed += 1
        elif matched:
            warn(f"{desc} (düşük relevance: {top_relevance:.3f})")
            info(f"   Kaynaklar: {sources_str[:80]}")
        else:
            fail(f"{desc}")
            info(f"   Beklenen: {expected_sources} | Bulunan: {sources_str[:80]}")

    print(f"\n  Sonuç: {passed}/{len(test_cases)} RAG testi geçti")
    return passed, len(test_cases)

# ─── 2. BÖLÜM: Triaj Kararı Mantık Testi ───────────────────
def test_triage_decisions():
    print(f"\n{BOLD}{'═'*60}{RESET}")
    print(f"{BOLD}2. Triaj Kararı Mantık Testi (Gemma 4){RESET}")
    print(f"{'═'*60}")

    # (senaryo, beklenen_level, gerekçe)
    scenarios = [
        {
            "name": "🔴 AMI - Açık Kardiyak Acil",
            "interview": """
Hasta: Mehmet, 62, Erkek
S1: Göğsünüzde baskı hissediyor musunuz? → C: Evet, sabahtan beri göğsüm çok sıkışiyor
S2: Sol kolunuza ya da çenenize yayılıyor mu? → C: Evet sol koluma iniyor, çok kötü
S3: Terleme veya nefes darlığı var mı? → C: Evet çok terliyorum, nefes almakta güçlük çekiyorum
S4: 1-10 skalasında ağrı kaç? → C: 9-10 arası, dayanamıyorum
S5: Bilinen kalp hastalığı ya da diyabet var mı? → C: Diyabetim var, hipertansiyon da var""",
            "expected": "RED",
            "must_have": ["kardiyak", "acil", "AMI", "MI", "damar", "heart", "emergency"],
        },
        {
            "name": "🟡 Yüksek Ateş Çocuk",
            "interview": """
Hasta: Ayşe, 4, Kız
Ebeveyn: Çocuğumun ateşi 39.5°C, 2 gündür var
S1: Boğaz ağrısı ya da öksürük var mı? → C: Biraz öksürüyor, boğazı kırmızıymış
S2: Ense sertliği fark ettiniz mi? → C: Hayır öyle bir şey yok
S3: Bilinç ya da davranış değişikliği var mı? → C: Biraz halsiz ama normal konuşuyor
S4: Döküntü var mı? → C: Hayır döküntü yok
S5: İlaç verdikten sonra ateş düştü mü? → C: Parasetamol verince biraz iniyor""",
            "expected": "YELLOW",
            "must_have": ["ateş", "çocuk", "pediyatrik", "fever", "pediatric"],
        },
        {
            "name": "🟢 Basit ÜSYE",
            "interview": """
Hasta: Zeynep, 28, Kadın
S1: Şikayetiniz ne? → C: 3 gündür hafif soğuk algınlığı, burun akıntısı var
S2: Ateşiniz var mı? → C: 37.2°C, çok fazla değil
S3: Nefes darlığı ya da göğüs ağrısı var mı? → C: Hayır sadece burun tıkanıklığı
S4: Başka kronik hastalık var mı? → C: Hayır sağlıklıyım
S5: Boğaz ağrısı oluyor mu? → C: Hafif, ibuprofen alınca geçiyor""",
            "expected": "GREEN",
            "must_have": ["yeşil", "rutin", "hafif", "green", "routine", "mild"],
        },
        {
            "name": "🔴 İnme Şüphesi",
            "interview": """
Hasta: Fatma, 71, Kadın
S1: Ne şikayetle geldiniz? → C: Kocam konuşamıyor birden, ağzı eğildi
S2: Kolu kaldırabiliyor mu? → C: Sağ kolu kaldıramıyor, sarkıyor
S3: Ne zaman başladı? → C: 30 dakika önce, birdenbire oldu
S4: Daha önce benzer bir şey oldu mu? → C: Hayır hiç böyle olmamıştı
S5: Kan basıncı ilacı kullanıyor mu? → C: Evet hipertansiyon için ilaçları var""",
            "expected": "RED",
            "must_have": ["inme", "felç", "stroke", "acil", "nöroloji"],
        },
        {
            "name": "🟡 Karın Ağrısı - Apandisit Şüphesi",
            "interview": """
Hasta: Can, 19, Erkek
S1: Ağrı nerede? → C: Önce göbeğim ağrıyordu, şimdi sağ altıma geçti
S2: Kaç saattir devam ediyor? → C: 8-9 saat
S3: Ateş, bulantı kusma var mı? → C: 38°C ateşim var, biraz bulantım var
S4: 1-10 skalasında? → C: 7-8 arası, hareket edince artıyor
S5: İştahınız var mı? → C: Hiç yemek yemek istemiyorum""",
            "expected": "YELLOW",  # akut apandisit şüphesi = ORANGE/YELLOW
            "must_have": ["apandisit", "appendix", "karın", "aril", "urgent"],
        },
    ]

    passed = 0
    details = []

    TRIAGE_SYSTEM = """Sen Manchester Triage System uzmanısın. SADECE geçerli JSON döndür.
GÜVENLİK KURALI: Şüphe halinde daha yüksek triaj seviyesi seç. Kırmızı bayraklar varsa RED zorunlu.
{
  "triage_level": "RED veya YELLOW veya GREEN",
  "confidence_score": 0-100,
  "chief_complaint": "Ana şikayet",
  "evidence": ["Kanıt 1", "Kanıt 2"],
  "recommended_action": "Eylem",
  "doctor_review_required": true/false
}"""

    for sc in scenarios:
        print(f"\n  {BOLD}{sc['name']}{RESET}")
        t0 = time.time()
        try:
            prompt = f"Hasta mülakatı:\n{sc['interview']}\n\nBu hastayı triaj et. Sadece JSON döndür."
            raw = ask_model(prompt, system=TRIAGE_SYSTEM, timeout=90.0)
            elapsed = time.time() - t0

            # JSON parse
            cleaned = raw.strip()
            if "```" in cleaned:
                parts = cleaned.split("```")
                for p in parts:
                    if "{" in p:
                        cleaned = p.replace("json","").strip()
                        break

            result = json.loads(cleaned)
            level  = result.get("triage_level", "?")
            conf   = result.get("confidence_score", 0)
            action = result.get("recommended_action", "")
            evidence = result.get("evidence", [])

            level_ok = level == sc["expected"]
            ev_text  = " ".join(evidence).lower() + action.lower()
            hint_ok  = any(kw.lower() in ev_text for kw in sc["must_have"])

            info(f"   Yanıt: {level} (güven:{conf}%) — {elapsed:.1f}s")
            info(f"   Eylem: {action[:80]}")
            for ev in evidence[:3]:
                info(f"   Kanıt: {ev[:80]}")

            if level_ok:
                ok(f"   Triaj seviyesi DOĞRU: {level} (beklenen: {sc['expected']})")
                passed += 1
            else:
                # AMI/inme için RED yerine YELLOW da kritik hata
                if sc["expected"] == "RED" and level != "RED":
                    fail(f"   KRİTİK HATA: {level} beklendi RED — Hasta tehlikede!")
                else:
                    warn(f"   Triaj seviyesi FARKLI: {level} (beklenen: {sc['expected']})")
                    # Apandisit için YELLOW/ORANGE kabul edilebilir
                    if sc["expected"] == "YELLOW" and level in ("YELLOW", "RED"):
                        ok(f"   Kabul edilebilir aralıkta (RED veya YELLOW)")
                        passed += 1

            if not hint_ok:
                warn(f"   Gerekçe zayıf — beklenen anahtar kelimeler bulunamadı: {sc['must_have']}")

            details.append({"name": sc["name"], "level": level, "expected": sc["expected"],
                           "correct": level_ok, "confidence": conf})

        except json.JSONDecodeError as e:
            fail(f"   JSON parse hatası: {e}")
            info(f"   Ham yanıt: {raw[:200]}")
        except Exception as e:
            fail(f"   Model hatası: {e}")

    print(f"\n  Triaj Sonuçları: {passed}/{len(scenarios)} doğru")
    return passed, len(scenarios), details

# ─── 3. BÖLÜM: Soru Kalitesi Testi ─────────────────────────
def test_question_quality():
    print(f"\n{BOLD}{'═'*60}{RESET}")
    print(f"{BOLD}3. Mülakat Sorusu Kalitesi (Gemma 4){RESET}")
    print(f"{'═'*60}")

    SYSTEM = """Sen AnamnezAI — deneyimli tıbbi pre-triaj asistanısın.
SADECE 1 soru sor (max 2 cümle). Tıbbi jargon kullanma. ACİL semptomlar varsa önce detaylandır.
OPQRST çerçevesini uygula. Soru işaretiyle bitir."""

    cases = [
        {
            "name": "Göğüs ağrısı başvurusu",
            "complaint": "Hasta: Ali, 55, Erkek. Şikayet: 'Göğsümde ağrı var'",
            "expect_topics": ["kol", "sırt", "çene", "yayılım", "arm", "radiation", "terleme", "nefes"],
        },
        {
            "name": "Baş dönmesi başvurusu",
            "complaint": "Hasta: Hasan, 42, Erkek. Şikayet: 'Başım dönüyor'",
            "expect_topics": ["ne zamandır", "nasıl", "bulantı", "düşme", "when", "how long"],
        },
        {
            "name": "Çocuk ateşi başvurusu",
            "complaint": "Hasta: Leyla, 3, Kız. Ebeveyn şikayeti: 'Ateşi var, halsiz'",
            "expect_topics": ["ateş", "kaç derece", "ne zamandır", "döküntü", "temperature", "rash"],
        },
    ]

    passed = 0
    for case in cases:
        print(f"\n  {BOLD}{case['name']}{RESET}")
        t0 = time.time()
        try:
            question = ask_model(case["complaint"], system=SYSTEM, timeout=60.0)
            elapsed = time.time() - t0

            info(f"   Model sorusu: \"{question}\"")
            info(f"   Yanıt süresi: {elapsed:.1f}s")

            q_lower = question.lower()
            # Soru işaretli mi?
            has_q = "?" in question
            # Tek cümle/soru mu? (Çok uzun değil)
            reasonable_length = 20 < len(question) < 250
            # Beklenen konulardan en az 1'i içeriyor mu?
            topic_match = any(t.lower() in q_lower for t in case["expect_topics"])

            checks = [
                (has_q, "Soru işareti var"),
                (reasonable_length, f"Makul uzunluk ({len(question)} karakter)"),
                (topic_match, f"Klinik açıdan alakalı konu"),
            ]

            all_ok = True
            for check_ok, check_msg in checks:
                if check_ok:
                    ok(f"   {check_msg}")
                else:
                    fail(f"   {check_msg}")
                    all_ok = False

            if all_ok:
                passed += 1

        except Exception as e:
            fail(f"   Hata: {e}")

    print(f"\n  Soru kalitesi: {passed}/{len(cases)} test geçti")
    return passed, len(cases)

# ─── 4. BÖLÜM: RAG + Triage Entegrasyon Testi ───────────────
def test_rag_augmented_triage():
    print(f"\n{BOLD}{'═'*60}{RESET}")
    print(f"{BOLD}4. RAG + Triaj Entegrasyon Testi{RESET}")
    print(f"{'═'*60}")

    try:
        import rag as rag_module
        rag_module.ingest_builtin_knowledge()

        query = "göğüs ağrısı sol kola yayılım terleme kardiyak acil"
        context = rag_module.get_medical_context_for_triage(
            chief_complaint=query, min_relevance=0.30
        )

        if context and len(context) > 100:
            ok(f"get_medical_context_for_triage() çalışıyor ({len(context)} karakter)")
            # Beklenen kategorilerin bağlamda olup olmadığını kontrol et
            if "TRİAJ" in context or "ACİL" in context or "CARDIAC" in context.upper() or "kard" in context.lower():
                ok("Bağlamda kardiyak/triaj protokol içeriği var")
            else:
                warn("Bağlamda kardiyak içerik bulunamadı")
            info(f"Bağlam önizleme:\n{context[:400]}")
        else:
            fail(f"RAG bağlamı yetersiz: '{context[:100]}'")
            return 0, 1

        # RAG ile zenginleştirilmiş bir triage çağrısı yap
        TRIAGE_SYS = """Sen MTS triaj uzmanısın. SADECE JSON döndür.
{"triage_level":"RED/YELLOW/GREEN","confidence_score":0-100,"chief_complaint":"...","evidence":[],"recommended_action":"...","doctor_review_required":true}"""

        augmented_system = TRIAGE_SYS + "\n\n" + context

        prompt = """HASTA: Kadir, 58 yaş, Erkek, Diyabetik, Hipertansiyon
MÜlakat:
Q: Şikayetiniz? → A: 1 saattir göğsüm dayanılmaz baskıyor
Q: Yayılım? → A: Sol kolum tuttu, çeneme de vuruyor
Q: Terleme? → A: Soğuk terliyorum, çok korkuyorum
Q: 1-10? → A: 10
Q: Nefes? → A: Biraz zor alıyorum
Triaj et. Sadece JSON."""

        t0 = time.time()
        raw = ask_model(prompt, system=augmented_system, timeout=90.0)
        elapsed = time.time() - t0

        cleaned = raw.strip().replace("```json","").replace("```","")
        result = json.loads(cleaned)
        level = result.get("triage_level","?")
        conf  = result.get("confidence_score",0)

        info(f"RAG-augmented triaj: {level} (güven:{conf}%) — {elapsed:.1f}s")

        if level == "RED" and conf >= 80:
            ok(f"RAG + Triaj entegrasyonu MÜKEMMEL: {level} @ {conf}%")
            return 1, 1
        elif level == "RED":
            ok(f"RAG + Triaj doğru seviye: {level} (güven biraz düşük: {conf}%)")
            return 1, 1
        else:
            fail(f"RAG + Triaj HATALI: {level} beklendi RED — Kritik!")
            return 0, 1

    except Exception as e:
        fail(f"Entegrasyon testi hatası: {e}")
        import traceback; traceback.print_exc()
        return 0, 1

# ─── ANA TEST RUNNER ─────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n{BOLD}{'═'*60}")
    print(f"  AnamnezAI — AI Kalite Testi")
    print(f"  Model: {MODEL} @ {OLLAMA_URL}")
    print(f"{'═'*60}{RESET}")

    # Ollama ping
    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=5.0)
        models = [m["name"] for m in r.json().get("models",[])]
        if not any("gemma4" in m for m in models):
            print(f"{RED}❌ gemma4:e4b bulunamadı! Mevcut: {models}{RESET}")
            sys.exit(1)
        ok(f"Ollama bağlantısı OK, model: {MODEL}")
    except Exception as e:
        print(f"{RED}❌ Ollama bağlanamadı: {e}{RESET}")
        sys.exit(1)

    total_pass = 0
    total_all  = 0

    # Test 1 — RAG
    p, a = test_rag_retrieval()
    total_pass += p; total_all += a

    # Test 2 — Triage kararı
    p, a, details = test_triage_decisions()
    total_pass += p; total_all += a

    # Test 3 — Soru kalitesi
    p, a = test_question_quality()
    total_pass += p; total_all += a

    # Test 4 — Entegrasyon
    p, a = test_rag_augmented_triage()
    total_pass += p; total_all += a

    # ─── Özet ───────────────────────────────────────────────
    print(f"\n{BOLD}{'═'*60}")
    print(f"  GENEL SONUÇ: {total_pass}/{total_all} test geçti")
    score = int(total_pass / total_all * 100) if total_all else 0
    if score >= 80:
        print(f"  {GREEN}🏆 BAŞARILI — Skor: {score}%{RESET}")
    elif score >= 60:
        print(f"  {YELLOW}⚠ KISMEN BAŞARILI — Skor: {score}%{RESET}")
    else:
        print(f"  {RED}❌ GELİŞTİRME GEREKLİ — Skor: {score}%{RESET}")
    print(f"{'═'*60}{RESET}\n")

    # Triage detay özeti
    print(f"{BOLD}Triaj Kararı Özeti:{RESET}")
    for d in details:
        sym = "✅" if d["correct"] else "❌"
        print(f"  {sym} {d['name']}: {d['level']} (beklenen:{d['expected']}, güven:{d['confidence']}%)")

