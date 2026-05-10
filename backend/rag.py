"""
AnamnezAI — Medical RAG (Retrieval-Augmented Generation)
=========================================================
Tıbbi bilgi tabanından ilgili bağlamı alarak Gemma 4'ü güçlendirir.

Mimari:
  PDF/Text Dökümanlar
       ↓
  Chunk & Embed (multilingual-MiniLM)
       ↓
  ChromaDB (yerel vektör veritabanı)
       ↓
  Sorgu geldiğinde top-K chunk al
       ↓
  Gemma 4 promptuna bağlam ekle → Daha doğru triaj
"""

import os
import re
import json
import hashlib
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger("anamnezai.rag")

# Lazy imports — sunucu başlangıcını yavaşlatmamak için
_chroma_client = None
_collection = None
_embed_model = None

CHROMA_DIR = os.getenv("CHROMA_DIR", os.path.join(os.path.dirname(__file__), "..", "chroma_db"))
COLLECTION_NAME = "medical_knowledge"
EMBED_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
CHUNK_SIZE = 400      # kelime
CHUNK_OVERLAP = 60    # kelime
TOP_K = 6             # Varsayılan retrieval sayısı (artırıldı: 4→6)

# Kategori öncelik sırası (düşük sayı = yüksek öncelik)
CATEGORY_PRIORITY = {
    "triage_protocol": 1,
    "emergency_protocol": 2,
    "clinical_guideline": 3,
    "icd10_codes": 4,
    "icd10_coding": 4,
    "clinical_reference": 5,
    "epidemiology": 6,
    "terminology": 7,
    "qa": 8,
    "general": 9,
}

# ─────────────────────────────────────────────
#  Tıbbi Terim Sözlüğü — TR ↔ EN Query Expansion
#  (API çağrısı olmadan anlık genişleme)
# ─────────────────────────────────────────────
_TR_EN_MEDICAL = {
    # Kardiyak
    "göğüs ağrısı": "chest pain cardiac",
    "göğüs": "chest thoracic",
    "kalp": "heart cardiac",
    "çarpıntı": "palpitation tachycardia arrhythmia",
    "kalp krizi": "myocardial infarction AMI heart attack",
    "kalp yetmezliği": "heart failure",
    "hipertansiyon": "hypertension high blood pressure",
    "tansiyon": "blood pressure hypertension",
    "nabız": "pulse heart rate",
    "aort": "aortic aorta dissection",
    # Nöroloji
    "felç": "stroke cerebrovascular",
    "inme": "stroke ischemic cerebral",
    "baş ağrısı": "headache migraine cephalgia",
    "baş dönmesi": "dizziness vertigo",
    "bayılma": "syncope loss of consciousness",
    "uyuşma": "numbness paresthesia",
    "güçsüzlük": "weakness paralysis paresis",
    "konvülsiyon": "seizure epilepsy convulsion",
    "nöbet": "seizure epileptic fit",
    "bilinç kaybı": "loss of consciousness unconscious GCS",
    "afazi": "aphasia speech difficulty",
    # Solunum
    "nefes darlığı": "dyspnea breathlessness shortness of breath",
    "nefes": "breath respiratory breathing",
    "öksürük": "cough",
    "balgam": "sputum phlegm",
    "hırıltı": "wheezing stridor",
    "akciğer": "lung pulmonary",
    "pnömotoraks": "pneumothorax",
    "emboli": "embolism pulmonary embolism PE",
    "astım": "asthma bronchospasm",
    # Karın / GIS
    "karın ağrısı": "abdominal pain abdomen",
    "karın": "abdomen abdominal",
    "bulantı": "nausea vomiting",
    "kusma": "vomiting emesis",
    "ishal": "diarrhea",
    "kabızlık": "constipation",
    "sarılık": "jaundice icterus",
    "apandisit": "appendicitis appendix",
    "kolesistit": "cholecystitis gallbladder",
    "pankreatit": "pancreatitis",
    "kanama": "bleeding hemorrhage",
    "kanlı": "bloody hemorrhagic",
    # Travma / Ortopedi
    "kırık": "fracture broken bone",
    "düşme": "fall trauma",
    "travma": "trauma injury",
    "bel ağrısı": "back pain lumbar",
    "boyun ağrısı": "neck pain cervical",
    "eklem": "joint articular",
    "omuz": "shoulder",
    "diz": "knee",
    "bileği": "wrist ankle",
    # Deri / Alerji
    "döküntü": "rash dermatitis",
    "kaşıntı": "itching pruritus",
    "şişlik": "swelling edema",
    "kızarıklık": "erythema redness",
    "yanık": "burn",
    "anafilaksi": "anaphylaxis allergic reaction",
    "alerji": "allergy allergic",
    "ürtiker": "urticaria hives",
    # KBB
    "kulak ağrısı": "ear pain otalgia otitis",
    "boğaz ağrısı": "sore throat pharyngitis tonsillitis",
    "burun kanaması": "epistaxis nosebleed",
    "yutma güçlüğü": "dysphagia swallowing difficulty",
    # Göz
    "görme kaybı": "vision loss blindness",
    "göz ağrısı": "eye pain ophthalmic",
    "çift görme": "diplopia double vision",
    # Endokrin
    "şeker": "glucose diabetes blood sugar",
    "diyabet": "diabetes mellitus",
    "hipoglisemi": "hypoglycemia low blood sugar",
    "tiroid": "thyroid",
    # Psikiyatri / Genel
    "ateş": "fever febrile pyrexia temperature",
    "titreme": "chills shivering",
    "halsizlik": "fatigue weakness malaise",
    "terleme": "diaphoresis sweating",
    "idrar": "urine urinary",
    "kan": "blood hemorrhage",
    "enfeksiyon": "infection",
    "sepsis": "sepsis septic",
    "çocuk": "pediatric child infant",
    "bebek": "infant neonatal baby",
    "yaşlı": "elderly geriatric",
    "hamile": "pregnant pregnancy obstetric",
    "gebe": "pregnant obstetric",
}

# İngilizce → Türkçe ters sözlük (opsiyonel kullanım)
_EN_TR_MEDICAL = {v_word: k
                  for k, v in _TR_EN_MEDICAL.items()
                  for v_word in v.split()}


def expand_query_multilingual(query: str) -> str:
    """
    Kullanıcı sorgusunu TR↔EN tıbbi sözlükle genişletir.
    Herhangi bir dilde girilen sorguya, karşılık gelen İngilizce
    (veya Türkçe) tıbbi terimler eklenir.

    Örnek:
      "göğüs ağrısı sol kola yayılım" →
      "göğüs ağrısı sol kola yayılım chest pain cardiac thoracic"
    """
    q_lower = query.lower()
    expansions: list[str] = []

    for tr_term, en_terms in _TR_EN_MEDICAL.items():
        if tr_term in q_lower:
            # İngilizce karşılıklardan ilk 2'yi ekle (uzunluğu kontrol et)
            en_words = en_terms.split()[:2]
            expansions.extend(en_words)

    # İngilizce kelime varsa Türkçe karşılık ekle
    for en_word, tr_term in _EN_TR_MEDICAL.items():
        if en_word.lower() in q_lower and tr_term not in q_lower:
            expansions.append(tr_term)

    if expansions:
        # Tekrarlananları kaldır, query'ye ekle
        unique_expansions = list(dict.fromkeys(expansions))
        expanded = query + " " + " ".join(unique_expansions[:8])
        logger.debug(f"Query expanded: '{query}' → '{expanded}'")
        return expanded

    return query


# ─────────────────────────────────────────────
#  Çok Dilli Sorgu Çevirisi — Herhangi Dil → İngilizce
# ─────────────────────────────────────────────
_langdetect_available = None
_deep_translator_available = None


def _check_translation_libs() -> tuple[bool, bool]:
    """Çeviri kütüphanelerinin kullanılabilirliğini kontrol eder (lazy, bir kere)."""
    global _langdetect_available, _deep_translator_available
    if _langdetect_available is None:
        try:
            from langdetect import detect
            _langdetect_available = True
        except ImportError:
            _langdetect_available = False
    if _deep_translator_available is None:
        try:
            from deep_translator import GoogleTranslator
            _deep_translator_available = True
        except ImportError:
            _deep_translator_available = False
    return _langdetect_available, _deep_translator_available


def detect_language(text: str) -> str:
    """Metnin dilini algılar. Başarısız olursa 'unknown' döner."""
    lang_ok, _ = _check_translation_libs()
    if not lang_ok:
        return "unknown"
    try:
        from langdetect import detect
        return detect(text)
    except Exception:
        return "unknown"


def translate_query_to_english(query: str) -> str:
    """
    Kullanıcı sorgusunu herhangi bir dilden İngilizce'ye çevirir.

    Strateji:
      1. Dil algılama (langdetect)
      2. Türkçe ise  → sözlük tabanlı genişleme (internet gerektirmez, hızlı)
      3. İngilizce   → doğrudan döndür
      4. Diğer dil   → deep-translator ile Google Translate (internet gerekir)
      5. Herhangi bir hata → orijinal sorguyu döndür (sessiz fallback)

    Örnek:
      "douleur thoracique" (Fransızca) → "chest pain"
      "göğüs ağrısı"      (Türkçe)    → "göğüs ağrısı chest pain cardiac"
      "chest pain"         (İngilizce) → "chest pain"
      "ألم في الصدر"       (Arapça)    → "chest pain"
    """
    if not query or len(query.strip()) < 2:
        return query

    lang_ok, trans_ok = _check_translation_libs()

    # Dil algıla
    detected_lang = detect_language(query) if lang_ok else "unknown"
    logger.debug(f"Detected language: '{detected_lang}' for query: '{query[:50]}'")

    # Türkçe → sözlük tabanlı genişleme (en hızlı, internet yok)
    if detected_lang in ("tr", "unknown") and any(t in query.lower() for t in _TR_EN_MEDICAL):
        return expand_query_multilingual(query)

    # İngilizce → doğrudan kullan
    if detected_lang == "en":
        return query

    # Diğer diller → deep-translator ile çevir
    if trans_ok and detected_lang not in ("tr", "en"):
        try:
            from deep_translator import GoogleTranslator
            translated = GoogleTranslator(source="auto", target="en").translate(query)
            if translated and translated.strip():
                logger.info(f"Query translated ({detected_lang}→en): '{query}' → '{translated}'")
                return translated.strip()
        except Exception as e:
            logger.warning(f"Translation failed ({detected_lang}→en): {e}")

    # Türkçe için genişleme yap (algılama başarısız olsa bile)
    expanded = expand_query_multilingual(query)
    return expanded


# ─────────────────────────────────────────────
#  Lazy init
# ─────────────────────────────────────────────
def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Embedding modeli yükleniyor: {EMBED_MODEL_NAME}")
            _embed_model = SentenceTransformer(EMBED_MODEL_NAME)
            logger.info("Embedding modeli hazır.")
        except ImportError:
            logger.warning("sentence-transformers kurulu değil. pip install sentence-transformers")
            raise
    return _embed_model


def _get_collection():
    global _chroma_client, _collection
    if _collection is None:
        try:
            import chromadb
            os.makedirs(CHROMA_DIR, exist_ok=True)
            _chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
            _collection = _chroma_client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(f"ChromaDB hazır. Koleksiyon: {COLLECTION_NAME}, Kayıt: {_collection.count()}")
        except ImportError:
            logger.warning("chromadb kurulu değil. pip install chromadb")
            raise
    return _collection


def is_rag_available() -> bool:
    """RAG bitleşenlerinin kurulu olup olmadığını kontrol eder."""
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
        return True
    except ImportError:
        return False


# ─────────────────────────────────────────────
#  Document Chunking
# ─────────────────────────────────────────────
def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Metni örtüşen chunk'lara böler."""
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        if len(chunk.strip()) > 50:  # Çok kısa chunk'ları atla
            chunks.append(chunk.strip())
        start += chunk_size - overlap
    return chunks


def _text_id(text: str, source: str, idx: int) -> str:
    """Tekralanmayı önlemek için deterministik ID üretir."""
    content = f"{source}_{idx}_{text[:50]}"
    return hashlib.md5(content.encode()).hexdigest()[:16]


# ─────────────────────────────────────────────
#  Ingestion
# ─────────────────────────────────────────────
def ingest_text(text: str, source: str = "manual", category: str = "general") -> int:
    """
    Ham metin alır, chunk'a böler, vektörize eder ve ChromaDB'ye ekler.
    Geri döndürür: eklenen chunk sayısı
    """
    collection = _get_collection()
    embed = _get_embed_model()

    chunks = _chunk_text(text)
    if not chunks:
        return 0

    # Zaten eklenmiş ID'leri filtrele
    ids = [_text_id(c, source, i) for i, c in enumerate(chunks)]
    existing = set(collection.get(ids=ids)["ids"])
    new_chunks = [(iid, ch) for iid, ch in zip(ids, chunks) if iid not in existing]

    if not new_chunks:
        logger.info(f"[{source}] Tüm chunk'lar zaten mevcut, atlanıyor.")
        return 0

    new_ids, new_texts = zip(*new_chunks)
    embeddings = embed.encode(list(new_texts), show_progress_bar=False).tolist()

    collection.add(
        ids=list(new_ids),
        embeddings=embeddings,
        documents=list(new_texts),
        metadatas=[{"source": source, "category": category} for _ in new_texts],
    )
    logger.info(f"[{source}] {len(new_ids)} chunk eklendi.")
    return len(new_ids)


def ingest_pdf(pdf_path: str, source_name: Optional[str] = None, category: str = "clinical_guideline") -> int:
    """PDF dosyasını okur ve ChromaDB'ye ekler."""
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.warning("pypdf kurulu değil. pip install pypdf")
        return 0

    path = Path(pdf_path)
    if not path.exists():
        logger.warning(f"PDF bulunamadı: {pdf_path}")
        return 0

    source = source_name or path.stem
    reader = PdfReader(str(path))
    full_text = ""
    for page in reader.pages:
        full_text += (page.extract_text() or "") + "\n"

    full_text = re.sub(r"\s+", " ", full_text).strip()
    if not full_text:
        logger.warning(f"PDF boş veya okunamadı: {pdf_path}")
        return 0

    count = ingest_text(full_text, source=source, category=category)
    logger.info(f"PDF işlendi: {source} — {count} chunk")
    return count


