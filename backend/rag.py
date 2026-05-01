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
TOP_K = 4             # Varsayılan retrieval sayısı


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
    """
    collection = _get_collection()
    embed = _get_embed_model()

    query_emb = embed.encode([query], show_progress_bar=False).tolist()

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
                           min_relevance: float = 0.30) -> str:
    """
    Sorguyla ilgili tıbbi bağlamı prompt'a hazır formatta döndürür.
    Düşük relevance'lı sonuçları filtreler.
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

        lines = ["=== Tıbbi Referans Bilgisi ==="]
        for h in relevant:
            lines.append(f"[{h['source']}] {h['document']}")

        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"RAG retrieval hatası (önemsiz): {e}")
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
# ─────────────────────────────────────────────
BUILTIN_MEDICAL_KNOWLEDGE = [
    # MTS Triaj Kriterleri
    {
        "source": "MTS_Triage_Guide",
        "category": "triage_protocol",
        "text": """Manchester Triage System (MTS) 5 seviyesi:
RED (Hemen): AMI, inme, anafilaksi, solunum yetmezliği, GCS<8, major travma, aort diseksiyonu.
ORANGE (Çok Acil, 10dk): Göğüs ağrısı, akut konfüzyon, konvülsiyon, ciddi dispne, taşikardi >150.
YELLOW (Acil, 60dk): Orta ağrı (5-7/10), yüksek ateş >38.5, vomiting, dehidrasyon, fraktur.
GREEN (Standart, 120dk): Hafif ağrı (<5/10), kronik şikayet alevlenmesi, küçük travma.
BLUE (Rutin, 240dk): Kronik hastalık takibi, reçete yenileme, hafif USYE."""
    },
    {
        "source": "MTS_Triage_Guide",
        "category": "triage_protocol",
        "text": """MTS Ağrı Değerlendirmesi:
0-3: Hafif ağrı - GREEN
4-6: Orta ağrı - YELLOW
7-9: Şiddetli ağrı - ORANGE
10: Dayanılmaz ağrı - RED
CTAS ağrı soruları: Lokalizasyon, yayılım, başlangıç, süre, tetikleyici, kötüleştiren faktörler."""
    },
    # Kardiyak Acil
    {
        "source": "Cardiac_Emergency_Protocol",
        "category": "emergency_protocol",
        "text": """Akut Miyokard Enfarktüsü (AMI) Belirtileri:
Göğüs ağrısı/baskısı > 20 dakika, sol kol/çene/sırt yayılması, diyaforez, bulantı, dispne.
Atipik sunum: Epigastrik ağrı, sırt ağrısı (özellikle kadınlar ve diyabetiklerde).
TIMI skoru risk faktörleri: Yaş >65, diyabet, HT, sigara, aile hikayesi.
Triaj: KESINLIKLE RED — EKG, troponin, aspirin 300mg, O2."""
    },
    {
        "source": "Cardiac_Emergency_Protocol",
        "category": "emergency_protocol",
        "text": """Hipertansif Kriz:
Hipertansif Acil: KB >180/120 + organ hasarı (troponin yüksekliği, AKI, ensefalopati, papil ödem) → RED
Hipertansif Urjansi: KB >180/120, organ hasarı yok → YELLOW
Semptomlar: Baş ağrısı, görme bozukluğu, göğüs ağrısı, nörolojik semptomlar.
Sorulacak: KB değerleri, kronik HT hikayesi, ilaç uyumu, baş ağrısı şiddeti."""
    },
    # Nörolojik Acil
    {
        "source": "Neurological_Emergency",
        "category": "emergency_protocol",
        "text": """İnme (CVA) FAST Değerlendirmesi:
F (Face): Yüzde asimetri/sarkma var mı?
A (Arm): Kol gücü simetrik mi? (kolları kaldır, tut)
S (Speech): Konuşma bozukluğu var mı? (afazi, dizartri)
T (Time): Semptom başlangıç zamanı! tPA penceresi 4.5 saat.
+ BALANCE: Denge kaybı
+ EYES: Görme kaybı
+ HEAD: Ani şiddetli baş ağrısı
Triaj: RED — Kod inme aktivasyonu, CT angio ivedi."""
    },
    {
        "source": "Neurological_Emergency",
        "category": "emergency_protocol",
        "text": """Baş ağrısı Kırmızı Bayrakları (RED FLAGS):
"Hayatımın en kötü baş ağrısı" (subaraknoid kanama)
Ani başlangıç (thunderclap headache)
Ateş + boyun sertliği + ışık hassasiyeti (menenjit)
Nörolojik defisit eşlik ediyor
İmmünosüpresif hasta veya kanser hikayesi
Progresif kötüleşme, yatmakla kötüleşme
Tümü → RED triaj gerektirir."""
    },
    # Solunum
    {
        "source": "Respiratory_Protocol",
        "category": "emergency_protocol",
        "text": """Solunum Sıkıntısı Değerlendirmesi:
Hafif dispne (SpO2 >94%, KB stabil): YELLOW
Orta dispne (SpO2 90-94%, yardımcı solunum kasları aktif): ORANGE
Şiddetli dispne (SpO2 <90%, siyanoz, bilinç değişikliği): RED
WHEEZING: Astım/KOAH → Bronkodilatatör, nebülizasyon
Tek taraflı solunum sesi azalması: Pnömotoraks! → RED
Pembe köpüklü balgam + ortopne: Pulmoner ödem → RED"""
    },
    # Karın Ağrısı
    {
        "source": "Abdominal_Pain_Guide",
        "category": "clinical_guideline",
        "text": """Karın Ağrısı Değerlendirmesi:
Yaygın defans/rijidite: Perforasyon → RED
Sağ alt kadran ağrısı + McBurney hassasiyeti + ateş: Apandisit → ORANGE
Ani sağ üst kadran ağrısı + sarılık + ateş (Charcot triadı): Kolanjit → RED
Göbek çevresinden başlayıp sağ alta yayılan + iştahsızlık: Apandisit
Sırt yayılımlı epigastrik ağrı + bulantı + ateşsiz: Pankreatit"""
    },
    # Pediatrik
    {
        "source": "Pediatric_Triage",
        "category": "clinical_guideline",
        "text": """Pediatrik Triaj Özel Kriterleri:
<3 ay bebek ateş >38°C: Hemen değerlendirme (RED/ORANGE)
Fontanel bombeliği: Menenjit → RED
Trakeal çekinti, stridor: Krup/epiglottit → RED/ORANGE
Dehidrasyon: Gözyaşı yok, ağız kuru, kapiller dolum >3sn → YELLOW/ORANGE
Ateşli konvülsiyon: Çocuklarda sık; bilinç açılırsa genellikle benign"""
    },
    # Sepsis
    {
        "source": "Sepsis_Protocol",
        "category": "emergency_protocol",
        "text": """Sepsis Erken Tanı (qSOFA):
Solunum hızı ≥22/dk
GCS <15 (bilinç değişikliği)
Sistolik KB ≤100 mmHg
2/3 kriter: Sepsis şüphesi → RED
SIRS kriterleri: Ateş >38 veya <36, nabız >90, solunum >20, lökosit >12K veya <4K
Odak: Pnömoni (öksürük, dispne), üriner (disüri, kostovertebral açı hassasiyeti), batın"""
    },
    # Yaşlı Hasta
    {
        "source": "Geriatric_Triage",
        "category": "clinical_guideline",
        "text": """Yaşlı Hasta Triaj Özel Dikkatler:
Ateşsiz sepsis görülebilir (hipotermi oluşabilir)
AMI atipik sunum: epigastrik ağrı, halsizlik, dispne (göğüs ağrısı olmayabilir)
Düşme: Kalça fraktürü şüphesi — hareket kısıtlılığı + ağrı → Görüntüleme
Bilinç değişikliği: Altta yatan acil (sepsis, AMI, inme, ilaç intoksikasyonu) araştır
Polifarmasi: İlaç-ilaç etkileşimi, toksik tablo olasılığı yüksek"""
    },
    # Türkçe Tıbbi Terminoloji
    {
        "source": "Medical_Terminology_TR",
        "category": "terminology",
        "text": """Klinik Tıp Terimleri (Türkçe-İngilizce):
Dispne (Dyspnea): Nefes darlığı
Taşikardi (Tachycardia): Hızlı kalp atışı >100/dk
Bradikardi: Yavaş kalp atışı <60/dk
Diyaforez (Diaphoresis): Aşırı terleme
Senkop (Syncope): Bayılma
Prezenkop (Presyncope): Bayılma hissi
Pallor: Solgunluk
Siyanoz: Morluğun görülmesi → SpO2 düşüklüğü
Dizartri: Konuşma güçlüğü (motor)
Afazi: Konuşamama (dil merkezi)
Hemipareji/Hemipleji: Tek taraf kol-bacak güçsüzlüğü"""
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