def ingest_json_qa(json_path: str, question_field: str = "question",
                   answer_field: str = "answer", source: str = "qa_dataset") -> int:
    """JSON/JSONL Q&A dosyasını okur ve ekler."""
    path = Path(json_path)
    if not path.exists():
        logger.warning(f"JSON bulunamadı: {json_path}")
        return 0

    total = 0
    with open(path, encoding="utf-8") as f:
        if path.suffix == ".jsonl":
            lines = [json.loads(l) for l in f if l.strip()]
        else:
            data = json.load(f)
            lines = data if isinstance(data, list) else [data]

    for item in lines:
        q = item.get(question_field, "")
        a = item.get(answer_field, "")
        if q and a:
            combined = f"Q: {q}\nA: {a}"
            total += ingest_text(combined, source=source, category="qa")

    logger.info(f"JSON Q&A işlendi: {source} — {total} chunk")
    return total


# ─────────────────────────────────────────────
#  Retrieval
# ─────────────────────────────────────────────
def retrieve(query: str, n_results: int = TOP_K, category_filter: Optional[str] = None) -> list[dict]:
    """
    Verilen sorguya göre en alakalı belge chunk'larını getirir.

    Arama öncesi sorgu otomatik olarak İngilizce'ye çevrilir:
      - Türkçe   → sözlük tabanlı genişleme (TR + EN terimler)
      - İngilizce → doğrudan kullan
      - Diğer dil → deep-translator ile çevir (internet gerekir)
    Bu sayede Türkçe, İngilizce veya başka herhangi bir dilde girilen
    sorgular, Chromadb'deki tıbbi bilgilerle daha iyi eşleşir.
    """
    collection = _get_collection()
    embed = _get_embed_model()

    # ── Çeviri katmanı — herhangi bir dil → İngilizce ──
    translated_query = translate_query_to_english(query)
    # Orijinal + çevrilmiş sorguyu birleştir (en iyi kapsama için)
    search_query = (
        f"{query} {translated_query}"
        if translated_query.strip().lower() != query.strip().lower()
        else query
    )

    query_emb = embed.encode([search_query], show_progress_bar=False).tolist()

    where = {"category": category_filter} if category_filter else None

    results = collection.query(
        query_embeddings=query_emb,
        n_results=min(n_results, max(1, collection.count())),
        where=where,
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        hits.append({
            "document": doc,
            "source": meta.get("source", ""),
            "category": meta.get("category", ""),
            "relevance": round(1 - dist, 3),  # cosine similarity
        })
    return hits


def get_context_for_prompt(query: str, n_results: int = TOP_K,
                           min_relevance: float = 0.35) -> str:
    """
    Sorguyla ilgili tıbbi bağlamı prompt'a hazır formatta döndürür.
    Düşük relevance'lı sonuçları filtreler.

    Sorgu herhangi bir dilde girilebilir — retrieve() içindeki
    çeviri katmanı otomatik olarak İngilizce'ye dönüştürür.
    """
    if not is_rag_available():
        return ""

    try:
        collection = _get_collection()
        if collection.count() == 0:
            return ""

        hits = retrieve(query, n_results=n_results)
        relevant = [h for h in hits if h["relevance"] >= min_relevance]

        if not relevant:
            return ""

        # Kategori önceliğine göre sırala
        relevant.sort(key=lambda h: (
            CATEGORY_PRIORITY.get(h.get("category", "general"), 9),
            -h["relevance"]
        ))

        lines = ["=== Tıbbi Referans Bilgisi ==="]
        for h in relevant:
            lines.append(f"[{h['source']}] {h['document']}")

        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"RAG retrieval hatası (önemsiz): {e}")
        return ""


def get_medical_context_for_triage(
    chief_complaint: str,
    qa_history: str = "",
    n_per_query: int = 5,
    min_relevance: float = 0.38,
    max_chunks: int = 8,
) -> str:
    """
    Triaj kararı için optimize edilmiş multi-query RAG retrieval.

    Strateji:
    1. Ana şikayet ile genel arama (Çeviri katmanıyla — herhangi bir dil)
    2. Triaj protokolü odaklı arama ("triage assessment " + şikayet)
    3. Acil protokol odaklı arama ("emergency RED urgency " + şikayet)
    4. Sonuçları de-duplicate + kategori önceliğine göre sırala
    5. En alakalı max_chunks chunk'ı yapılandırılmış formatta döndür

    Bu sayede:
    - Genel vektör araması gözden kaçırabileceği protokol chunk'ları yakalanır
    - Emergency/triage kategorileri her zaman üste gelir
    - Doğruluk artar, gürültü azalır
    - Türkçe, İngilizce veya başka dilde girilen şikayetler aynı doğrulukla çalışır
    """
    if not is_rag_available():
        return ""

    try:
        collection = _get_collection()
        if collection.count() == 0:
            return ""

        complaint_lower = chief_complaint.lower().strip()

        # ── Çeviri katmanı: şikayeti İngilizce'ye çevir ──────────
        complaint_en = translate_query_to_english(chief_complaint)
        complaint_en_lower = complaint_en.lower().strip()

        # Multi-query stratejisi (orijinal + İngilizce çeviri)
        queries = [
            chief_complaint,                               # Orijinal dil
            complaint_en,                                  # İngilizce çeviri
            f"triage assessment {complaint_en_lower} emergency severity",
            f"Manchester Triage System {complaint_en_lower} red flags urgency",
        ]
        if qa_history:
            # Q&A geçmişinin ilk 200 karakterini ek sorgu olarak ekle
            queries.append(qa_history[:200])

        # Tüm query'lerden sonuç topla, ID'ye göre de-duplicate
        seen_docs: dict[str, dict] = {}  # doc_text → hit
        for q in queries:
            try:
                hits = retrieve(q, n_results=n_per_query)
                for h in hits:
                    if h["relevance"] < min_relevance:
                        continue
                    key = h["document"][:80]  # İçerik prefix'i ile de-dup
                    if key not in seen_docs or h["relevance"] > seen_docs[key]["relevance"]:
                        seen_docs[key] = h
            except Exception:
                continue

        if not seen_docs:
            return ""

        # Kategori önceliği + relevance ile sırala
        ranked = sorted(
            seen_docs.values(),
            key=lambda h: (
                CATEGORY_PRIORITY.get(h.get("category", "general"), 9),
                -h["relevance"],
            )
        )

        # En fazla max_chunks chunk al
        top = ranked[:max_chunks]

        # Yapılandırılmış prompt bağlamı oluştur
        lines = [
            "=== Klinik Karar Destek Bağlamı (RAG) ===",
            f"Şikayet: {chief_complaint}",
            "Aşağıdaki klinik kılavuz bilgileri bu triaj kararına yardımcı olmak için getirilmiştir:",
            "",
        ]
        # Kategorilere göre grupla
        by_cat: dict[str, list] = {}
        for h in top:
            cat = h.get("category", "general")
            by_cat.setdefault(cat, []).append(h)

        cat_labels = {
            "triage_protocol": "📋 TRİAJ PROTOKOLÜ",
            "emergency_protocol": "🚨 ACİL PROTOKOL",
            "clinical_guideline": "📖 KLİNİK KILAVUZ",
            "clinical_reference": "🔬 KLİNİK REFERANS",
            "icd10_codes": "🏷 ICD-10",
            "icd10_coding": "🏷 ICD-10",
            "epidemiology": "📊 EPİDEMİYOLOJİ",
            "terminology": "📝 TERMİNOLOJİ",
        }

        for cat_key in sorted(by_cat.keys(), key=lambda k: CATEGORY_PRIORITY.get(k, 9)):
            label = cat_labels.get(cat_key, f"[{cat_key}]")
            lines.append(f"{label}:")
            for h in by_cat[cat_key]:
                lines.append(f"  [{h['source']}] {h['document']}")
            lines.append("")

        lines.append(
            "⚕️ GÜVENLİK NOTU: Şüphe durumunda daima daha yüksek triaj seviyesi seç."
        )

        return "\n".join(lines)

    except Exception as e:
        logger.warning(f"get_medical_context_for_triage hatası: {e}")
        return ""


def get_db_stats() -> dict:
    """ChromaDB koleksiyon istatistiklerini döndürür."""
    try:
        collection = _get_collection()
        count = collection.count()
        # Kaynaklara göre dağılım
        if count > 0:
            sample = collection.get(limit=min(count, 1000), include=["metadatas"])
            sources = {}
            for m in sample["metadatas"]:
                s = m.get("source", "unknown")
                sources[s] = sources.get(s, 0) + 1
        else:
            sources = {}
        return {
            "total_chunks": count,
            "sources": sources,
            "embed_model": EMBED_MODEL_NAME,
            "chroma_dir": CHROMA_DIR,
        }
    except Exception as e:
        return {"error": str(e), "total_chunks": 0}


# ─────────────────────────────────────────────
#  Yerleşik Tıbbi Bilgi Tabanı (Bootstrap)
#  Sprint 16: Kapsamlı genişletme — 100+ chunk
# ─────────────────────────────────────────────
BUILTIN_MEDICAL_KNOWLEDGE = [

    # ════════════════════════════════════════
    #  1. MTS / CTAS TRİAJ PROTOKOLLERİ
    # ════════════════════════════════════════
    {
        "source": "MTS_Triage_Guide",
        "category": "triage_protocol",
        "text": """Manchester Triage System (MTS) 5 Seviyeli Triaj:
RED (Hemen/İmmediately): AMI, inme, anafilaksi, solunum yetmezliği, GCS<8, major travma, aort diseksiyonu, status epileptikus, hipertansif ensefalopati.
ORANGE (Çok Acil/Very Urgent, 10 dk): Göğüs ağrısı, akut konfüzyon, konvülsiyon (post-iktal), ciddi dispne (SpO2<90), taşikardi>150, ağır ağrı (8-10/10).
YELLOW (Acil/Urgent, 60 dk): Orta şiddetli ağrı (5-7/10), ateş >38.5°C, vomiting ≥4 kez, fraktur şüphesi, kan şekeri <60 veya >300.
GREEN (Standart/Standard, 120 dk): Hafif ağrı (<5/10), kronik şikayet alevlenmesi, küçük travma, üst solunum yolu enfeksiyonu, stabil kronik hastalık.
BLUE (Rutin/Non-urgent, 240 dk): Kronik hastalık kontrolü, reçete yenileme, bürokratik işlemler, hafif cilt sorunları."""
    },
    {
        "source": "MTS_Triage_Guide",
        "category": "triage_protocol",
        "text": """MTS Ağrı Değerlendirmesi — NRS (Numeric Rating Scale):
0: Ağrı yok
1-3: Hafif ağrı — GREEN triaj
4-6: Orta ağrı — YELLOW triaj
7-9: Şiddetli ağrı — ORANGE triaj
10: Dayanılmaz ağrı — RED triaj
Çocuklar için FLACC skalası veya Wong-Baker yüz skalası kullanılır.
Yaşlılarda ve kognitif bozukluğu olanlarda davranışsal ağrı işaretlerine dikkat: grimace, vücut gerginliği, ajitasyon."""
    },
    {
        "source": "MTS_Triage_Guide",
        "category": "triage_protocol",
        "text": """CTAS (Canadian Triage and Acuity Scale) Kriterleri:
Level 1 — Resüsitasyon (Hemen): Solunum durması, kardiyak arrest, GCS<9, şok, anafilaksi
Level 2 — Acil (15 dk): MI şüphesi, inme, ciddi solunum güçlüğü, sepsis belirtileri, hipertansif kriz
Level 3 — İvedi (30 dk): Şiddetli ağrı, yüksek ateş ≥38.5°C pediatrik, orta dehydration
Level 4 — Az İvedi (60 dk): Orta ağrı, vomiting <4 kez, küçük travma, stabil bulgular
Level 5 — Rutin (120 dk): Kronik şikayet, hafif semptom, takip ziyareti"""
    },
    {
        "source": "MTS_Discriminators",
        "category": "triage_protocol",
        "text": """MTS Anahtar Triaj Diskriminatörları:
Airway compromise (Hava yolu tehlikesi) → RESÜSİTASYON
Shock (Şok) → RESÜSİTASYON — KB<90 sistolik, perfüzyon kötü
Unconscious (Bilinçsiz) → RESÜSİTASYON
Recent fit (Son 30 dk içinde konvülsiyon) → ÇOK ACİL
Altered consciousness (Değişmiş bilinç) → ÇOK ACİL
Severe pain (Şiddetli ağrı >7/10) → ÇOK ACİL veya ACİL
Pyrexia (Ateş >38.5°C) → duruma göre ACİL
Vomiting (Kusma) → sıklık ve süreye göre değerlendirme"""
    },

    # ════════════════════════════════════════
    #  2. KARDİYAK ACİL PRROTOKOLLERİ
    # ════════════════════════════════════════
    {
        "source": "Cardiac_Emergency_Protocol",
        "category": "emergency_protocol",
        "text": """Akut Miyokard Enfarktüsü (AMI) — STEMI ve NSTEMI:
Klasik bulgular: Efor veya istirahat göğüs ağrısı/baskısı >20 dakika, sol kol/çene/sırt/epigastrik yayılım, diaforez, bulantı, dispne.
Atipik sunum (kadınlar, diyabetikler, yaşlılar): Yorgunluk, nefes darlığı, bulantı — göğüs ağrısı olmayabilir.
Risk faktörleri (TIMI skoru): Yaş >65, DM, HT, sigara, aile öyküsü, hiperlipidemi, önceki kardiyak olay.
Triaj: KESİNLİKLE RED — 12-derivasyon EKG <10 dk, troponin, aspirin 300mg po, O2 hedef SpO2>94%.
ST elevasyonu → STEMI aktivasyonu (kateter lab) derhal
ST depresyonu veya T dalgası değişikliği → NSTEMI/UA protokolü"""
    },
    {
        "source": "Cardiac_Emergency_Protocol",
        "category": "emergency_protocol",
        "text": """Hipertansif Kriz Yönetimi:
Hipertansif Acil (Emergency): KB >180/120 mmHg + organ hasarı
  - Ensefalopati (baş ağrısı, konfüzyon), eklampsi, MI, akut kalp yetmezliği, aort diseksiyonu, akut böbrek yetmezliği
  - TRİAJ: RED — IV antihipertansif, yoğun bakım
Hipertansif Urjansi (Urgency): KB >180/120 mmHg + organ hasarı YOK
  - TRİAJ: YELLOW/ORANGE — oral antihipertansif, 24-48 saat kontrolü
Sormak gereken: Kronik HT hikayesi? İlaç uyumsuzluğu? En yüksek KB değeri? Baş ağrısı şiddeti ve tipi? Görme bozukluğu? Göğüs ağrısı?"""
    },
    {
        "source": "Cardiac_Emergency_Protocol",
        "category": "emergency_protocol",
        "text": """Kalp Yetmezliği Akut Dekompansasyonu:
Bulgular: Ortopne (yatınca nefes darlığı), PND (gece nefes darlığı), bilateral bacak ödemi, pembe köpüklü balgam.
Fizik muayene: Bilateral raller, S3 gallop, juguler venöz dolgunluk.
Hızlı BNP artışı, SpO2 <90%, solunum sıkıntısı → RED triaj.
Tetikleyiciler: İlaç uyumsuzluğu (diüretik atlanması), aşırı tuz/su alımı, AF gelişimi, enfeksiyon (pnömoni).
Sorulacak: Mevcut kalp hastalığı? Ne zamandan beri ödemi var? Kaç yastıkla uyuyor? Yakın zamanda kilo aldı mı?"""
    },
    {
        "source": "Cardiac_Emergency_Protocol",
        "category": "emergency_protocol",
        "text": """Palpitasyon ve Aritmi Değerlendirmesi:
Taşikardi >150 atım/dk → ORANGE triaj (AF hızlı yanıtlı, SVT, VT)
Bradikardi <40 atım/dk + senkop/hipotansiyon → RED (tam kalp bloğu)
Palpitasyon + göğüs ağrısı veya senkop → ORANGE — EKG acil
Ayrımsal tanı: sinüs taşikardisi, AF, VT, SVT, WPW
Sorulacak: Başlangıç ani mi yavaş mı? Ritim düzenli mi? Baş dönmesi veya senkop oldu mu? Daha önce aritmi tanısı var mı?"""
    },
    {
        "source": "Cardiac_Emergency_Protocol",
        "category": "emergency_protocol",
        "text": """Senkop (Bayılma) Kırımızı Bayrakları (Cardiac vs Vasovagal):
KARDİYAK SENKOP — yüksek risk (RED/ORANGE):
  - Egzersiz sırasında bayılma
  - Pozisyondan bağımsız ani senkop
  - EKG anormalliği
  - Bilinen kardiyak hastalık veya kalp yetmezliği
  - Ailede ani ölüm hikayesi
  - Senkop öncesi palpitasyon
VAZOVAGAl SENKOP — düşük risk (GREEN/YELLOW):
  - Uzun dik durma veya kalabalık ortam
  - Prodrom: terleme, bulanık görme, bulantı
  - Prodromun ardından tam bilinç kaybı
  - Hızlı iyileşme (dakikalar içinde)"""
    },

    # ════════════════════════════════════════
    #  3. NÖROLOJİK ACİL
    # ════════════════════════════════════════
    {
        "source": "Neurological_Emergency",
        "category": "emergency_protocol",
        "text": """İnme (Serebrovasküler Hastalık) — FAST+ Değerlendirmesi:
F — Face (Yüz): Yüzde asimetri, ağız kenarı sarkması
A — Arm (Kol): Kol gücüsüzlüğü, her iki kolu kaldırma testi
S — Speech (Konuşma): Afazi, dizartri, anlamsız konuşma
T — Time (Zaman): Semptom başlangıç saati — tPA penceresi 4.5 saat, trombektomi 24 saate kadar
B — Balance (Denge): Ani denge kaybı, koordinasyon bozukluğu
E — Eyes (Gözler): Horizontale gaze deviyasyonu, görme alanı defekti, diplopi
TRİAJ: KESİNLİKLE RED — Kod İnme aktivasyonu, beyin BT acil
Sormak gereken: Tam olarak ne zaman başladı? İlk belirtisi ne oldu? Antikoagülan veya antiagregan kullanıyor mu?"""
    },
    {
        "source": "Neurological_Emergency",
        "category": "emergency_protocol",
        "text": """Baş Ağrısı Kırmızı Bayrakları (Thunderclap & Red Flags):
SUBARAKNOID KANAMA: "Hayatımın en şiddetli baş ağrısı", ani başlangıç, ense sertliği, fotofobi, bulantı/kusma
MENENJİT: Ateş + ense sertliği + fotofobi üçlüsü = Kernig ve Brudzinski pozitif
HIPERTANSIF ENSEFALOPATİ: KB >180 + baş ağrısı + konfüzyon + görme bozukluğu
SEREBRAL VENÖZ TROMBOZ: Subakut ilerleyen baş ağrısı + fokal nörolojik semptom + papil ödem
POSTKOİTAL BAŞAĞRISI: Cinsel aktivite sırasında ani baş ağrısı
Bütün bu durumlar → RED triaj, BT ve LP değerlendirmesi
ALARM İPUÇLARI: Progresif kötüleşme, pozisyona bağımlılık, 50 yaş üzeri ilk baş ağrısı, malignitesi olan hasta"""
    },
    {
        "source": "Neurological_Emergency",
        "category": "emergency_protocol",
        "text": """Konvülsiyon ve Epilepsi Acil Yönetimi:
Status Epileptikus: >5 dakika konvülsiyon veya bilinç geriye dönmeden 2+ nöbet → RED (Benzodiazepin IV)
İlk kez konvülsiyon → ORANGE (EEG, görüntüleme, elektrolitler)
Bilinen epilepsi + tek nöbet + tam iyileşme → YELLOW
Sormak gereken: Nöbet ne kadar sürdü? Fokal mı generalize mi? Nöbet sonrası bilinç ne kadar kuvvetliydi? İlaç kesimi var mı? Ateş veya enfeksiyon var mı? Yakın kafa travması?
Tetikleyiciler: İlaç uyumsuzluğu, alkol çekilmesi, hipoglisemi, hiponatremi, enfeksiyon"""
    },
    {
        "source": "Neurological_Emergency",
        "category": "emergency_protocol",
        "text": """Bilinç Değişikliği Yönetimi — AEIOU TIPS:
A — Alcohol (Alkol/madde intoksikasyonu)
E — Epilepsy (Epilepsi, post-iktal durum)
I — Insulin (Hipoglisemi/hipergliemi)
O — Opiate/Overdose (İlaç aşımı)
U — Uremia (Üremik ensefalopati, karaciğer yetmezliği)
T — Trauma (Kafa travması, subdural hematom)
I — Infection (Menenjit, ensefalit, sepsis)
P — Psychiatric (Psikiyatrik kriz, konversiyon)
S — Stroke/Shock (İnme, şok)
GCS <14 → minimum ORANGE, GCS <9 → RED"""
    },

    # ════════════════════════════════════════
    #  4. SOLUNUM ACİLLERİ
    # ════════════════════════════════════════
    {
        "source": "Respiratory_Protocol",
        "category": "emergency_protocol",
        "text": """Solunum Sıkıntısı Değerlendirmesi — SpO2 ve Klinik:
SpO2 >94%, istirahat halinde rahat → GREEN/YELLOW
SpO2 90-94%, hafif dispne, yardımcı kaslar aktif → YELLOW/ORANGE
SpO2 <90% veya <92% (KOAH'lı hastada <88%) → RED acil oksijen
Siyanoz (periferik veya santral), konfüzyon, bilinç bozukluğu ile dispne → RED
Solunum hızı >30/dk → ciddi sıkıntı işareti → ORANGE/RED
Tanımlayıcı sorular: İstirahat halinde mi var? Başlangıç ani mi? Balgam rengi ve miktarı? Ateş eşlik ediyor mu? Bilinen astım veya KOAH?"""
    },
    {
        "source": "Respiratory_Protocol",
        "category": "emergency_protocol",
        "text": """Astım Akut Atağı Şiddet Sınıflandırması:
Hafif Atak: Konuşma cümle tam, SpO2>95%, SS<25/dk → YELLOW
Orta Atak: Konuşma kısa cümleler, SpO2 91-95%, SS>25/dk, yardımcı kaslar hafif → ORANGE
Ağır Atak: Sadece kelime konuşabiliyor, SpO2<91%, SS>30/dk, belirgin yardımcı kas kullanımı, hırıltı yoğun → RED
Hayatı Tehdit Eden: Siyanoz, oksijen satürasyonu ölçülemiyor, bradikardi, "sessiz akciğer" (yeterli hava girmesi yok) → RESÜSİTASYON
Fırtına uyarısı: Hasta konuşamıyor + terleme + acil his → derhal kırmızı triaj"""
    },
    {
        "source": "Respiratory_Protocol",
        "category": "emergency_protocol",
        "text": """Pnömotoraks Klinik Değerlendirmesi:
Ani başlayan göğüs ağrısı + dispne → pnömotoraks şüphesi (özellikle genç, uzun ince yapılı erkek)
Fizik muayene: Etkilenen tarafta solunum sesi azalmış, perküsyonda hipersonorite
Tansiyon pnömotoraks: Trakeal deviasyon, yükselen JVB, hipotansiyon → RED, acil iğne dekompresyonu
Spontan pnömotoraks — küçük (<2 cm): YELLOW
Spontan pnömotoraks — büyük veya belirtili: ORANGE/RED
NOTEkGEÇMİŞ: Daha önce pnömotoraks geçirdi mi? Akciğer hastalığı var mı? Son havacılık veya dalış aktivitesi?"""
    },
    {
        "source": "Respiratory_Protocol",
        "category": "emergency_protocol",
        "text": """Akciğer Embolisi (Pulmoner Emboli) Şüphesi:
Klinik bulgular: Ani başlayan dispne, plöritik göğüs ağrısı (nefesle artan), hemoptizi, taşikardi, hipoksi
Wells skoru yüksek + SpO2 düşük → RED
Risk faktörleri: Derin ven trombozu geçmişi, uzun immobilizasyon (seyahat, ameliyat), malinite, gebelik, OKS kullanımı
Sorulacak: Son uzun yolculuk veya ameliyat? Bacakta kızarıklık/şişlik/ağrı? Nefes darlığı başlangıcı ani mi?
Pulsoksimetre düşüklüğü açıklanamıyorsa PE'yi düşün"""
    },

    # ════════════════════════════════════════
    #  5. KARİN ACİLLERİ
    # ════════════════════════════════════════
    {
        "source": "Abdominal_Pain_Guide",
        "category": "clinical_guideline",
        "text": """Karın Ağrısı Sistematik Değerlendirmesi:
RİJİDİTE/DEFANS: Karın sert gibiyse → perforasyon, peritonit → RED
SAĞ ALT KADRAN: McBurney hassasiyeti + ateş + iştahsızlık + bulantı → Apandisit → ORANGE
SAĞ ÜST KADRAN: Safra kesesi ağrısı (yağlı yemek sonrası), Murphy pozitif → Kolesistit → ORANGE/YELLOW
EPİGASTRİK: Sırt yayan şiddetli ağrı + ateşsiz + bulantı → Pankreatit → ORANGE/RED
CHARCOT TRİADI (ateş + sarılık + sağ üst kadran ağrısı) → Kolanjit → RED
LOKASYON-TANI İPUCU:
  - Sağ alt kadran: Apandisit
  - Sol alt kadran: Sigmoid divertiküliti
  - Orta karın/göbek: Erken apandisit, aort anevrizması"""
    },
    {
        "source": "Abdominal_Pain_Guide",
        "category": "clinical_guideline",
        "text": """Karın Ağrısı Kadın Hastalarda Özel Değerlendirme:
EKTOPİK GEBELİK: Tek taraflı alt karın ağrısı + vaginal kanama + gebe olabilir → RED (rüptür riski hayati tehlike)
OVARİAN TORSİYON: Ani başlayan şiddetli alt karın ağrısı + bulantı ultrasoundda ödem → ORANGE
PELVİK İNFLAMATUAR HASTALLIK (PID): Alt karın ağrısı + servikal hareket hassasiyeti + ateş → ORANGE
MİTTELSCHMERZ (ovülasyon ağrısı): Ay ortasında tek taraflı hafif ağrı → GREEN
Sorulacak: Son adet tarihi? Hamilelik ihtimali? Vaginal akıntı veya kanama var mı? Cinsel aktif mi?"""
    },
    {
        "source": "Abdominal_Pain_Guide",
        "category": "clinical_guideline",
        "text": """Gastrointestinal Kanama Değerlendirmesi:
Hematemez (kanlı kusma): ÜST GIS → RED/ORANGE (peptik ülser, özofageal varis rüptürü)
Melena (siyah katran dışkı): ÜST GIS veya sağ kolon → ORANGE/RED
Hematokezi (kırmızı kan dışkısı): ALT GIS (hemoroid, divertikül, kolorektal karsinom) → YELLOW/ORANGE
Dev hematemez + hipotansiyon → RED (özofageal varis rüptürü → vakit kaybetme)
Sorulacak: Ne kadar kan? Dışkı rengi nasıl? NSAİİ veya aspirin kullanımı? Karaciğer hastalığı veya siroz geçmişi? Antikoagülan kullanımı?"""
    },

    # ════════════════════════════════════════
    #  6. ENDOKRIN ACİLLER
    # ════════════════════════════════════════
    {
        "source": "Endocrine_Emergency",
        "category": "emergency_protocol",
        "text": """Hipoglisemi Değerlendirmesi ve Yönetimi:
Hafif (Bilinç açık): Titreme, terleme, çarpıntı, açlık hissi, KB<70 mg/dL → hasta oral seker alabiliyorsa YELLOW
Orta: Konfüzyon, baş dönmesi, koordinasyon bozukluğu → hasta yardım gerektirir → ORANGE
Ağır: Bilinç kaybı, konvülsiyon → IV dekstroz gerekli → RED
Hipoglisemi kardiyak aritmiyi tetikleyebilir / miyokard iskemisini ağırlaştırabilir
Risk grupları: İnsülin veya sulfonilurea kullanan DM hastaları, alkol kullanımı, uzun süre aç kalma
Sorulacak: KB cihazı ölçümü var mı? Son insülin dozu ve zamanı? Son yemek ne zaman? Benzer durum daha önce oldu mu?"""
    },
    {
        "source": "Endocrine_Emergency",
        "category": "emergency_protocol",
        "text": """Hiperglisemik Aciller — DKA ve HHS:
Diyabetik Ketoasidoz (DKA):
  Bulgular: Dehidrasyon, kussmaul solunumu (derin hızlı nefes), aseton kokusu, karın ağrısı, KB>250 mg/dL
  Çoğunlukla Tip 1 DM → RED
Hiperozmolar Hiperglisemik Durum (HHS):
  Bulgular: Çok yüksek KB (>600 mg/dL), ağır dehidrasyon, konfüzyon/koma, asidoz yok
  Genellikle Tip 2 DM, yaşlı → RED
Sorulacak: Bilinen DM? Tip I mi Tip II mi? İnsülin kesimi var mı? Enfeksiyon geçiriyor mu? Bulantı/kusma var mı? İdrar miktarı azaldı mı?"""
    },
    {
        "source": "Endocrine_Emergency",
        "category": "emergency_protocol",
        "text": """Tiroid Fırtınası ve Miksödem Koması:
TİROİD FIRTINASI: Ateş >38.5 + ciddi taşikardi + hipertiroidizm + konfüzyon/ajitasyon → RED (nadir ama hayatı tehdit)
MİKSÖDEM KOMASI: Hipotermi + konfüzyon + hipoventilasyon + hipotiroidizm hastasında → RED
Adrenal Kriz (Addison krizi): Hipotansiyon + hiponatremi + hiperkalemi + steroid kullanan hasta → RED (IV steroid acil)"""
    },

    # ════════════════════════════════════════
    #  7. SEPSİS VE ENFEKSİYON
    # ════════════════════════════════════════
    {
        "source": "Sepsis_Protocol",
        "category": "emergency_protocol",
        "text": """Sepsis Erken Tanı — qSOFA ve SIRS:
qSOFA (≥2 kriter → sepsis şüphesi):
  1. Solunum hızı ≥22/dk
  2. GCS <15 (bilinç değişikliği)
  3. Sistolik KB ≤100 mmHg
SIRS (≥2 kriter):
  Ateş >38°C veya <36°C
  Nabız >90 atım/dk
  Solunum hızı >20/dk veya PaCO2<32
  Lökosit >12.000 veya <4.000 veya >%10 bant
Septik Şok = Sepsis + sıvıya dirençli hipotansiyon → RED, yoğun bakım
"Sepsis bundle": 1 saat içinde kan kültürü, IV antibiyotik, 30 mL/kg sıvı bolus"""
    },
    {
        "source": "Sepsis_Protocol",
        "category": "emergency_protocol",
        "text": """Sepsis Odak Değerlendirmesi:
ÜROGENİTAL (En sık): İdrar yaparken yanma, sık idrara çıkma, kostovertebral açı hassasiyeti, bulanık idrar
PNÖMONI: Öksürük, pürülan balgam, tek taraflı ral, ateş + lökositoz
BATINSAL: Apandisit, kolesistit, divertikülit, peritonit → defans/rijidite
DERI/YUMUŞAK DOKU: Nekrotizan fasiit — ağrı deri bulgularıyla orantısız, hızla ilerleyen şişlik, krepitasyon
MENENJİT: Ateş + ense sertliği + fotofobi = menenjit — LP öncesi BT gerekebilir
Özellikle immünosüpresif, yaşlı ve diyabetik hastalarda atipik prezentasyon olabilir"""
    },

    # ════════════════════════════════════════
    #  8. TRAVMA VE İNTOKSİKASYON
    # ════════════════════════════════════════
    {
        "source": "Trauma_Protocol",
        "category": "emergency_protocol",
        "text": """Kafa Travması Değerlendirmesi — GCS ve Kırmızı Bayraklar:
KIRMİZI BAYRAKLAR (CT gerektirir — RED/ORANGE):
  - GCS <15 veya progressif kötüleşme
  - 2+ kusma epizodu
  - Fokal nörolojik defisit
  - Konvülsiyon
  - Kafa kaidesi kırığı bulguları (Raccoon eyes, Battle's sign, hemotimpanum)
  - Antikoagülan kullanımı
  - Yaş >65 veya <2 yaş
  - Alkol veya madde altında eziyeti
  - Travma mekanizması ağır (trafik kazası, düşme)
GCS 15 + şikayetsiz + düşük risk mekanizması → GREEN (izlem)
KANAD Kuralı ve New Orleans Kuralı CT endikasyon kılavuzları kullanılabilir"""
    },
    {
        "source": "Trauma_Protocol",
        "category": "emergency_protocol",
        "text": """İlaç ve Madde Zehirlenmesi — Toksidrom Tanıma:
OPİYAT: Miyozis (iğne ucu pupil), solunum depresyonu, stupor/koma, bradikardi → Nalokson
ANTİKOLİNERJİK: Miidriazis, ağız kuruluğu, hipertermi, üriner retansiyon, ajitasyon, hasta çıplak ve kızarmış (atropin, TCA, antihistaminik)
KOLİNERJİK (ORGANOFOSFAT): SLUDGE: Salivasyon, Lakrimasyon, Üriner inkontinans, Diyare, GIS kramplar, Emesis + miosis, brokospazm → Atropin
SEMPATOMİMETİK (Kokain, amfetamin): Miidriazis, taşikardi, HT, ateş, ajitasyon, terleme
SEDATİF/HİPNOTİK: CNS depresyon, normal pupil, solunum depresyonu
Her intoksikasyon şüphesinde → ORANGE/RED, toksikoloji konsültasyonu"""
    },
    {
        "source": "Trauma_Protocol",
        "category": "emergency_protocol",
        "text": """Yanık Değerlendirmesi — Yüzde 9 Kuralı ve Derinlik:
YÜZEY:
  Baş/boyun: %9, Her kol: %9, Anterior gövde: %18, Posterior gövde: %18, Her bacak: %18, Genital bölge: %1
DERİNLİK:
  1. Derece: Yalnızca epidermis, kızarıklık, ağrılı → GREEN
  2. Derece (yüzeyel): Büller, ağrılı → YELLOW/ORANGE >%10
  2. Derece (derin): Büller olmayabilir, az ağrılı, soluk → ORANGE/RED
  3. Derece: Eskar, ağrısız, beyaz/siyah → RED
ACİL: Yüz/boyun/el/genital bölge yanıkları, inhalasyon yaralanması (saç yanar, is karası), >%20 YAKT → RED"""
    },

    # ════════════════════════════════════════
    #  9. PEDİATRİK VE JERİATRİK
    # ════════════════════════════════════════
    {
        "source": "Pediatric_Triage",
        "category": "clinical_guideline",
        "text": """Pediatrik Triaj Özel Kriterleri — PAT (Pediatric Assessment Triangle):
Görünüm (Tone, Interactiveness, Consolability, Look/Gaze, Speech/Cry) → Anormal ise kötü ipucu
Solunum Çalışması: İnterkoastal çekilme, burun kanatları solunumu, stridor, wheezing
Dolaşım Rengi: Pallor, siyanoz, mottling (beneklenme)
PAT + Vital Bulgular → Triaj kararı
<3 ay ateş ≥38°C: HEP RED — occult bakteremi, menenjit riski
1-3 yaş ateş ≥39°C: Klinik duruma göre ORANGE/YELLOW
>36 ay ateş ≥39°C: Klinik duruma göre YELLOW/GREEN
Fontanel bombeliği → Menenjit/hipertansif kriz → RED"""
    },
    {
        "source": "Pediatric_Triage",
        "category": "clinical_guideline",
        "text": """Pediatrik Solunum Değerlendirmesi — Stridor ve Wheezing:
KRUP (Laringotrakeobronşit): Havlayan öksürük + inspiratuar stridor + ateş, gece kötüleşir → ORANGE/YELLOW
EPİGLOTTİT: Yüksek ateş + drooling + yutma güçlüğü + tripod pozisyon + stridor → RED (airway tehlike)
BRONŞYOLIT: 0-2 yaş, RSV kışın, ekspiratuar wheeze, subcostal çekilme → SpO2'ye göre
YABANCI CİSİM: Ani başlayan unilateral wheeze, öksürük, öyküde yabancı cisim yutma → ORANGE/RED
PERTUSSIS: Öksürük + inspiratuar whoop + kusma, aşısız bebek → ORANGE"""
    },
    {
        "source": "Geriatric_Triage",
        "category": "clinical_guideline",
        "text": """Yaşlı Hasta Triaj Özel Dikkatler (≥65 yaş):
ATİPİK SUNUM: AMI'de göğüs ağrısı yerine halsizlik/konfüzyon, sepsiste ateş olmayabilir (hipotermi)
AKUT KONFİZYON (Delirium): Her yaşlıda delirium = altta yatan acil (enfeksiyon, AMI, inme, ilaç, metabolik)
DÜŞME: Kalça kırığı şüphesi — yürüyemiyor + ağrı → Görüntüleme (pelvis X-ray / BT)
POLİFARMASİ: ≥5 ilaç, ilaç-ilaç etkileşimi, ilaç toksisitesi (digoksin, warfarin)
SOSYAL BAĞLAM: Bakıcısı kim? Bağımsız yaşıyor mu? Basit hayati belirtiler normal görünse de fonksiyonel düşüş önemli ipucu.
Yaşlıda AĞRI altriajlanabilir — ağrı kesicilerin etkisi azalmıştır, sessiz kalabilirler"""
    },
    {
        "source": "Geriatric_Triage",
        "category": "clinical_guideline",
        "text": """Yaşlıda Dehidrasyon ve Oral Alım Bozukluğu:
Bulgu: Ağız kuruluğu, göz içi çökmesi, turgor azalması, oligüri, bilinç bulanıklığı
Kapiler dolum >3 sn → Ciddi dehidrasyon → ORANGE
HT ilaçları alırken dehidrasyon → Böbrek yetmezliği riski artar
KVKK: Yaşlı hasta verisini aile üyesiyle paylaşmadan önce hastanın onayını al
Sorulacak: Son 24 saatte ne yedi/içti? Son idrara ne zaman çıktı? Dışkılama var mı?"""
    },

    # ════════════════════════════════════════
    #  10. VITAL BULGULAR REFERANS ARALIĞI
    # ════════════════════════════════════════
    {
        "source": "Vital_Signs_Reference",
        "category": "clinical_reference",
        "text": """Vital Bulgular Normal Değerleri — Yetişkin:
KB (Tansiyon): Sistolik 90-140 mmHg, Diastolik 60-90 mmHg
  Hipotansiyon: Sistolik <90 mmHg → Şok riski → ORANGE/RED
  Hipertansiyon Kriz: Sistolik >180 mmHg + semptom → ORANGE/RED
Nabız (Kalp Hızı): 60-100 atım/dk
  Taşikardi: >100/dk (>150/dk → ORANGE)
  Bradikardi: <60/dk (<40/dk + semptom → RED)
SpO2 (Oksijen Satürasyonu): %95-100
  Kabul edilebilir minumum: KOAH hastası %88-92, diğer hastalar >%94
  <90% → Tüm hastalarda oksijen başla → ORANGE/RED
Solunum Hızı: 12-20/dk
  Taşipne: >25/dk → ciddi solunum yükü
  Bradipne: <8/dk → solunum depresyonu → RED
Ateş: 36.1-37.2°C
  Düşük ateş: 37.3-38.0°C
  Ateş: >38.0°C
  Yüksek ateş: >39.0°C
  Hipotermi: <35.0°C → sepsis, şok, yaşlı"""
    },
    {
        "source": "Vital_Signs_Reference",
        "category": "clinical_reference",
        "text": """Pediatrik Vital Bulgular Normal Değerleri:
Nabız limitleri yaşa göre değişir:
  Yenidoğan: 120-160 atım/dk
  1-12 ay: 100-160 atım/dk
  1-3 yaş: 90-150 atım/dk
  3-5 yaş: 80-140 atım/dk
  6-12 yaş: 70-120 atım/dk
  >12 yaş: 60-100 atım/dk (yetişkin)
Solunum Hızı:
  Yenidoğan: 40-60/dk
  6-12 ay: 25-40/dk
  1-5 yaş: 20-30/dk
  >5 yaş: 15-20/dk
KB (Çocukta Hipotansiyon): Sistolik <70 + (2 × yaş) mmHg
SpO2: >95% tüm yaş gruplarında (yenidoğan geçiş dışı)"""
    },

    # ════════════════════════════════════════
    #  11. ICD-10 TÜRKÇE REFERANS
    # ════════════════════════════════════════
    {
        "source": "ICD10_Turkish_Reference",
        "category": "icd10_codes",
        "text": """ICD-10 Kardiyak Kodlar (Sık Acil Tanılar):
I21.0 — Anterior miyokard enfarktüsü (AMI anterior)
I21.1 — İnferior miyokard enfarktüsü (AMI inferior)
I21.9 — Akut miyokard enfarktüsü, tanımlanmamış (AMI NOS)
I22.9 — Ardışık miyokard enfarktüsü, tanımlanmamış
I20.0 — Kararsız angina (Unstable angina)
I47.1 — Supraventriküler taşikardi (SVT)
I48.0 — Paroksismal atriyal fibrilasyon (AF)
I49.01 — Ventriküler fibrilasyon (VF)
I50.0 — Konjestif kalp yetmezliği (KKY)
I11.0 — Kalp yetmezliği ile birlikte hipertansif kalp hastalığı
I27.0 — Primer pulmoner hipertansiyon
I71.0 — Torsade de pointes (yukan ise uzun QT)"""
    },
    {
        "source": "ICD10_Turkish_Reference",
        "category": "icd10_codes",
        "text": """ICD-10 Nörolojik Kodlar (Sık Acil Tanılar):
I63.9 — Serebral enfarkt, tanımlanmamış (İskemik İnme)
I61.9 — Serebral kanama (Hemorajik İnme)
I60.9 — Subaraknoid kanama (SAK)
G40.909 — Epilepsi, tanımlanmamış (Status epileptikus dahil)
G43.909 — Migren, tanımlanmamış
G44.309 — Küme baş ağrısı, tanımlanmamış
G89.29 — Diğer kronik ağrı (kronik ağrı sendromu)
R55 — Senkop ve kollaps
R41.3 — Diğer hafıza bozukluğu (demans muayene dahil)
G35 — Multipl skleroz (MS) yeni tanı veya atak"""
    },
    {
        "source": "ICD10_Turkish_Reference",
        "category": "icd10_codes",
        "text": """ICD-10 Solunum Kodları (Acil Başvuru):
J18.9 — Pnömoni, organizma tanımlanmamış
J45.901 — Akut şiddetli astım atağı (status asthmaticus)
J44.1 — KOAH akut alevlenme
J93.9 — Pnömotoraks, tanımlanmamış
J96.00 — Akut solunum yetmezliği, hipoksi ile (tip 1)
I26.99 — Pulmoner emboli, akut (PE)
R06.0 — Dispne (nefes darlığı)
R05 — Öksürük
R09.02 — Hipoksi (düşük oksijen satürasyonu, SpO2 düşüklüğü)"""
    },
    {
        "source": "ICD10_Turkish_Reference",
        "category": "icd10_codes",
        "text": """ICD-10 Karın/GIS Kodları (Acil):
K35.2 — Peritonitli akut apandisit
K80.0 — Kolesistit ile akut kolelitiyazis
K85.9 — Akut pankreatit, tanımlanmamış
K57.32 — Divetikülit, perforasyon veya apse olmaksızın, alt GIS
K92.0 — Hematemez (üst GIS kanama)
K92.1 — Melena (dışkıda siyah/katranımsı kan)
K25.0 — Akut gastrik ülser, kanama ile
R10.0 — Akut karın (peritonit bulguları)
N10 — Akut piyelonefrit (idrar yolu enfeksiyonu, böbrek tutulumu)"""
    },
    {
        "source": "ICD10_Turkish_Reference",
        "category": "icd10_codes",
        "text": """ICD-10 Travma ve Toksikoloji Kodları:
S09.90 — Baş yaralanması, tanımlanmamış
S02.90 — Kafatası kırığı, kapalı
T39.9 — Analjezik ilaç zehirlenmesi (aspirin, NSAİİ)
T36-T50 — İlaç zehirlenmesi genel kodu grubu
T14.91 — İntihar girişimi
T07 — Çoklu yaralanma
T30.0 — Vücut alanı tanımlanmamış yanık, 1. derece
S72.0 — Femur boynu kırığı (kalça kırığı, yaşlılarda sık)
T74.01 — Çocuk ihmali
W18.30 — Düşme, tanımlanmamış"""
    },
    {
        "source": "ICD10_Turkish_Reference",
        "category": "icd10_codes",
        "text": """ICD-10 Endokrin ve Metabolik Kodlar:
E11.65 — Tip 2 DM, hiperglisemik koma ile
E11.641 — Tip 2 DM, hipoglisemi ile, bilinç kaybı
E10.10 — Tip 1 DM, ketoasidoz ile (DKA)
E87.1 — Hiponatremi
E87.5 — Hiperkalemi
E83.51 — Hiperkalsemi
E05.5 — Tiroid krizi (tiroid fırtınası)
E03.5 — Miksödem koma
E27.1 — Birincil adrenokortikoid yetmezliği (Addison hastalığı)
E23.0 — Hipopitüitarizm"""
    },

    # ════════════════════════════════════════
    #  12. İLAÇ REAKSİYONLARI VE ALERJİ
    # ════════════════════════════════════════
    {
        "source": "Allergy_Drug_Protocol",
        "category": "clinical_reference",
        "text": """Anafilaksi Tanı ve Acil Yönetimi:
TANIM: ≥1 organ sisteminde şiddetli alerjik reaksiyon, sıklıkla kombine (deri + solunum + dolaşım)
KLİNİK: Kurdeşen/anjioödem + solunum sıkıntısı + hipotansiyon → RED — epinefrin 0.5 mg IM
HAFIF ALERJİ: Yalnızca deri (kurdeşen) → GREEN/YELLOW — oral antihistaminik
Tetikleyiciler: İlaç (penisilin en sık), besin (fındık, balık), arı sokması, lateks
SORULACAK: Daha önce alerji geçirdi mi? Hangi ilaca veya yiyeceğe? Epi-kalem taşıyor mu?
Anafilaksi → Yatı + 4-8 saat gözlem (bifazik reaksiyon riski)"""
    },
    {
        "source": "Allergy_Drug_Protocol",
        "category": "clinical_reference",
        "text": """Sık İlaç Alerjileri ve Çapraz Reaksiyon:
PENİSİLİN ALERJİSİ: Sefalosporin cross-reaksiyon ~%1-2 (eskiden >%10 sanılıyordu)
  Gerçek penisilin alerjisi: Beta-laktam grubu dikkatli kullanılmalı, mümkünse alternatif tercih
NSAİİ/ASPİRİN: Astım hastalarında NSAID-exacerbated respiratory disease (AERD/Samter sendromu)
KONTRASt MADDE: Önceki reaksiyon varsa premedikasyon protokolü (steroid + antihistaminik)
IYOT ALERJİSİ: Kontrast maddeye respons sistematik değil, deniz mahsulleri alerjisi iyot alerjisini göstermez
SULFA (TMP-SMX): Sulfonamid grubu reaksiyon, diüretiklerle çapraz reaksiyon nadir
KVKK: Alerji bilgisi hasta rızası olmadan üçüncü tarafla paylaşılamaz"""
    },
    {
        "source": "Allergy_Drug_Protocol",
        "category": "clinical_reference",
        "text": """Sık İlaç Etkileşimleri (Klinik Önem Taşıyanlar):
WARFARIN + NSAİİ → Kanama riski artar
WARFARIN + Antibiyotik (flukonazol, metronidazol) → INR yükselir
ACEİ/ARB + Potasyum tutucu diüretik (spironolakton) → Hiperkalemi
ASPİRİN + NSAİİ → Antiplatelet etki azalır
QT uzatan ilaçlar (amiodaron, sitalopram, klorokin) + başka QT uzatan → Torsade riski
METFORMIN + Kontrast madde → GFR <30 ise kontrast nefropati + laktik asidoz riski
OKS (Oral Kontraseptif) + Rifampisin/fenitoin → OKS etkisi azalır → Gebelik riski"""
    },

    # ════════════════════════════════════════
    #  13. TÜRKİYE ACİL SERVİS BAĞLAMI
    # ════════════════════════════════════════
    {
        "source": "Turkey_Emergency_Context",
        "category": "clinical_reference",
        "text": """Türkiye Acil Servis İstatistikleri ve Bağlamı:
Türkiye'de yıllık acil servis başvurusu: ~117 milyon (2023 SB verileri)
Günlük başvuru: ~320.000 (büyük şehirlerde yoğunluk)
Yeşil (GREEN) kategorisi: Başvuruların yaklaşık %60-70'i → Yönlendirilebilir vakalar
Acil servis triaj kategorileri Türkiye'de: Kırmızı/Sarı/Yeşil renk kodu (MTS uyumlu)
Ortalama bekleme süresi: İkinci ve üçüncü basamak hastanelerde 1-4 saat
ASM (Aile Sağlığı Merkezi): Hafif vakaların %40'ını üstlenebilir → Acil servisi boşaltır
112 Acil: Karmaşık yaralanma, kardiyak arrest, inme aktivasyonu için → Doğrudan sahaya
Başvuru pik saatleri: 08-12 arası ve 18-22 arası"""
    },
    {
        "source": "Turkey_Emergency_Context",
        "category": "clinical_reference",
        "text": """KVKK (Kişisel Verilerin Korunması Kanunu) ve Sağlık Verisi:
Türkiye KVKK (6698 sayılı kanun): Özel nitelikli kişisel veri kategorisinde sağlık verileri
Hasta verisi işleme: Açık rıza zorunlu (Acil durum istisnaları hariç)
Veri saklama süresi: Hasta dosyaları asgari 10 yıl (sağlık tesisi ruhsatı iptalinde asgari 20 yıl süresiyle)
Hasta hakları: Verilerine erişim, düzeltme, silme hakkı (silme acil durumda verinin aktif tutulması süreciyle çelişmez)
AnamnezAI veri güvenliği: Tüm veriler Ollama (yerel) üzerinde işlenir — buluta gitmez → KVKK uyumlu
Pseudonimizasyon: Analitik raporlama için hasta ismi kaldırılır"""
    },
    {
        "source": "Turkey_Emergency_Context",
        "category": "clinical_reference",
        "text": """Türkiye Birinci Basamak Sağlığa Başvuru Nedenleri (Sıklık Sırasına Göre):
1. Üst solunum yolu enfeksiyonları (ÜSYE) /%30 — GREEN çoğu zaman
2. Hipertansiyon takibi — GREEN
3. Diyabet takibi — GREEN
4. Kas-iskelet sistemi ağrıları (sırt, bel, eklem) — GREEN/YELLOW
5. Deri sorunları (egzama, ürtiker) — GREEN
6. Gastrointestinal şikayetler (bulantı, ishal) — GREEN/YELLOW
7. Göğüs ağrısı (kardiyak veya non-kardiyak) — YELLOW/RED
8. Baş ağrısı — GREEN/YELLOW (RED bayraklar aranmalı)
9. İdrar yolu enfeksiyonu — YELLOW (komplike ise ORANGE)
10. Anksiyete, depresyon — GREEN (akut psikiyatrik kriz ORANGE)"""
    },

    # ════════════════════════════════════════
    #  14. TIBBİ TERMİNOLOJİ TÜRKİYE
    # ════════════════════════════════════════
    {
        "source": "Medical_Terminology_TR",
        "category": "terminology",
        "text": """Klinik Tıp Terimleri — Türkçe (A-D):
Akut: Ani başlayan, kısa süreli
Anafilaksi: Ağır alerjik reaksiyon, sistemik, can tehdit edici
Anjiyoödem: Derin deri/mukoza şişmesi, hava yolunu tehdit edebilir
Apne: Oluşum yokluğu, solunumun durması
Aritmia/Aritmi: Kalp ritim bozukluğu
Atelektazi: Akciğer lobunun çökmesi
Bradikardi: Yavaş kalp atışı (<60/dk)
Bradipne: Yavaş solunum (<12/dk)
Bilirubin: Karaciğer fonksiyon belirteci, sarılık
BT/CT: Bilgisayarlı Tomografi — görüntüleme yöntemi
Dehidrasyon: Vücut suyunun azalması
Deliryum: Akut konfüzyon durumu, bilinç dalgalanması
Diaphoresis/Diyaforez: Soğuk terleme
Diplopi: Çift görme
Dispne: Nefes darlığı subjektif hissi
Disüri: İdrar yaparken ağrı/yanma"""
    },
    {
        "source": "Medical_Terminology_TR",
        "category": "terminology",
        "text": """Klinik Tıp Terimleri — Türkçe (E-N):
Edema/Ödem: Doku içinde sıvı birikmesi, şişlik
Ekimoz: Deri altı kanama, morluk
Epigastrik: Mide bölgesi, karın ortası üstü
Epistaksis: Burun kanaması
Hematemez: Kanlı kusma
Hematüri: İdrarda kan
Hemipleji: Tek taraflı felç
Hemoptizi: Balgamla kan gelmesi
Hipertansiyon: Yüksek kan basıncı (sistolik >140 mmHg)
Hipoglisemi: Düşük kan şekeri (<70 mg/dL)
Jaundis/Sarılık: Bilirubin artışına bağlı deri, mukoza ve göz beyazlarında sarı renk
Konfüzyon: Bilinç bulanıklığı, oryantasyon bozukluğu
Miyozis: Pupil daralması
Miydriazis: Pupil büyümesi
Nöropati: Sinir hasarı"""
    },
    {
        "source": "Medical_Terminology_TR",
        "category": "terminology",
        "text": """Klinik Tıp Terimleri — Türkçe (O-Z):
Oligüri: Az idrar çıkışı (<500 mL/gün yetişkin)
Pallor: Solgunluk
Parezi: Kısmi güçsüzlük
Peteşi: Küçük deri içi kanama noktaları
Plöritis: Akciğer zarı iltihabı, nefesle artan ağrı
Presenkop: Bayılma hissi, tam kayıp öncesi
Pürülan: İrinli
Raller: Akciğer oskültasyonunda ıslak sesler (pnömoni, kalp yetmezliği)
Rijidite: Kas sertliği (batın muayenesinde defans, nörolojide menjit)
Siyanoz: Mavimsi renk değişikliği (SpO2 düşüklüğü)
Senkop: Bilinç kaybı, kendiliğinden toparlama
Stidor: Üst hava yolu obstrüksiyonunda yüksek perdeli soluk sesi
Taşikardi: Hızlı kalp atışı (>100/dk)
Taşipne: Hızlı solunum (>20/dk)
Troponin: Miyokard hasarını gösteren biyobelirteç (AMI tanısında altın standart)
Üremi: Böbrek yetmezliğinde üre birikimi, nörolojik belirtiler
Vertigo: Dönme hissi (sistemik vestibüler patoloji)"""
    },

    # ════════════════════════════════════════
    #  15. TIBBİ SORGULAMA METODOLOJISI
    # ════════════════════════════════════════
    {
        "source": "Clinical_Assessment_Methods",
        "category": "clinical_reference",
        "text": """OPQRST Ağrı Değerlendirme Aracı (Anamnez):
O — Onset (Başlangıç): Ani mı yoksa yavaş mı başladı? Ne yapıyordunuz?
P — Provocation/Palliation (Artıran/Azaltan): Ne zaman şiddetleniyor? Nefes almakla mı? (plöritis), eforla mı? (kardiyak), yemekten sonra mı? (GIS)
Q — Quality (Kalite): Baskı mı (kardiyak), keskin mi (pnömotoraks), künt mü (kas), yanıcı mı (gastrik)
R — Radiation (Yayılım): Sol kol/çene → AMI; sırta yayılım → aort diseksiyonu/pankreatit; kasığa yayılım → böbrek taşı
S — Severity (Şiddet): 0-10 skalada kaç? (NRS)
T — Time (Zaman): Ne kadar süredir? Sürekli mi aralıklı mı?"""
    },
    {
        "source": "Clinical_Assessment_Methods",
        "category": "clinical_reference",
        "text": """SAMPLE Anamnez Çerçevesi:
S — Signs/Symptoms (Belirtiler): Ana şikayet ve eşlik eden belirtiler
A — Allergies (Alerjiler): İlaç, besin, lateks alerjisi var mı?
M — Medications (İlaçlar): Hangi ilaçları kullanıyor? Dozlar? Son dozu ne zaman?
P — Pertinent Medical History (İlgili Tıbbi Geçmiş): Kronik hastalıklar, önceki ameliyatlar?
L — Last Oral Intake (Son Ağızdan Alım): En son ne yedi/içti ve ne zaman? (anestezi, GIS değerlendirme)
E — Events Prior to Illness (Başvuru Öncesi Olaylar): Ne yapıyordunuz? Nerede başladı?"""
    },
    {
        "source": "Clinical_Assessment_Methods",
        "category": "clinical_reference",
        "text": """Hasta Güvenliği ve Tıp Hataları Önleme:
5 Doğru: Doğru hasta, doğru ilaç, doğru doz, doğru yol, doğru zaman
İlaç hataları en sık: İsim benzerliği (LASA drugs), bozuk ondalıklı yazım, sözlü order
Risk faktörleri: Polifarmasi, doz hesaplama (pediatri, böbrek yetm.), high alert ilaçlar (insülin, warfarin, heparin)
Kayıt: Her müdahale tarih/saat ile kayıt altına alınmalı
Geri bildirim döngüsü: Hasta durumu kötüleşirse yeniden triaj — başlangıç triajı değiştirilebilir (triaj süreci dinamik)
Hasta kimlik doğrulama: İsim + doğum tarihi ile doğrula (oda numarası veya yatak yeterli değil)"""
    },

    # ════════════════════════════════════════
    #  16. OBSTETRİ VE JİNEKOLOJİ ACİLLER
    # ════════════════════════════════════════
    {
        "source": "OB_GYN_Emergency",
        "category": "emergency_protocol",
        "text": """Gebelik Acilleri — Birinci Trimester:
EKTOPİK GEBELİK: Amenore + vajinal kanama + karın ağrısı → RED (rüptür = hayatı tehdit)
  En sık lokasyon: Tuba uterina (%95). Kültür kanamasından farklı: küçük miktarda, koyu, aralıklı
DÜŞÜK (Abort): Vajinal kanama + kasılma → Abortus imminens/incomplete. Serviks açık mı?
HIPEREMEZIS GRAVİDARUM: Şiddetli bulantı/kusma, kilo kaybı, ketonüri → Dehidrasyon → YELLOW/ORANGE
Beta-hCG + Transvajinal USG → Kesin tanı için
Sorulacak: Son adet tarihi kesin mi? Gebe olabilir mi? Vajinal kanama veya akıntı var mı?"""
    },
    {
        "source": "OB_GYN_Emergency",
        "category": "emergency_protocol",
        "text": """Gebelik Acilleri — İkinci/Üçüncü Trimester:
PREEKLAMPSİ: HT (>140/90) + proteinüri + ≥20hf gebelik → ORANGE
EKLAMPSİ: Preeklampsi + konvülsiyon → KESİNLİKLE RED (IV MgSO4, antihipertansif)
PLASENTA PREVİA: Ağrısız parlak kırmızı vajinal kanama, gebelikte → RED
PLASENTA DEKOLMANI: Vajinal kanama + karın ağrısı/sertliği + fetal kalp ritim bozukluğu → RED
HELLP SENDROMU: Hemoliz + yüksek karaciğer enzimleri + düşük trombosit → RED
PREMATURİTE TEHDIDI: <37 hf + düzenli kontraksiyonlar + serviks değişimi → ORANGE
Tüm gebelik acillerinde: Gebelik haftası, fetal hareket varlığı, daha önce ultrason?"""
    },

    # ════════════════════════════════════════
    #  17. PSİKİYATRİK ACİLLER
    # ════════════════════════════════════════
    {
        "source": "Psychiatric_Emergency",
        "category": "emergency_protocol",
        "text": """Psikiyatrik Acil Değerlendirmesi — Güvenlik Önce:
İNTİHAR RİSKİ DEĞERLENDİRMESİ:
  Yüksek risk (RED): Plan var, araç erişimi var, yakın girişim geçmişi, aktif psikoz, ciddi madde kullanımı
  Orta risk (ORANGE): Düşünceler var ama plan/araç yok
  Düşük risk (YELLOW): Pasif ölüm isteği, destek mekanizmaları mevcut
SORULACAK (nazikçe): "Kendinize zarar vermeyi veya yaşamınıza son vermeyi düşünüyor musunuz?" — direkt sormak gerekli
Psikoz (sanrı/halüsinasyon) + ajitasyon → ORANGE/RED (kendine veya başkalarına tehlike)
AKİL (MADDE + PSQ + SUI): Madde entoksikasyonu her psikiyatrik tabloyu taklit edebilir — önce tıbbi nedenler dışlanmalı"""
    },
    {
        "source": "Psychiatric_Emergency",
        "category": "emergency_protocol",
        "text": """Ajitasyon ve Agresyon Yönetimi Acil Serviste:
Sözel de-eskalayon önce: Sakin konuşma, alan ver, tehdit etme, isteklerini dinle
Fiziksel kısıtlama: Son seçenek, ekip işi, dökümantasyon zorunlu
Farmakoterapiye erken başla (belirsizse): IM lorazepam veya IM haloperidol
Ayırıcı tanı: Deliryum (tıbbi neden!), intoksikasyon, hipoglisemi, hipertiroidizm, temporal epilepsi
Yatış endikasyonları: Aktif intihar riski, aktif psikoz, stabilize edilemeyen ajitasyon
Alkol yoksunluğu: Tremor + taşikardi + hipertansiyon + terle → Delirium tremens riski → ORANGE"""
    },

    # ════════════════════════════════════════
    #  18. TAMMEMLEYİCİ KLİNİK PROTOKOLLER
    # ════════════════════════════════════════
    {
        "source": "Clinical_Protocols_Misc",
        "category": "clinical_reference",
        "text": """Böbrek Taşı (Üriner Kolik) Değerlendirmesi:
Bulgular: Bulgusu olan bir taraftaki lomber/yan ağrı, testise veya labiya majora'ya yayılım, bulantı/kusma, hematüri
Ağrı şiddeti: Çoğunlukla >7/10 → ORANGE
Komplikasyon şüphesi (RED/ORANGE): Ateş (enfekte taş, urosepsis), tek böbrek, iki taraflı tıkanma, şiddetli bulantı, böbrek yetmezliği
Sorulacak: Daha önce böbrek taşı geçirdi mi? Son yirmi dört saatte ne kadar su içti? Hematüri var mı? Ateş var mı?
Güçlü analjezik (IV ketorolak veya IV metamizol) + IV sıvı, US veya BT"""
    },
    {
        "source": "Clinical_Protocols_Misc",
        "category": "clinical_reference",
        "text": """Derin Ven Trombozu (DVT) Klinik Değerlendirmesi:
Klinik Bulgular: Unilateral bacak şişliği (>3 cm fark), kızarıklık, ısı artışı, Homans işareti (güvenilmez)
Wells DVT Skoru:
  Aktif malinite: +1
  Yatak istirahati veya büyük cerrahi son 4 hf: +1
  Alt ekstremite tüm kol şişliği: +1
  Baldırda >3 cm şişme: +1
  Basıya hassas yüzeyel venler: +1
  Önceki DVT: +1
  Alternatif tanı eşit olasılıklı: -2
Score ≥2 → Yüksek olasılık → Doppler US ve antikoagülan değerlendirmesi
Proksimal DVT (popliteal ve üzeri) → PE riski yüksek → ORANGE"""
    },
    {
        "source": "Clinical_Protocols_Misc",
        "category": "clinical_reference",
        "text": """Diyare Değerlendirmesi ve Gizli Kan:
ACİL ŞÜPHE EDİLEN DURUMLAR (ORANGE/RED):
  Kanlı diyare + ateş + karın ağrısı → Enfeksiyöz kolit (E.coli O157:H7, Shigella)
  Kanlı diyare + trombositopeni + böbrek yetmezliği → HUS (Hemolitik Üremik Sendrom) → RED
  İshal + hipotansiyon + ateş → Toksik megakolon → RED
YATIRMAK GEREKMEYEBILIR ANCAK İZLEM GEREKİR (YELLOW):
  Seyahat sonrası ishal, şiddetli dehidrasyon belirtisi, yaşlı/immunsüpresif hasta
ACİL SORMAK GEREKENLER: Kanda leke var mı? Seyahat geçmişi? Hastanede yatış geçmişi (C.diff)? Bağışıklık durumu? Dehidrasyon bulguları?"""
    },
    {
        "source": "Clinical_Protocols_Misc",
        "category": "clinical_reference",
        "text": """Akut Gözlem — Göz Acilleri (Görme Kaybı):
ACİL (RED): Ani görme kaybı, ağrısız — santral retinal arter tıkanması (CRAO) → ≤90 dk geri dönüşümlü, göz masajı, parasentez
ACİL (RED): Ani görme kaybı, ağrılı → Akut kapalı açı glokomu (bulanık görme + bulantı + renkli çemberler) → IV asetazolamid + oftalmoloji
ACİL (RED): Retinal dekolman — yarım görme alanı kaybı, "perde", ışık çakmaları
ORANGE: Kemozis + ağrı + sekresyon → Orbital sellülit (ateş eşlik ediyorsa)
YELLOW: Konjonktivit → bakteriyel, viral, alerjik
Sorulacak: Ne zaman başladı? Ani mı? Tek gözde mi bilateral mi? Travma var mı? Daha önce göz cerrahisi?"""
    },
    # ════════════════════════════════════════
    #  Sprint 16 EK: ICD-10 TR KODLAMA REHBERİ
    # ════════════════════════════════════════
    {
        "source": "ICD10_TR_v2024",
        "category": "icd10_coding",
        "text": """ICD-10 Kardiyoloji Kodları — Türkiye Klinik Pratiği:
I21.0 — Anterior miyokard enfarktüsü (ST yükselmeli)
I21.1 — Alt duvar MI (inferior STEMI)
I21.2 — ST-yükselmesiz MI (NSTEMI)
I20.0 — Unstabil angina
I25.1 — Aterosklerotik kalp hastalığı
I50.0 — Konjestif kalp yetmezliği
I48.0 — Atriyal fibrilasyon (paroksismal)
I10   — Esansiyel hipertansiyon
I64   — İnme (SVA) — tür belirtilmemiş
I63.5 — Serebral enfarkt (aterosklerotik)
R07.4 — Göğüs ağrısı, tanımlanmamış
R07.9 — Göğüs ağrısı kardiyak olmayan"""
    },
    {
        "source": "ICD10_TR_v2024",
        "category": "icd10_coding",
        "text": """ICD-10 Solunum Sistemi Kodları — TR:
J18.9 — Pnömoni, tanımlanmamış
J06.9 — Akut üst solunum yolu enfeksiyonu
J44.1 — KOAH, akut alevlenme
J45.9 — Astım, kontrol altında değil
J13   — Streptococcus pneumoniae pnömonisi
J80   — Akut respiratuar distres sendromu (ARDS)
J96.0 — Akut solunum yetmezliği
R06.0 — Dispne (nefes darlığı)
R06.2 — Wheezing (hırıltı)
U07.1 — COVID-19 (laboratuvar doğrulamalı)
U07.2 — COVID-19 (klinik / epidemiyolojik)
J96.9 — Solunum yetmezliği, tanımlanmamış"""
    },
    {
        "source": "ICD10_TR_v2024",
        "category": "icd10_coding",
        "text": """ICD-10 Gastrointestinal ve Genel Kodlar — TR:
K92.1 — Melena (kanlı dışkı)
K25.0 — Mide ülseri, akut kanamali
K57.3 — Divertiküloz (komplikasyonsuz)
K81.0 — Akut kolesistit
K80.2 — Safra taşı kolik ağrısı
K35.2 — Akut apandisit, peritonit ile
K25.4 — Kronik mide ülseri (kanama olmaksızın)
R10.1 — Üst karın ağrısı
R10.3 — Alt karın ağrısı
R55   — Senkop ve kollaps
R57.0 — Kardiyojenik şok
R57.9 — Şok, tanımlanmamış
E11.9 — Tip 2 diyabet mellitüs, komplikasyonsuz
E10.65 — Tip 1 diyabet, hipoglisemi ile"""
    },
    {
        "source": "ICD10_TR_v2024",
        "category": "icd10_coding",
        "text": """ICD-10 Nöroloji ve Travma Kodları — TR:
G35   — Multiple skleroz (MS)
G43.9 — Migren, tanımlanmamış
G44.3 — Kronik posttravmatik baş ağrısı
G40.9 — Epilepsi, tanımlanmamış
R51   — Baş ağrısı
S00-S09 — Baş yaralanmaları
S10-S19 — Boyun yaralanmaları
S36.0 — Dalak yaralanması
T14.9 — Yaralanma, tanımlanmamış
T78.2 — Anafilaktik şok, tanımlanmamış madde
T71   — Asfiksi (boğulma)
Z03.89 — Diğer şüpheli hastalıklar gözlem
Z00.00 — Sağlık muayenesi, komplikasyonsuz"""
    },
    # ════════════════════════════════════════
    #  Sprint 16 EK: TÜRKİYE ACİL SERVİS İSTATİSTİKLERİ 2024
    # ════════════════════════════════════════
    {
        "source": "Turkey_Health_Stats_2024",
        "category": "epidemiology",
        "text": """Türkiye Acil Servis İstatistikleri 2024 (Sağlık Bakanlığı):
Yıllık başvuru: ~117 milyon (dünya ortalamasının 2.3 katı)
Başvuruların %68'i ambulatuvar yönetilebilir vakalar
En sık başvuru nedenleri: Üst solunum yolu enfeksiyonu (%18), Kas-iskelet ağrısı (%14), Karın ağrısı (%12)
Kardiyovasküler aciller: Toplam başvuruların %8'i — hastane içi mortalite %2.1
Kırmızı alan triaj oranı: %3.4 (ulusal hedef <5%)
Ortalama acil servis bekleme süresi: 42 dakika (2024 hedef: <30 dk)
Gereksiz başvuru oranı: %42 (YEEP programı ile azaltma hedefi)
Pediatrik acil başvuru oranı: %28 (mevsimsel enfeksiyonlar dominant)
65 yaş üstü başvuru oranı: %22 (kronik hastalık komplikasyonları ağırlıklı)
Gözlem süresi ortalaması: 4.2 saat"""
    },
    {
        "source": "Turkey_Health_Stats_2024",
        "category": "epidemiology",
        "text": """Türkiye Kardiyovasküler Hastalık Yükü 2024:
Kardiyovasküler hastalıklar Türkiye'de ölümlerin %38.5'ine neden olmaktadır.
Yıllık MI insidansı: ~70.000 yeni vaka, erkeklerde kadınlara göre 2.5 kat fazla
STEMI'de kapı-balon süresi hedefi: <90 dakika (2024 başarı oranı %71)
İnme insidansı: ~85.000/yıl — atriyal fibrilasyon %20-25 etyoloji
Kalp yetmezliği prevalansı: nüfusun %2.8'i (~2.4 milyon hasta)
Acil PTCA merkezi sayısı: 103 (2024 itibariyle)
Risk faktörleri: Hipertansiyon %35, Obezite %32, Sigara %27, Diyabet %15.4
Önlenebilir kardiyak ölüm oranı: %60 (erken müdahale ile)
Önemli: Türk hastaları, Batılı toplumlara kıyasla daha genç yaşta MI geçirmektedir (<55 yaş MI erkeklerde %31)"""
    },
    {
        "source": "Turkey_Health_Stats_2024",
        "category": "epidemiology",
        "text": """Türkiye Diyabet ve Metabolik Hastalık Epidemiyolojisi 2024:
Diyabet prevalansı: %15.4 (dünya ortalaması %10.5) — 12.4 milyon diyabetli
Prediyabet: ek %21.1 (yüksek riskli grup)
Tip 2 diyabet: %92, Tip 1: %5, Diğer: %3
Diyabetik koma: yılda ~4.500 acil başvuru
DKA (diyabetik ketoasidoz): Tip 1'de en sık ilk başvuru nedeni (%30)
HbA1c kontrolsüzlük oranı (>%7): %68
Diyabetik ayak ülseri: yılda ~35.000 yeni vaka, amputasyon riski %15
Hipoglisemi acil başvurusu: yılda ~28.000 (insülin kullanıcılarında %8 oranında)
Obezite ile ilişkili acil başvurular artış trendi: son 5 yılda %23 artış"""
    },
    # ════════════════════════════════════════
    #  Sprint 16 EK: GENİŞLETİLMİŞ MTS ALGORİTMALAR
    # ════════════════════════════════════════
    {
        "source": "MTS_Protocols_Extended_v3",
        "category": "triage_protocol",
        "text": """MTS Genişletilmiş Kardiyak Triaj Algoritması:
ADIM 1 — Hayati Risk Tespiti:
  □ Bilinç kaybı/değişikliği (GCS <15) → RED
  □ Solunum yetmezliği (SpO2 <90%) → RED
  □ Dolaşım yetersizliği (SKB <90) → RED
ADIM 2 — Kardiyak Semptom Değerlendirmesi:
  □ Göğüs ağrısı + sol kol/çene yayılımı → Yüksek MI şüphesi → RED
  □ Göğüs ağrısı + diaphoresis (terleme) → Yüksek kardiyak risk → RED
  □ Göğüs ağrısı EKG anormalliği ile → RED (STEMI protokolü)
  □ Göğüs ağrısı izole, stabil → YELLOW (kardiyak marker takibi)
ADIM 3 — Risk Faktörü Skorlaması:
  Diyabet, HT, hiperkolesterolemi, sigara, aile öyküsü, erkek >45/kadın >55 yaş
  ≥2 risk faktörü + semptom → Kardiyoloji konsültasyonu
ADIM 4 — EKG Endikasyonu:
  Her göğüs ağrısı başvurusunda 10 dakika içinde EKG çekilmesi zorunlu"""
    },
    {
        "source": "MTS_Protocols_Extended_v3",
        "category": "triage_protocol",
        "text": """MTS Pediatrik Triaj Özel Durumları:
KIRMIZI BAYRAKLAR — Acil Pediyatrik Durumlar:
  □ Bebek (<3 ay) + ateş ≥38°C → RED (menenjit/sepsis riski)
  □ Bronşiyolit + SpO2 <92% → RED
  □ Anafilaksi bulguları (ürtiker + bronkospazm + hipotansiyon) → RED
  □ Konvülsiyon devam ediyor → RED
  □ Dehidrasyon bulguları — gözyaşı yok, ağız kuruluğu, fontanel çökmüş → RED
  □ Menenjit üçlüsü: ateş + baş ağrısı + ense sertliği → RED
SARI BAYRAKLAR:
  □ Ateş ≥39°C + 3-36 ay arası → YELLOW (okült bakteriyemi)
  □ Kulak enfeksiyonu + yüksek ağrı → YELLOW
  □ İdrar yolu enfeksiyonu belirtileri (<2 yaş) → YELLOW
YAŞ SPESIFIK VITAL DEĞERLER:
  Yenidoğan: KAH 120-160/dk, SS 40-60/dk, SKB 60-90 mmHg
  1-3 yaş: KAH 90-150/dk, SS 24-40/dk, SKB 80-110 mmHg
  Okul çağı: KAH 70-120/dk, SS 18-30/dk, SKB 90-120 mmHg"""
    },
    # ════════════════════════════════════════
    #  Sprint 17 EK: ORTOPEDİ / TRAVMA
    # ════════════════════════════════════════
    {
        "source": "Orthopedic_Triage",
        "category": "clinical_guideline",
        "text": """Ortopedik Acil Triaj — Kırık ve Dislokasyon:
AÇIK KIRIK (kemik deriden dışarı veya yara var): RED — enfeksiyon ve damar/sinir hasarı riski
KALÇa KIRIGI (yaşlı düşme, kalça/uyluk ağrısı, bacak kısalması/dışa rotasyon): ORANGE — cerrahi
OMLUz DİSLOKASYONU: Ani ağrı + kol hareketsiz + omuz şekil bozukluğu → ORANGE
BİLEK/AYAK BİLEĞİ (Ottawa Kuralları):
  Ayak bileği → malleous üzeri 6 cm'de hassasiyet + ağırlık taşıyamıyor → X-ray gerekli → YELLOW/ORANGE
  Diz → Ottawa Diz Kuralı: yaş>55, fibula başı hassas, diz fleksiyonu <90° → X-ray
OMURGA TRAVMASI: Boyun veya sırt ağrısı + travma + uyuşukluk/güçsüzlük → RED (spinal kord koruma)
KOMPARTİMAN SENDROMU (5P): Pain, Pressure, Pallor, Paralysis, Pulselessness → RED (acil fasyotomi)
Sorulacak: Nasıl düştü? Direkt mi çarptı? Şişlik ne kadar sürede gelişti? Uyuşukluk/karıncalanma var mı?"""
    },
    {
        "source": "Orthopedic_Triage",
        "category": "clinical_guideline",
        "text": """Bel Ağrısı Triaj Değerlendirmesi:
KIRMIZI BAYRAKLAR (RED/ORANGE — görüntüleme zorunlu):
  - Bel ağrısı + mesane/bağırsak kontrolü kaybı → Cauda equina sendromu → RED ACİL
  - Bel ağrısı + ateş + IV ilaç kullanımı → Spondilodiskit/epidural apse → RED
  - 50 yaş üzeri + travmasız başlayan şiddetli bel ağrısı → Malinite şüphesi → ORANGE
  - Bel ağrısı + bacak güçsüzlüğü progressif → RED
  - Geceleri kötüleşen, istirahatla geçmeyen bel ağrısı → İnflamatuvar/neoplastik → ORANGE
MEKANİK BEL AĞRISI (GREEN/YELLOW):
  - Eforla artan, istirahatla azalan, 20-55 yaş, travma geçmişi
  - NRS <6, nörolojik belirti yok → YELLOW (analjezi + hareket önerisi)
Sorulacak: Bacağa yayılıyor mu (siyatik)? Ayağa kalkınca artar mı? İdrar/dışkılama sorunu var mı?"""
    },
    # ════════════════════════════════════════
    #  Sprint 17 EK: KBB (KULAK-BURUN-BOĞAZ) ACİLLERİ
    # ════════════════════════════════════════
    {
        "source": "ENT_Emergency",
        "category": "clinical_guideline",
        "text": """Kulak Acilleri — Triaj:
ANİ İŞİTME KAYBI: Tek taraflı ani işitme kaybı → ORANGE (ilk 72 saat steroid penceresi)
DIŞ KULAK YOLU YABANCI CİSMİ (çocuk): YELLOW — konservatif çıkarma, perforasyon riski
AKUT OTİT MEDIA: Ateş + kulak ağrısı + timpanik membran bombeli → YELLOW (antibiyotik)
OTİT EKSTERNASi ("yüzücü kulağı"): Tragus bası hassasiyeti + akıntı → YELLOW/GREEN
MASTOIDIT: Kulak arkasında şişlik + ateş + kulak ağrısı → ORANGE (IV antibiyotik gerekebilir)
BENIGN PAROKSİZMAL POZİSYONEL VERTİGO (BPPV): Baş pozisyonu ile tetiklenen kısa süreli (<1 dk) vertigo → GREEN (Epley manevrası)
MENİER HASTALIĞI: Tekrarlayan vertigo + işitme kaybı + kulak çınlaması → YELLOW (akut ataklarda)"""
    },
    {
        "source": "ENT_Emergency",
        "category": "clinical_guideline",
        "text": """Boğaz ve Boyun Acilleri — Triaj:
EPİGLOTİT (yetişkin): Ani başlayan yutma güçlüğü + drooling + boğuk ses + tripod pozisyon → RED (havayolu tehlikesi)
PERİTONSİLER APSE: Tek taraflı şişlik + uvula deviasyonu + ağız açamıyor (trismus) → ORANGE/RED (drenaj gerekli)
RETROFARENGEAL APSE: Boyun ağrısı + yutma güçlüğü + ateş + boyun sertliği → RED
AKUT TONSİLLİT: Ateş + boğaz ağrısı + şişmiş tonsil + eksüda → YELLOW/GREEN (antibiyotik)
EPİSTAKSİS (Burun Kanaması):
  Anterior (ön): Massmak alanı, bastırma ile durur → GREEN
  Posterior (arka): Durdurulamıyor, yaşlı/hipertansiyon hastası → ORANGE (tampon)
  Epistaksis + antikoagülan kullanımı + durmayan kanama → ORANGE/RED
YABANCI CİSİM YUTMA: Keskin cisim (kemik, iğne, olta) veya pil → ORANGE (acil endoskopi)
Düz cisim, semptom yok → YELLOW (radyoloji)"""
    },
    # ════════════════════════════════════════
    #  Sprint 17 EK: DERMATOLOJİ ACİLLERİ
    # ════════════════════════════════════════
    {
        "source": "Dermatology_Triage",
        "category": "clinical_guideline",
        "text": """Döküntü Triaj Değerlendirmesi — Kırmızı Bayraklar:
HAYATI TEHLİKE (RED):
  PETEŞİ/PURPURAf + yüksek ateş + hastayı iyi hissettirmeyen → Meningokoksemi → RED ACİL (IV penisilin)
  STEVENs-JOHNSON SENDROMU / TEN: Yaygın büller + mukoza tutulumu + ilaç öyküsü → RED
  NEKROTİZAN FASİİT: Hızla yayılan, orantısız ağrılı kızarık şişlik + krepitasyon → RED
  ANAFİLAKSİ ile ürtiker: Deri + solunum/dolaşım → RED
ACİL (ORANGE):
  Yüz/boyun anjioödemi (larinks ödemi riski) → ORANGE/RED
  Canlı ikinci derece yanık >%15 YAKT → ORANGE
  İnfekte yaralar: Kızarıklık genişliyor + ateş + lenf bezi şişliği → ORANGE (Selülit/erizipel)
STANDARD (YELLOW/GREEN):
  Kontakt dermatit, urtiker (anafilaksi yok), egzama alevlenmesi
Sorulacak: Döküntü ne kadar sürede yayıldı? İlaç kullanımı yeni mi? Ateş var mı? Kaşıntı mı ağrı mı?"""
    },
    {
        "source": "Dermatology_Triage",
        "category": "clinical_guideline",
        "text": """Yara ve Cilt Enfeksiyonu Triajı:
SELÜLIT: Kızarıklık + ısı + ödem + ağrı — sınır marker ile takip → YELLOW
  Yüz selüliti, göz çevresi → ORANGE (orbital selülit riski)
  Şeker hastası ayak yaraları → ORANGE (süpürüntü, koku, iyileşmeme)
APSE: Flüktüan şişlik → Drenaj → YELLOW
ERİZİPEL: Ateş + parlak kırmızı, sınırlı döküntü, özellikle yüz/bacak → YELLOW
ZONA (HERPES ZOSTER): Ağrılı tek taraflı döküntü + kabarcık + güzergah bant şeklinde → YELLOW
  Göz çevresi zona (oftalmik zona) → ORANGE (göz konsültasyonu)
DERI ALTINDA YABANCI CİSİM (kıymık, cam): YELLOW — dikkatli çıkarma, tetanoz sorgula
TETANOZ RISKI: Kirli yara + aşı durumu belirsiz/> 5 yıl → İmmünoprofilaksi gerekli → YELLOW
Sorulacak: Yara kaç saat/gün önce oldu? Kirli mi (toprak, hayvan)? Tetanoz aşısı ne zaman?"""
    },
    # ════════════════════════════════════════
    #  Sprint 17 EK: ÜROLOJİ ACİLLERİ
    # ════════════════════════════════════════
    {
        "source": "Urology_Emergency",
        "category": "emergency_protocol",
        "text": """Üroloji Acilleri — Triaj:
TESTİS TORSİYONU: Ani başlayan şiddetli skrotal ağrı + bulantı → RED ACİL (<6 saat kurtarma penceresi)
  Kremasterik refleks kaybolmuş, testis yüksekte → HEMEN ÜROLOJİ
PRİAPİZM: >4 saat süren ağrılı ereksiyon → ORANGE (iskemik priapizm — acil drenaj)
ÜRINER RERANSİYON (idrar yapamıyor): Suprapubik dolgunluk + ağrı + son idrara çıkma uzun zaman → ORANGE (kateter)
  Prostat büyümesi, ilaç (antikolinerjik, sempatomimetik) → yaşlı erkek risk grubu
HEMATÜRI (idrarda kan): Ağrısız makroskobik hematüri → malinite (böbrek, mesane, prostat) → YELLOW (üroloji)
  Hematüri + pıhtı → Tıkanma riski → ORANGE
PİYELONEFRİT: Ateş + kostovertebral açı hassasiyeti + dizüri → YELLOW (IV antibiyotik) 
  Sepsis bulgusu varsa → RED
Sorulacak: Son ne zaman idrar yaptı? İdrar rengi? Çocukta: ıslatma alışkanlığı değişti mi?"""
    },
    # ════════════════════════════════════════
    #  Sprint 17 EK: TÜRKİYE'YE ÖZGÜ KLİNİK BAĞLAM
    # ════════════════════════════════════════
    {
        "source": "Turkey_Clinical_Context",
        "category": "clinical_reference",
        "text": """Türkiye'ye Özgü Sık Karşılaşılan Klinik Durumlar:
MEVSİMSEL HASTALIKLAR:
  Kış (Aralık-Mart): ÜSYE, grip, meningit (mevsimsel artış), RSV (bebek)
  Yaz (Haziran-Eylül): Isı çarpması (özellikle yaşlılar, tarım işçileri), gıda zehirlenmesi, trafik kazaları
  Kurban Bayramı: Kesici-delici alet yaralanmaları, gıda zehirlenmesi artışı
YÜKSEK SEVİYE GRUPLARI:
  Tarım işçileri: Organofosfat zehirlenmesi (SLUDGE: salivasyon, lakrimasyon, üriner, diyare, GIS, emisis)
  İnşaat işçileri: İsh, künt travma, göz ve cilt yaralanmaları
  Yaşlı kırsal nüfus: Kaza dışı ilaç aşımı (depresyon), hipotermi, yetersiz beslenme
COVİD-19 SONRASI BAĞLAM (2024-2026): Long-COVID bulguları (kronik yorgunluk, nefes darlığı, beyin sisi)
  Post-COVID PE riski artar — DVT değerlendirmesinde dikkate al"""
    },
    {
        "source": "Turkey_Clinical_Context",
        "category": "clinical_reference",
        "text": """Türkiye'de İlaç Güvenliği ve Yaygın İlaç Kullanımı:
EN SIK KULLANILAN İLAÇLAR (Türkiye, 2024):
  1. Analjezikler (parasetamol, ibuprofen, metamizol/Novalgin) — aşırı kullanım yaygın
  2. Antihipertansifler (amlodipin, enalapril, losartan) — uyumsuzluk sorunu
  3. Statinler (atorvastatin, rosuvastatin)
  4. Proton pompa inhibitörleri (omeprazol, pantoprazol) — gereksiz uyum
  5. Antibiyotikler (amoksisilin-klavulanat, azitromisin) — direnç sorunu
METAMİZOL (Novalgin) KULLANIMI: Türkiye'de yaygın, Avrupa'da yasak — agranülositoz riski
ASPİRİN FAZLASI: Erken dönem (tinnitus, hipertermi) → YELLOWsorulacak antikoagülan kullanımı
YÜKSEK RİSKLİ KOMBINASYONLAR (sık görülen):
  Warfarin + Novalgin → Kanama riski kritik artış
  Metformin + alkol → Laktik asidoz
  Antihipertansif + NSAİİ → Böbrek yetmezliği riski
Sorulacak: Hangi ilaçları kullanıyorsunuz? Doktor reçetesi mi, kendi aldınız mı? Son doz ne zaman?"""
    },
    {
        "source": "Turkey_Clinical_Context",
        "category": "clinical_reference",
        "text": """Türkiye Sağlık Sistemi Yönlendirme Rehberi:
ASM (AİLE SAĞLIĞI MERKEZİ) — GREEN vakalar için:
  Üst solunum yolu enfeksiyonu, hafif ateş, reçete yenileme, kronik hastalık takibi, aşı
  Hafta içi 08:00-17:00, randevu ile (MHRS: mhrs.gov.tr veya ALO 182)
ACİL SERVİS — YELLOW/RED için:
  7/24 hizmet, tüm devlet ve özel hastaneler
  Yeşil alan (hafif vaka yön): Acil servis verimini artırmak için → ASM'ye yönlendir
112 ACİL:
  Kardiyak arrest, inme, ağır travma, bilinç kaybı → Doğrudan 112
  Çağrı sonrası: Kapıyı aç, asansörü bekle, ilaç listesini hazırla
Randevu Sistemi (MHRS): Branş bazlı poliklinik randevusu — rutin vakalar için
SGSK Kapsam: Devlet hastanesi ve anlaşmalı özel → muayene ücreti farkı olabilir"""
    },
    # ════════════════════════════════════════
    #  Sprint 17 EK: ISI ÇARPMASI / HİPOTERMİ / ÇEVRE ACİLLERİ
    # ════════════════════════════════════════
    {
        "source": "Environmental_Emergency",
        "category": "emergency_protocol",
        "text": """Isı Çarpması ve Hipertermik Aciller:
ISIL KRIZ (Heat Stroke) — RED: Vücut ısısı >40°C + bilinç değişikliği (klasik), terleme olmayabilir (klasik tip)
  Exertional (fiziksel): Ağır egzersiz, sporcular, askerler + bilinç değişikliği → RED
  Semptomlar: Konfüzyon, ataksi, konvülsiyon, sıcak kuru cilt
  YÖNETİM: Hızlı soğutma (ıslak örtü + fan, buz banyosu değil), IV sıvı dikkatli
ISIL TÜKENME (Heat Exhaustion) — YELLOW: Terleme + halsizlik + baş dönmesi + bulantı, bilinç açık
  Oral sıvı veya IV izotonik, serin ortam
GÜNEŞ ÇARPMASI (Sunstroke): Baş ağrısı + hafif bilinç bulanıklığı + ateş → YELLOW
KREMP (Isı Krampi): Yorgunluk sonrası kas krampi, aşırı terleme → GREEN (elektrolit)
Türkiye'de risk: Yaz ayları, özellikle SE Anadolu, yaşlılar ve açık havada çalışanlar yüksek risk"""
    },
    {
        "source": "Environmental_Emergency",
        "category": "emergency_protocol",
        "text": """Hipotermi ve Soğuk Maruziyeti:
HİPOTERMİ DERECELERİ:
  Hafif (32-35°C): Titreme, letarji, ataksi → YELLOW (ısıtma)
  Orta (28-32°C): Titreme yok, stupor, AF, bradikardi → ORANGE
  Ağır (<28°C): Koma, VF riski, pulsuz görünebilir → RED (aktif ısıtma, CPR gerekirse)
KLİNİK NOT: "Ölü değildir, ısınana kadar ölü değildir" — soğuk kardiyak arreste CPR devam et
DONMA (Frostbite): Parmak/burun/kulak → beyaz sertleşme → YELLOW (ılık su banyosu 40°C)
  Büllü donma → ORANGE
Türkiye'de risk: Doğu ve İç Anadolu kışı, evsiz nüfus, alkol altında maruz kalma
Sorulacak: Ne kadar süre soğukta kaldı? Alkol var mı? Isınmaya çalıştı mı?"""
    },
    # ════════════════════════════════════════
    #  Sprint 17 EK: GÖZ ACİLLERİ (GENİŞLETİLMİŞ)
    # ════════════════════════════════════════
    {
        "source": "Ophthalmology_Emergency",
        "category": "emergency_protocol",
        "text": """Göz Kimyasal Yaralanması ve Travma:
KİMYASAL YANIK (Red — En Acil Göz Acili):
  Asit veya baz (özellikle NaOH, Ca(OH)2 — çimento, tuvalet açıcı) → HEMEN su ile yıkama 15-20 dakika
  Yıkama önce, göz muayenesi sonra — bekleme yok
  Baz yanıkları daha derin girer → daha kötü prognoz
LAZEr/UV YARALANMASI (Fotokeratit): Kaynak kaynakçılığı veya UV maruziyeti → 6-12 saat sonra ağrı, gözyaşı
  → YELLOW (topikal anestezik + göz yaması)
PENETRAN GÖZE TRAVMA: Sivri cisim sokulması, şüphe → RED (göze baskı yapma, shield)
ORBITAL KIRIK: Çift görme + enoftalmus + şişlik altı doku → ORANGE (orbital BT)
GÖZ İÇİ BASINCI YÜKSELMESI SEMPTOMLARI: Göz ağrısı + bulanık görme + haleler → Akut glokom → RED
Sorulacak: Ne zaman oldu? Ne değdi — asit mi, baz mı? Görme kaybı var mı? Diplopi?"""
    },
    # ════════════════════════════════════════
    #  Sprint 17 EK: ÇOCUK ACİLLERİ (GENİŞLETİLMİŞ)
    # ════════════════════════════════════════
    {
        "source": "Pediatric_Emergency_Extended",
        "category": "clinical_guideline",
        "text": """Çocukta Karın Ağrısı Özel Değerlendirme:
APANDİSiT (Çocuk): 5-15 yaş pik, bebekte atipik (peritonit riski yüksek)
  Bulgu: Göbek çevresi ağrı → sağ alt kadrana kayma + ateş + iştahsızlık + rebound → ORANGE
  Alvarado skoru ≥7 → Yüksek ihtimal → BT/US + cerrahi
İNTUSÜSEPSİYON: 6-36 ay, kolje kramlp tarzı ağrı + çilek jölesi dışkı + karın kitlesi → RED
VOLVÜlÜS: Yenidoğan veya küçük çocuk + safralı kusma + distansiyon → RED (cerrahi acil)
MEZADENİT: ÜSYE sonrası karın ağrısı + mezenter lenf nodu büyümesi → GREEN/YELLOW (antiinfl)
FUNKSİYONEL KARIN AĞRISI: Okul çağı, stresten etkilenme, palpasyonla azalma, kırmızı bayrak yok → GREEN
Sorulacak: Kaç yaşında? Son dışkı ne renk ve neye benziyordu? Ateş var mı? Karın sert mi?"""
    },
    {
        "source": "Pediatric_Emergency_Extended",
        "category": "clinical_guideline",
        "text": """Çocukta Yüksek Ateş Yönetimi:
YENİDOĞAN (<28 gün) ATEŞ ≥38°C: HER ZAMAN RED — sepsis workup (LP dahil), IV antibiyotik
BEBEK (1-3 ay) ATEŞ ≥38°C: RED/ORANGE — okült bakteremi riski yüksek
BEBEK (3-24 ay) ATEŞ ≥39°C: Klinik görünüme göre ORANGE/YELLOW
  Aşısız → Hib/pnömokok sepsis riski → ORANGE
  Görünümü iyi, aşılı → YELLOW (ateş düşürücü, takip)
FEBRİL KONVÜLSIYON: 6 ay-5 yaş, basit (<15 dk, jeneralize, tek) → YELLOW (febril konvülsiyon eğitimi)
  Kompleks (>15 dk, fokal, tekrarlayan) → ORANGE (EEG değerlendirme)
ATEŞ MİMEZEN DURUMLAR: Diş çıkarma hafif ateş (37.5°C altı) → GREEN
ANTIPIRETIK: Parasetamol 15 mg/kg her 4-6 saat veya ibuprofen 10 mg/kg her 6-8 saat (>3 ay)
Sorulacak: Ateş tam kaç derece? Ne zamandır devam ediyor? Titreme, ense sertliği, öne eğilemiyor mu?"""
    },
    # ════════════════════════════════════════
    #  Sprint 17 EK: KLİNİK SORGULAMA KALİTE KONTROL
    # ════════════════════════════════════════
    {
        "source": "Clinical_QA_Quality",
        "category": "clinical_reference",
        "text": """Tıbbi Mülakatta Kritik Kaçırılmaması Gereken Sorular:
GENEL ACİL DEĞERLENDİRME HER VAKADA:
  □ Şikayet ne zamandır var, nasıl başladı?
  □ Daha önce aynı şikayet oldu mu?
  □ Şu an hangi ilaçları kullanıyor?
  □ Bilinen alerjisi var mı?
  □ Kronik hastalık var mı (DM, HT, kalp hastalığı, KOAH)?
AĞRI VAKASINDA:
  □ 1-10 skalasında kaçıncı derecede? (0=yok, 10=dayanılmaz)
  □ Sürekli mi, kesik kesik mi?
  □ Başka yere yayılıyor mu?
  □ Neler kötüleştirir/iyileştirir?
ACİL ŞÜPHE VARSA:
  □ Son yemek ne zaman? (anestezi güvenliği)
  □ Hamile olabilir mi? (kadın, üreme çağı)
  □ Son 24 saatte bilinç değişikliği oldu mu?
ÇOCUK VAKASINDA:
  □ Kaç kg? (ilaç dozu hesabı)
  □ Aşı takvimi tam mı?
  □ Annede gebelik komplikasyonu var mıydı?"""
    },
    {
        "source": "Clinical_QA_Quality",
        "category": "clinical_reference",
        "text": """Triaj Hata Kaynakları ve Önleme — Klinik Güvenlik:
ALT-TRİAJ (Undertriage) — En Tehlikeli Hata:
  Yaşlılarda atipik prezentasyon: AMI'de göğüs ağrısı yok, sadece yorgunluk/konfüzyon
  Diyabetiklerde ağrı eşiği yüksek → ağır durumu sessiz taşıyabilir
  İmmünosüpresif: Ateş olmadan ağır sepsis olabilir
  Psikiyatrik hastada fiziksel acili gözden kaçırma riski
ÜST-TRİAJ (Overtriage) — Kaynak israfı ama kabul edilebilir:
  Belirsiz semptomda yüksek triaj → "güvenli yanılma"
ZAMAN TUZAĞI: Triaj yapıldıktan sonra kötüleşen hasta → dinamik olarak yeniden triaj
DOKÜMANTASYON: Her triaj kararı, saati ve gerekçesi kayıt altına alınmalı
SÖZEL ONAY: "Bunu doğru anladım mı? Başka önemli bir şey var mı?" her mülakatın sonu"""
    },
    # ════════════════════════════════════════
    #  Sprint 17 EK: MENTAL SAĞLIK GENİŞLETME
    # ════════════════════════════════════════
    {
        "source": "Mental_Health_Extended",
        "category": "emergency_protocol",
        "text": """Anksiyete Atağı vs. Kardiyak Acil Ayrımı:
PANİK ATAGI KLİNİK (GREEN/YELLOW):
  Çarpıntı + nefes darlığı + ölüm korkusu + uyuşma + terleme → Genç, daha önce aynı atak geçirdi
  Dakikalar içinde zirve + kendiliğinden geçer, EKG normal
  Tetikleyici: Stres, kapalı alan, animad (kalabalık)
KARDİYAK ACİL İLE AYRIMI (RED'e geç):
  >40 yaş + kardiyak risk faktörü varsa → HIÇ PTC ataması yapma, önce EKG
  Ağrı 10/10 + solukluk + diyaforez → Kardiyak dışla
  Nefes almakla artar mı? (plöritik → PE şüphesi)
HIPERVENTILASYON: Perioral + el-ayak uyuşması + karpopedal spazm → Kağıt torba → GREEN
Sorulacak: Bu ataklar daha önce aynı çıktı mı? Stres durumunda mı oldu? Kardiyoloji değerlendirmesi var mı?"""
    },

    {
        "source": "MTS_Protocols_Extended_v3",
        "category": "triage_protocol",
        "text": """MTS Ağrı Yönetimi ve Triaj Entegrasyonu:
NRS (Numerik Ağrı Skalası) ile Triaj:
  □ NRS 0-3 → Hafif → GREEN (analjezi + takip)
  □ NRS 4-6 → Orta → YELLOW (30 dk içinde değerlendirme)
  □ NRS 7-8 → Şiddetli → ORANGE (15 dk içinde)
  □ NRS 9-10 → Dayanılmaz → RED (anında)
Özel Durumlar:
  □ Çocuklar → Wong-Baker yüz skalası kullanılır
  □ Demansiyel hastalar → PAINAD skalası
  □ Somatik bağlamda ağrı (anksiyete eşlik ediyor) → YELLOW
ACILILIK MODIFIYE EDEN FAKTÖRLER (ağrı üzerine):
  □ Ani başlangıç (thunderclap) → Subaraknoid kanama şüphe → RED
  □ Geçici (TIK sonrası) ağrı azalması → Geçici iskemik atak → RED
  □ Ağrı + nabız bozukluğu → Aort diseksiyonu → RED
  □ Kronik ağrı kötüleşmesi (baseline>2 hf) → YELLOW"""
    },
]


def ingest_builtin_knowledge() -> int:
    """Yerleşik tıbbi bilgi tabanını ChromaDB'ye yükler."""
    total = 0
    for item in BUILTIN_MEDICAL_KNOWLEDGE:
        added = ingest_text(
            text=item["text"],
            source=item["source"],
            category=item["category"],
        )
        total += added
    logger.info(f"Yerleşik bilgi tabanı yüklendi: {total} yeni chunk")
    return total


def ingest_project_pdfs(pdf_dir: Optional[str] = None) -> int:
    """Projedeki PDF dosyalarını ChromaDB'ye yükler."""
    if pdf_dir is None:
        # Proje kök dizinini bul
        pdf_dir = os.path.join(os.path.dirname(__file__), "..", "..")

    total = 0
    pdf_dir = Path(pdf_dir)
    for pdf_file in pdf_dir.glob("**/*.pdf"):
        if "stitch" in str(pdf_file).lower():
            continue  # UI tasarım PDF'lerini atla
        try:
            count = ingest_pdf(
                str(pdf_file),
                source_name=pdf_file.stem[:40],
                category="project_document",
            )
            total += count
        except Exception as e:
            logger.warning(f"PDF atlandı ({pdf_file.name}): {e}")

    logger.info(f"Proje PDF'leri yüklendi: {total} chunk")
    return total

