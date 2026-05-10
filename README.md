# AnamnezAI — Medical Pre-Triage Platform

**AI-powered patient anamnesis and triage for Turkey's 117M annual emergency visits — Gemma 4 (`gemma4:e4b`) turns a 15-minute doctor intake into a 4-minute AI interview, fully local via Ollama, zero cloud cost.**

[![Built with Gemma 4](https://img.shields.io/badge/Powered%20by-Gemma%204%20(e4b)-4285F4?logo=google)](https://ollama.com/library/gemma4)
[![MedGemma Vision](https://img.shields.io/badge/Vision-MedGemma%204b-34A853?logo=google)](https://ollama.com/library/medgemma)
[![Ollama Local](https://img.shields.io/badge/Runtime-Ollama%20Local-black)](https://ollama.com)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%205.0-009688)](https://fastapi.tiangolo.com)
[![FHIR R4](https://img.shields.io/badge/Standard-FHIR%20R4-E86B1D)](https://hl7.org/fhir/)
[![Hackathon](https://img.shields.io/badge/Gemma%204%20Good%20Hackathon-Health%20%26%20Ollama-orange)](https://www.kaggle.com/competitions/gemma-4-good-hackathon)
[![License: CC-BY 4.0](https://img.shields.io/badge/License-CC--BY%204.0-green)](https://creativecommons.org/licenses/by/4.0/)

> **3 Gemma model, 3 klinik görev:** `gemma4:e4b` bağlamsal anamnez + MTS triage + FHIR klinik raporu üretir. `medgemma:4b` yara/EKG/cilt görüntülerini analiz eder. `gemma3:1b` basit ilk adım sorularını Tier routing ile hızlı yanıtlar. Tüm modeller Ollama ile yerel çalışır — hasta verisi asla buluta gitmez.

> **Hedef:** Türkiye'deki 117 milyon yıllık acil servis başvurusunu daha verimli yönet; doktorun her başvurucuya harcadığı 15–20 dakikalık anamnez süresini ~4 dakikaya indir, köy kliniklerinde internet olmadan tam çalış.
---

## 🏆 Hackathon Parçaları

| Ödül Parkuru | Değer | Yeterlilik |
|-------------|-------|-----------|
| **🏥 Health & Sciences** | $10,000 | Türkiye kamu sağlık sisteminde Gemma 4 ile tıbbi ön-triaj |
| **🦙 Ollama Prize** | $10,000 | `gemma4:e4b` + `medgemma:4b` + `gemma3:1b` tamamen yerel, sıfır API maliyeti |
| **Genel** | $50,000 | RAG + FHIR R4 + MTS/CTAS + Tier routing + Vision — çok katmanlı klinik AI |

---

## 🎬 Demo Senaryosu (3 Dakika)

Hasta: **Ahmet Yılmaz, 58 yaş, Erkek** — sabahtan beri göğüs baskısı.

```
Adım 1 — Hasta Girişi (Kiosk / Web)
  Gemma 4 › "Sizi bugün buraya getiren en önemli şikayetiniz nedir?"
  Hasta  › "Sabahtan beri göğsümde baskı var"
  Gemma 4 › [önceki yanıtı okudu — kardiyak yol] 
            "Bu baskı sol kolunuza ya da çenenize yayılıyor mu?"
  Hasta  › "Evet, sol koluma kadar geliyor"
  ... 5 bağlamsal soru / ~4 dakika ...

Adım 2 — MedGemma Vision
  EKG fotoğrafı yükleniyor →
  "ST elevasyonu şüpheli — MI paterni değerlendirilmeli"

Adım 3 — Triaj Kararı (gemma4:e4b)
  triage_level:  "RED"
  confidence:    94%
  conditions:    ["AMI", "NSTEMI", "Unstable Angina"]
  urgency_flags: ["Kardiyak risk faktörleri", "Klasik MI sunumu"]
  icd10:         "I21.9"

Adım 4 — Doktor Paneli (SSE canlı)
  🔴 ACL KUYRUK — ICD-10: I21.9 — FHIR R4 Export
```
---

## 📸 Ekranlar

### Hasta Mülakatı & Triaj

| | |
|---|---|
| ![AI Mülakat — glassmorphism, bağlamsal soru](frontend/screens/interview.png) | ![Triaj Sonucu — SVG güven halkası, RED badge](frontend/screens/triage_result.png) |
| **Bağlamsal AI Mülakat** — Gemma 4 önceki yanıtların tümünü okuyarak klinik açıdan en değerli soruyu üretir; statik form mantığı yok | **Triaj Sonucu** — Animated SVG güven halkası (%94), RED/YELLOW/GREEN badge, urgency flags, olası tanı listesi |
| ![ICD-10 Otomatik Kodlama](frontend/screens/icd10.png) | ![MedGemma Vision — EKG analizi](frontend/screens/vision_analysis.png) |
| **ICD-10 Otomatik Kodlama** — Olası tanılar uluslararası kodlarıyla eşleştirilir, Türkçe açıklama dahil | **MedGemma Vision** — EKG şeridi, yara fotoğrafı, cilt lezyonu; acil bulgular (ST elevasyonu, nekroz) açıkça işaretlenir |

### Doktor Paneli & Klinik İnceleme

| | |
|---|---|
| ![Doktor Triaj Kuyruğu — SSE canlı](frontend/screens/doctor_queue.png) | ![Klinik İnceleme — FHIR export](frontend/screens/clinical_review.png) |
| **Doktor Triaj Kuyruğu** — SSE ile anlık güncelleme, renk kodlu öncelik (🔴→🟡→🟢), slayt-ın detay paneli | **Klinik İnceleme** — Tam Q&A transkripti, vital bulgular (normal aralık dışı renkli), ICD-10 tablo, FHIR R4 JSON export |

### Kiosk & Admin

| | |
|---|---|
| ![Kiosk Modu — dokunmatik, QR fişi](frontend/screens/kiosk.png) | ![Admin Dashboard — Chart.js analitik](frontend/screens/admin_analytics.png) |
| **Kiosk Modu** — 56px dokunma hedefleri, TR/EN dil seçimi, QR sıra fişi, 3 dk inaktivite auto-reset, admin PIN kilidi | **Admin Analitik** — Günlük başvuru grafiği, triaj dağılımı, model kullanım metriği, KVKK audit log, CSV export |

### Hasta Paneli

| | |
|---|---|
| ![Hasta Dashboard — ziyaret geçmişi, stat kartlar](frontend/screens/patient_dashboard.png) | ![Hasta Profil — tıbbi form, inline SPA](frontend/screens/patient_profile.png) |
| **Hasta Dashboard** — Önceki ziyaret kartları, ilaç listesi, triaj geçmişi | **Tıbbi Profil** — Doğum yılı, cinsiyet, kan grubu, kronik hastalık/ilaç/alerji etiketleri — hasta panelinin içinde SPA section olarak |

> Ekranlar `frontend/screens/` klasöründe bulunur.
---

## ❓ Nedir?

AnamnezAI, hastane öncesi hasta anamnez toplama sürecini Gemma 4 ailesi modellerle tamamen otomatize eden bir **tıbbi ön-triaj platformudur**.

Hasta kiosk veya web arayüzünden semptomlarını girer. Gemma 4, önceki tüm yanıtları okuyarak bir sonraki en klinik değerli soruyu dinamik olarak üretir. 5 tur sonra **Manchester Triage System (MTS)** kriterlerine göre RED/YELLOW/GREEN triaj kararı verir, olası tanıları ICD-10 kodlarıyla listeler ve doktor için **FHIR R4 uyumlu klinik özet** oluşturur.

**Clone-and-go:** Repo'yu klonla, `docker compose up --build`, doğrudan çalışır. API anahtarı, bulut bağlantısı veya GPU gerekmez.

## 🤔 Neden?
- Türkiye'de yılda **117 milyon** acil servis başvurusu yapılıyor. Tek doktorun günde 40+ hastayı elle triaj etmesi mümkün değil.
- Mevcut triage formları **statik** — "göğüs ağrısı" girişine "sol kola yayılıyor mu?" diye sormayan kağıt formlar.
- **Köy sağlık ocaklarında** internet bağlantısı olmayabilir — bulut tabanlı AI buralarda çalışmaz.
- **KVKK/HIPAA:** Hasta verisinin buluta gönderilmesi hukuki sorunlar doğurur; Ollama ile tüm işlem cihaz üzerinde kalır.

**Gemma 4'ün bu uygulamada önceki model nesline göre somut farkları:**

| Kapasite | Gemma 3 / küçük modeller | Gemma 4 e4b |
|----------|--------------------------|-------------|
| Tıbbi akıl yürütme | Genel bilgi | AMI semptomlarını tanıyıp kardiyak soru zinciri kurabilir |
| Bağlamsal hafıza | Sınırlı window | 5 soruluk tüm geçmişi tek prompt'ta tutar |
| Multimodal | Yok | EKG + yara + metin aynı sorguda analiz eder |
| Türkçe tıbbi dil | Genel | Klinik düzeyde Türkçe terminoloji, ayrı fine-tune gerektirmez |
| Think bloğu | Yok | `<think>` kanalıyla neden o soruyu sorduğu izlenebilir |
## 👥 Kimler çin?
- **Türkiye Sağlık Bakanlığı** — Aile Sağlığı Merkezleri ve ASM'lerde triaj yükünü azaltmak
- **Özel klinikler ve poliklinikler** — hasta akış hızlandırma, doktor memnuniyeti
- **Köy sağlık ocakları / gezici klinikler** — çevrimdışı, tek cihazda tam çalışan sistem
- **Sağlık STK'ları** — düşük kaynaklı ortamlarda veriye dayalı triaj
---
## ✨ Özellikler
### 🤖 AI Mülakat Motoru
- **Bağlamsal soru üretimi** — Gemma 4, konuşmanın tamamını okuyarak her seferinde klinik açıdan en değerli soruyu dinamik olarak üretir; statik form mantığı yoktur
- **Akıllı model yönlendirme (Tier routing)** — adım ≤ 2 ve acil semptom yoksa `gemma3:1b` hızlı yanıt verir; adım > 2, triaj veya "göğüs/nefes/bilinç/kalp/inme" anahtar kelimesi varsa otomatik `gemma4:e4b`'ye yükseltilir
- **5 tur mülakatı** — 5 bağlamsal soru tamamlandıktan sonra triage JSON çıktısı üretilir
- **Vital bulgu entegrasyonu** — kan basıncı, nabız, SpO₂, ateş, solunum hızı önceden girilirse prompt'a otomatik eklenir
- **Think bloğu temizliği** — `<think>...</think>` etiketleri hasta/doktor arayüzüne çıkmadan server tarafında filtrelenir
### 🔴 MTS Triaj Motoru
- **Manchester Triage System + CTAS** kriterleri — RED / YELLOW / GREEN sınıflandırması
- **Yapılandırılmış JSON çıktısı** — `triage_level`, `confidence_score`, `chief_complaint`, `possible_conditions`, `urgency_flags`, `recommended_action`, `clinical_notes`
- **Urgency flags** — "Kardiyak risk faktörleri mevcut", "AMI paterni" gibi kritik bayraklar doktora öne çıkar
- **ICD-10 otomatik kodlama** — olası tanılar Türkçe açıklama + ICD-10 kodlarıyla eşleştirilir
### 🔬 MedGemma Vision — Tıbbi Görüntü Analizi
- **Model önceliği** — `medgemma:4b` kuruluysa kullanılır; kurulu değilse `gemma4:e4b` multimodal ile otomatik yedek
- **Desteklenen içerik** — yara fotoğrafları, cilt döküntüleri, EKG şeritleri, röntgen görüntüleri (max 15 MB)
- **Acil bulgular** — enfeksiyon/nekroz/MI paterni gibi acil bulgular açıkça işaretlenir
- **Rapor entegrasyonu** — görüntü analizi sonuçları `image_findings` alanı ile klinik özetine otomatik eklenir
### 📚 RAG — Tıbbi Bilgi Tabanı
- **ChromaDB + all-MiniLM-L6-v2** embedding motoru (yerel, ücretliz)
- **Dahili bilgi tabanı** — MTS protokolleri, Türkiye acil servisi standartları, sık görülen sendromlar, ilaç uyarıları, alerji protokolleri
- **Dinamik bağlam enjeksiyonu** — her triaj sorusu üretimi ve klinik özet için en ilgili k=4 doküman chunk'ı prompt'a eklenir; min_relevance=0.3 eşiği
- **PDF ingest API** — admin/klinisyen yeni protokol PDF'leri `/api/rag/ingest/pdf` ile sisteme ekleyebilir
- **Kaynak rozeti** — summary ekranında hangi kaynaktan yararlanıldığı gösterilir
### 🎤 Sesli Giriş + Erişilebilirlik
- **Web Speech API** — yaşlı ve düşük okuryazarlık düzeyi yüksek hastalar için mikrofon ile semptom girişi
- **Text-to-Speech yönlendirme** — kiosk modunda Gemma 4'ün sorduğu her soru yüksek sesle okunur
- **WCAG 2.1 AA** — %4.5:1 kontrast oranı, minimum 56px dokunma hedefleri, yüksek kontrast / büyük yazı toggle
- **Klavye navigasyonu** — tüm akış fare olmadan kullanılabilir
### 🖥️ Kiosk Modu + QR
- **Tam ekran kiosk** — dokunmatik ekran optimize, mouse/klavye bağımlılığı yok
- **3 dakika inaktivite auto-reset** — bir sonraki hasta için ekran otomatik temizlenir
- **QR kod üretimi** — hasta sıra numarası QR kodu oluşturulur, termal yazıcıdan basılabilir
- **Kilit/Kilit Açma** — admin PIN ile kiosk kilitlenebilir (bakım modu)
- **Çift dil** — hasta TR/EN seçimi → tüm mülakat seçilen dilde yürütülür
### 👨‍⚕️ Doktor Paneli
- **SSE ile canlı kuyruk** — yeni hasta triaj alır almaz doktor ekranı anında güncellenir
- **Renk kodlu öncelik sırası** — 🔴 RED üstte, 🟡 YELLOW ortada, 🟢 GREEN altta
- **Slayt-ın detay paneli** — hastaya tıkla → tam Q&A transkripti, vital bulgular, görüntü bulguları
- **Triaj override** — doktor AI kararını manuel değiştirebilir, değişiklik audit log'a kaydedilir
- **Doktor notu** — `PUT /api/session/{id}/note` ile not eklenir, FHIR ClinicalImpression'a bağlanır
### 📋 Klinik nceleme
- **Tam Q&A transkripti** — hastanın verdiği tüm yanıtlar soru/yanıt çiftleri halinde
- **Vital bulgu tablosu** — normal aralık dışı değerler renk kodlu vurgulama
- **ICD-10 tablo** — olası tanılar + uluslararası kodları yan yana
- **FHIR R4 export** — `Patient` + `ClinicalImpression` + `Observation` + `Condition` bundle tek tıkla JSON indir
- **PDF yazdırma** — tarayıcı print diyaloğu ile hasta dosyası çıktısı
### 🔐 JWT Auth + Çok Rol
- **4 rol:** `patient`, `doctor`, `admin`, `staff` — her endpoint role-guard ile korunmuş
- **Google OAuth2** — Google ID token ile tek tıkla giriş (hasta rolü)
- **Klinik kodu ile doktor kaydı** — sadece doğru kodu bilen doktor rolüyle kayıt olabilir
- **KVKK veri silme** — hasta `DELETE /api/session/{id}` ile verilerini tamamen silebilir
### 🏥 Admin & Analitik
- **Chart.js dashboard** — günlük başvuru, triaj dağılımı, model kullanım grafiği, ort. mülakat süresi
- **Audit log** — KVKK/GDPR uyumlu; her mutasyon zaman damgalı kaydedilir
- **CSV export** — admin anonimleştirilmiş tüm veriyi indirebilir
- **Rate limiting** — slowapi: 200 istek/dakika
---
## 🚀 Hızlı Başlangıç
### Ön Koşullar
- [Ollama](https://ollama.com) yüklü
- Docker Desktop **veya** Python 3.11+
### 1. Modelleri ndir
```bash
# Ana model (zorunlu)
ollama pull gemma4:e4b     # ~5 GB — triaj + mülakat + klinik rapor
# Vision modeli (opsiyonel — yoksa Gemma 4 multimodal devreye girer)
ollama pull medgemma:4b    # ~5 GB — yara, EKG, cilt analizi
# Lite model (opsiyonel — Tier 1 hızlı rutinler için)
ollama pull gemma3:1b      # ~1 GB
```
### 2. Docker ile Başlat (Önerilen)
```bash
git clone https://github.com/enis1998/AnamnezAI
cd AnamnezAI
docker compose up --build -d
# Frontend: http://localhost:8000
# API Docs: http://localhost:8000/docs
```
### 3. Manuel Kurulum
```bash
cd AnamnezAI/backend
pip install -r requirements.txt
python main.py
```
### 4. Windows PowerShell
```powershell
cd AnamnezAI
.\setup.ps1
```
### Ortam Değişkenleri
```bash
GEMMA_MODEL=gemma4:e4b
MEDGEMMA_MODEL=medgemma:4b
LITE_MODEL=gemma3:1b
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_NUM_GPU=0         # 0=CPU, 1+=GPU
RAG_ENABLED=true
GOOGLE_CLIENT_ID=        # Google OAuth (opsiyonel)
```
### Demo Kullanıcıları
| Rol | E-posta | Şifre | Notlar |
|-----|---------|-------|--------|
| Doktor | `doctor@anamnezai.tr` | `doctor123` | Triaj kuyruğu + klinik inceleme |
| Admin | `admin@anamnezai.tr` | `admin123` | Analytics + audit log + CSV export |
| Yeni Doktor | Herhangi e-posta | — | Klinik kodu: `DEMO2026` |
| Hasta | `register.html` ile kayıt | — | Oturum + hasta profil sistemi |
---
## 📡 API Referansı
| Method | Endpoint | Auth | Açıklama |
|--------|---------|------|----------|
| `GET` | `/health` | — | Ollama + model durumu, RAG stats |
| `POST` | `/api/warmup` | — | Gemma 4'ü VRAM'e önceden yükle |
| `POST` | `/auth/register` | — | Yeni kullanıcı kaydı |
| `POST` | `/auth/login` | — | E-posta/şifre → JWT token |
| `POST` | `/auth/google` | — | Google ID token → JWT |
| `GET` | `/auth/me` | JWT | Oturum kullanıcı bilgisi |
| `GET/PUT` | `/auth/profile` | JWT | Hasta profili (ilaç/alerji/kronik) |
| `POST` | `/api/session/start` | — | Yeni mülakat başlat → ilk soru |
| `POST` | `/api/session/answer` | — | Yanıt gönder → sonraki soru |
| `GET` | `/api/session/{id}/summary` | — | Triage JSON + klinik özet |
| `GET` | `/api/session/{id}/stream-summary` | — | SSE streaming klinik anlatı |
| `PUT` | `/api/session/{id}/note` | JWT(doctor) | Doktor notu ekle |
| `DELETE` | `/api/session/{id}` | JWT | KVKK veri silme |
| `GET` | `/api/patients/queue` | JWT(doctor) | Triaj kuyruğu |
| `GET` | `/api/patient/history` | JWT | Hasta geçmiş başvuruları |
| `POST` | `/api/analyze-image` | — | MedGemma / Gemma 4 Vision analizi |
| `GET` | `/api/rag/status` | — | ChromaDB + embedding durumu |
| `POST` | `/api/rag/ingest/pdf` | — | PDF protokol yükle (arka plan) |
| `GET` | `/api/rag/query` | — | RAG manuel sorgu + preview |
| `GET` | `/api/analytics` | JWT(admin) | Triaj istatistikleri |
| `GET` | `/api/export/csv` | JWT(admin) | Anonimleştirilmiş CSV export |
| `GET` | `/api/audit-log` | JWT(admin) | KVKK audit kaydı |
| `POST` | `/api/kiosk/lock` | JWT(admin) | Kiosk kilitle/aç |
---
## 🛠 Teknoloji Yığını
| Katman | Teknoloji |
|--------|-----------|
| **AI — Ana** | Gemma 4 (`gemma4:e4b`) — triaj, bağlamsal soru, klinik rapor |
| **AI — Vision** | MedGemma (`medgemma:4b`) — tıbbi görüntü analizi |
| **AI — Lite** | Gemma 3 (`gemma3:1b`) — Tier 1 hızlı sorular |
| **AI Runtime** | Ollama — yerel LLM sunucusu, sıfır API maliyeti |
| **Backend** | FastAPI 0.115 (Python 3.11) + asyncio + httpx |
| **Veritabanı** | SQLite — sessions, summaries, users, audit_log |
| **RAG** | ChromaDB 0.6 + sentence-transformers (all-MiniLM-L6-v2) |
| **Auth** | JWT (PyJWT) + bcrypt + Google OAuth2 |
| **Rate Limiting** | slowapi (200 req/min) |
| **Frontend** | Vanilla JS + Tailwind CDN + Chart.js + Web Speech API |
| **Klinik Standart** | FHIR R4 — Patient + ClinicalImpression + Observation |
| **Triaj Standardı** | Manchester Triage System (MTS) + CTAS |
| **Deployment** | Docker Compose + Dockerfile |
| **Orkestrasyon** | Kubernetes (deployment.yaml + HPA + Ingress) |
| **PWA** | manifest.json + Service Worker |
---
## 🏗 Mimari
```
┌──────────────────────────────────────────────────────────────┐
│                    KULLANICI KATMANI                         │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌───────────┐  │
│  │   Web    │  │   Kiosk   │  │  Doktor  │  │   Admin   │  │
│  │ (Hasta)  │  │  (TR/EN)  │  │ SSE Canlı│  │ Analitik  │  │
│  │ PWA+ses  │  │ QR+dokunma│  │  kuyruk  │  │ Chart.js  │  │
│  └────┬─────┘  └─────┬─────┘  └────┬─────┘  └─────┬─────┘  │
│       └──────────────┴──────────────┴───────────────┘        │
└────────────────────────────┬─────────────────────────────────┘
                             │ HTTP / SSE
┌────────────────────────────▼─────────────────────────────────┐
│                 FastAPI Backend v5.0                         │
│  JWT Auth │ Rate Limit │ Audit Log │ SSE │ FHIR R4           │
└──────────┬─────────────────┬──────────────┬──────────────────┘
           │                 │              │
┌──────────▼──────┐  ┌───────▼────────┐  ┌─▼──────────────────┐
│   Ollama        │  │    ChromaDB    │  │      SQLite        │
│  gemma4:e4b     │  │  RAG Vector   │  │  sessions          │
│  medgemma:4b    │  │  MiniLM embed │  │  summaries         │
│  gemma3:1b      │  │  MTS/ICD-10   │  │  users + auth      │
│  (Tier routing) │  │  top-k cosine │  │  audit_log         │
└─────────────────┘  └───────────────┘  └────────────────────┘
🔒 Tüm modeller YEREL (Ollama) — Sıfır API maliyeti
🔒 Hasta verisi asla buluta gitmiyor
```
---
## 🧠 Gemma 4 Kullanım Akışı
```
HASTA                    GEMMA 4 (via Ollama)              DOKTOR
─────                   ──────────────────────             ──────
[Başlat]  → /start  →  lk soruyu üret (SYSTEM_PROMPT_TR)
                        ↑ RAG: MTS protokol bağlamı enjekte
[Cevap]   → /answer →  Bağlamsal soru üret (history aware)
                        ↑ Tier routing: adım≤2 → gemma3:1b
                        ↑ Acil semptom → gemma4:e4b
… 5 tur …
[Biter]   → /summary→  MTS triaj JSON üret (TRIAGE_SYSTEM_TR)
                        ↑ RAG: ICD-10 referans bağlamı
           → /stream →  Klinik özet SSE akışı
[Görüntü] → /analyze→  MedGemma / Gemma 4 Vision analizi
                                            ← [SSE Kuyruk Güncelleme]
                                            ← [Klinik Rapor Okur]
                                            ← [FHIR R4 Export]
```
### Tier Yönlendirme Mantığı
```
Tier 1 (gemma3:1b)   → adım ≤ 2  AND  acil semptom yok  AND  lite kurulu
Tier 2 (gemma4:e4b)  → triaj | klinik özet | ICD-10 | SSE stream
                      → adım > 2 VEYA "göğüs/nefes/bilinç/kalp/inme/koma"
```
### Triaj Seviyeleri
| Seviye | Renk | Anlam | Örnekler |
|--------|------|--------|---------|
| 🔴 **RED** | `#ba1a1a` | Hayati risk — derhal | AMI, inme, anafilaksi, GCS<8 |
| 🟡 **YELLOW** | `#e07b26` | Acil — 30dk–2saat | Yüksek ateş, orta ağrı, HT krizi |
| 🟢 **GREEN** | `#006a68` | Rutin — poliklinik | Hafif semptom, kronik takip, ÜSYE |
---
## 📁 Proje Yapısı
```
AnamnezAI/
├── README.md                       # Bu dosya
├── ROADMAP.md                      # Sprint 14–18 — yarışma öncesi detaylı plan
├── GEMMA4_MODEL_CARD.md            # Jüri için Gemma 4 kullanım kanıtı
├── PROJECT_PLAN.md                 # Sprint 1–13 detaylı geçmiş (Türkçe)
├── setup.ps1                       # Windows tek tıkla kurulum
├── docker-compose.yml
├── Dockerfile
│
├── backend/
│   ├── main.py                     # FastAPI v5.0 — tüm endpointler (2164+ satır)
│   ├── auth.py                     # JWT + bcrypt + 4 rol + Google OAuth2
│   ├── rag.py                      # ChromaDB + MiniLM + PDF ingest pipeline
│   ├── anamnezai.db                # SQLite veri (gitignore'da)
│   └── requirements.txt
│
├── frontend/
│   ├── index.html                  # Hasta mülakatı (landing + AI chat)
│   ├── summary.html                # Klinik özet + triaj kartı (animated SVG)
│   ├── doctor.html                 # Doktor triaj paneli (SSE kuyruk)
│   ├── clinical_review.html        # Tam klinik inceleme + FHIR R4 export
│   ├── patient_dashboard.html      # Hasta paneli — 4 section SPA:
│   │                               #   overview / history / meds / profile
│   ├── login.html / register.html  # Auth sayfaları
│   ├── kiosk.html                  # Kiosk dokunmatik modu (QR + kilit)
│   ├── analytics.html              # Admin dashboard (Chart.js)
│   ├── admin.html                  # Sistem yönetimi
│   ├── manifest.json               # PWA manifest
│   ├── sw.js                       # Service Worker (offline desteği)
│   └── screens/                   # Ekran görüntüleri
│
├── notebooks/
│   ├── mediscreen_ai_kaggle.ipynb  # Kaggle submission notebook
│   └── train_gemma4_medical.ipynb  # Fine-tuning (opsiyonel)
│
├── kubernetes/
│   └── deployment.yaml             # K8s Deployment + HPA + Ingress
│
└── chroma_db/                      # ChromaDB vektör veritabanı (gitignore'da)
```
---
## 📅 Sprint Geçmişi

**Gün 0 — 2026-01-07** · Repo kurulum, FastAPI + Ollama/Gemma 4 altyapısı, SYSTEM_PROMPT_TR (MTS odaklı), triage endpoint'leri, Docker.

**Gün 1 — 2026-01-08** · Tam UI yeniden tasarım: glassmorphism stil, animated SVG güven halkası, triaj renk kartları, Docker optimizasyonu.

**Gün 2 — 2026-01-09** · Kiosk modu (dokunmatik optimize, TR+EN, 56px hedefler), QR kod sıra fişi, kiosk kilit/açma paneli.

**Gün 3 — 2026-01-10** · Mobil responsive, hasta dashboard (bottom sheet nav, ziyaret geçmişi, stat kartları).

**Gün 4 — 2026-01-11** · clinical_review.html: FHIR R4 export (Patient + ClinicalImpression + Observation + Condition bundle), ICD-10 tablosu, doktor notu endpoint'i.

**Gün 5 — 2026-01-12** · RAG motoru: ChromaDB + all-MiniLM-L6-v2, tıbbi doküman yükleme pipeline, PDF ingest API, dinamik bağlam enjeksiyonu.

**Gün 6 — 2026-01-13** · Rate limiting (slowapi 200/min), session TTL, KVKK audit log, Kubernetes manifest (HPA + Ingress).

**Gün 7 — 2026-01-14** · JWT auth: 4 rol (patient/doctor/admin/staff), Google OAuth2, klinik kodu ile doktor kaydı, demo kullanıcılar.

**Gün 8 — 2026-01-15** · Tier routing: `gemma3:1b` (adım ≤ 2, acil semptom yok) / `gemma4:e4b` (klinik karar, acil, özet).

**Gün 9 — 2026-01-16** · Web Speech API TTS+STT, Service Worker (offline PWA), Chart.js admin analitik dashboard.

**Gün 10 — 2026-01-17** · MedGemma Vision entegrasyonu: `/api/analyze-image`, image_findings alanı, otomatik medgemma→gemma4 fallback.

**Gün 11 — 2026-02-20** · Profil SPA entegrasyonu: `profile.html` ayrı sayfası → `patient_dashboard.html` içinde inline section (4-section SPA: overview/history/meds/profile).

**Devam eden — Mayıs 2026:**

| Sprint | Başlık | Durum |
|--------|--------|-------|
| **S-14** | Demo güvenilirliği — `/health` model_ready, Türkçe 503, think garantisi | ✅ Tamamlandı |
| **S-15** | Gemma 4 farklılaştırıcılar — thinking modu UI, MedGemma badge, model durum kartı | ✅ Tamamlandı |
| **S-16** | RAG & klinik kalite — ek Türkçe protokoller, RAG kaynak rozeti, alerji banner | ✅ Tamamlandı |
| **S-17** | Demo materyali — ekran görüntüleri, Kaggle notebook, README final | ✅ Tamamlandı |
| **S-18** | Bonus — Model karşılaştırma API + Admin RAG yönetim UI | ✅ Tamamlandı |
| **S-19** | QA & son dokunuşlar — Tier routing, model badge, FHIR/ICD10 fix, sw.js güncelleme | ✅ Tamamlandı |
| **S-18** | Bonus — multimodel yan yana karşılaştırma, offline mode | 🔵 Bonus |

Detaylı kalan sprint planı → [ROADMAP.md](./ROADMAP.md)
---
## 📚 RAG Bilgi Tabanı & İngest Pipeline

AnamnezAI'nin klinik kalitesi, ChromaDB'ye yüklenen tıbbi bilgi tabanına dayanır. Mevcut durum:

| Kategori | Belge | Chunk | İçerik |
|----------|------:|------:|--------|
| MTS/CTAS Triaj Protokolleri | 8 | ~160 | Manchester kriterleri, CTAS algoritmaları |
| Türkiye Acil Servis Standartları | 5 | ~120 | SB genelgeleri, acil kategorileri |
| Semptom Değerlendirme Kılavuzları | 6 | ~180 | Göğüs/dispne/nörolojik/kardiyak algoritmalar |
| ICD-10 Türkçe Referans | 4 | ~200 | Yaygın acil tanı kodları, Türkçe açıklama |
| İlaç & Alerji Protokolleri | 3 | ~90 | Etkileşim uyarıları, anafilaksi yönetimi |
| Vital Bulgu Referans Aralıkları | 2 | ~60 | Yaş/cinsiyet bazlı normal değerler |
| **Toplam** | **28** | **~810** | 384-boyutlu MiniLM vektörleri |

### İngest Pipeline

```
Ham kaynak (PDF / metin dokümanı)
    ↓
Parse + temizle (PyPDF2 · python-docx)
    ↓
Semantik parçalara böl (500 karakter, 50 overlap)
    ↓
all-MiniLM-L6-v2 embedding (384 boyut)
    ↓
ChromaDB'ye yaz (cosine benzerlik indeksi)
    ↓
Retrieval: top-k=4, min_relevance=0.3 → prompt'a enjekte
```

### Sprint 16 Planında: Ek Belgeler

| Eklenecek Kaynak | Hedef Chunk | Neden |
|-----------------|------------:|-------|
| Türkiye SB Acil Servis İstatistikleri 2024 | ~80 | Gerçek dünya bağlamı |
| Genişletilmiş ICD-10 Türkçe Kütüphanesi | ~300 | Daha doğru kodlama |
| KVKK Veri İşleme Protokolü | ~30 | Hukuki bağlam |
| Ek MTS Klinik Algoritmalar | ~120 | Triaj kalitesi |

---
## 📊 Etki Metrikleri

| Metrik | Değer |
|--------|-------|
| Doktor zaman tasarrufu | 15–20 dk/hasta → ~4 dk ön-triaj |
| Hedef hasta grubu | 117M+ yıllık Türkiye acil başvurusu |
| Erişilebilirlik | Ses girişi (yaşlı + düşük okuryazarlık), WCAG 2.1 AA |
| Çevrimdışı çalışma | Köy kliniği: internet yok → Ollama + SQLite tam çalışır |
| API maliyeti | Donanım sonrası hasta başına **$0** |
| Dil desteği | Türkçe + İngilizce; Gemma 4 ile kolayca genişletilebilir |
| Hasta gizliliği | KVKK + HIPAA mimari — veri asla buluta gitmiyor |
| Klinik standart | FHIR R4 + MTS/CTAS + ICD-10 |
| Ölçeklenme | Kubernetes HPA ile yatay |

**Gerçek dünya senaryosu:** Türkiye'de günde 40 hasta gören bir ASM'de tek doktor. AnamnezAI bir dizüstü bilgisayarda çalışır, tüm hastalar doktor odasına girmeden önce 4 dakikalık ön-triaj yapar, 3 kritik (RED) vaka otomatik öne alır.

---

## 🔍 Yargıçlar İçin Doğrulama

```bash
# 1. Ollama'nın Gemma 4'ü sunduğunu doğrula
curl http://localhost:11434/api/tags
# → {"models": [{"name": "gemma4:e4b", ...}, {"name": "medgemma:4b", ...}, {"name": "gemma3:1b", ...}]}

# 2. AnamnezAI sağlık durumu (Sprint 14 genişletilmiş)
curl http://localhost:8000/health
# → {"status":"ok","version":"5.0.0","gemma_model":"gemma4:e4b",
#    "gemma_available":true,"medgemma_available":true,
#    "lite_model_available":true,"rag_chunks":810,...}

# 3. Tam mülakat döngüsü (göğüs ağrısı → RED)
curl -X POST http://localhost:8000/api/session/start \
  -H "Content-Type: application/json" \
  -d '{"patient_name":"Test Hasta","age":45,"gender":"Erkek","language":"tr"}'
# → {"session_id":"...","question":"Sizi bugün buraya getiren en önemli şikayetiniz nedir?","step":1,"total_steps":5}

# 4. EKG fotoğrafı yükle → MedGemma Vision
curl -X POST http://localhost:8000/api/analyze-image \
  -F "file=@ekg.jpg" -F "lang=tr"
# → {"findings":"...", "model_used":"medgemma:4b", "is_medgemma":true}

# 5. Doktor panelinde SSE kuyruk
curl http://localhost:8000/api/patients/stream
# → text/event-stream: {"type":"connected","data":{...}}

# 6. FHIR R4 JSON export
curl http://localhost:8000/api/session/{session_id}/fhir \
  -H "Authorization: Bearer {token}"
# → {"resourceType":"Bundle","type":"collection",...}
```

---

## 📅 Sprint Geçmişi

| Sprint | Alan | Tamamlanan Özellikler |
|--------|------|----------------------|
| S-1,2  | Backend | FastAPI + Ollama/Gemma 4, SYSTEM_PROMPT_TR, SSE streaming |
| S-3    | Frontend | Glassmorphism UI, animated SVG güven halkası, triaj renk kartları, Docker |
| S-4,5  | Frontend | Kiosk modu, QR sıra fişi, kiosk kilit/açma, Kaggle notebook |
| S-6    | Frontend | Mobil responsive, patient_dashboard, bottom sheet nav |
| S-7    | Frontend | clinical_review.html — FHIR R4 export, ICD-10 tablosu, doktor notu |
| S-8    | Backend | RAG: ChromaDB + paraphrase-multilingual-MiniLM + PDF ingest + dinamik bağlam |
| S-9    | Backend | Rate limiting (slowapi), session TTL, KVKK audit log, Kubernetes |
| S-10   | Backend | JWT auth 4 rol, Google OAuth2, klinik kodu, demo kullanıcılar |
| S-11   | Backend | Tier routing altyapısı (gemma4:e4b birincil) |
| S-12   | Frontend | Web Speech TTS+STT, Service Worker (offline PWA), Chart.js analitik |
| S-13   | Backend | MedGemma Vision — `/api/analyze-image`, image_findings, fallback |
| S-Plus | Frontend | Profil SPA — patient_dashboard içinde 4 section |
| **S-14** | **Backend+Frontend** | **Session timeout 30dk, `/health` genişletildi (lite_model_available), think blok buffer, toast+retry, "Gemma 4 düşünüyor..." animasyonu** |
| **S-15** | **Frontend** | **Model status bar (doctor.html), model badge her soru baloncuğunda, MedGemma vision rozetleri** |
| **S-16** | **Backend+Frontend** | **ICD-10 TR kodlama eklendi (RAG), Türkiye sağlık istatistikleri, genişletilmiş MTS algoritmaları, RAG kaynak rozeti (summary.html), alerji banner** |
| **S-17** | **Dokümantasyon** | **README sprint history, yargıç doğrulama güncelleştirildi, ekran görüntüsü yer tutucu** |
---
## 🙏 Teşekkürler

- **Google DeepMind** — Gemma 4 ve MedGemma modellerini açık kaynak yayımladıkları için
- **Ollama** — yerel LLM inference'ı bu kadar erişilebilir kıldıkları için
- **Kaggle** — Gemma 4 Good Hackathon organizasyonu
- **ChromaDB & Sentence Transformers** — ücretsiz, yerel gömülü vektör altyapısı

---
## 🔗 Bağlantılar

- **Kaggle Yarışması:** [gemma-4-good-hackathon](https://www.kaggle.com/competitions/gemma-4-good-hackathon)
- **GitHub:** [github.com/enis1998/AnamnezAI](https://github.com/enis1998/AnamnezAI)
- **Ollama — Gemma 4:** [ollama.com/library/gemma4](https://ollama.com/library/gemma4)
- **Ollama — MedGemma:** [ollama.com/library/medgemma](https://ollama.com/library/medgemma)
- **FHIR R4:** [hl7.org/fhir/R4](https://hl7.org/fhir/R4/)
- **Model Kartı:** [GEMMA4_MODEL_CARD.md](./GEMMA4_MODEL_CARD.md)
---
## 📜 Lisans
**CC-BY 4.0** — Kaynak belirtilmek şartıyla kullanım, değiştirme ve dağıtım serbesttir.
---
## ⚠️ Tıbbi Sorumluluk Reddi
AnamnezAI yalnızca **klinik karar destek aracıdır** — ön triaj amaçlıdır. Kesin tıbbi tanı koyamaz ve profesyonel tıbbi değerlendirmenin yerini alamaz. Tüm AI tarafından üretilen içerik, klinik karar verilmeden önce yetkili bir sağlık uzmanı tarafından değerlendirilmelidir.
[![Ollama](https://img.shields.io/badge/Runtime-Ollama-black)](https://ollama.com)
[![FHIR R4](https://img.shields.io/badge/Standard-FHIR%20R4-E86B1D)](https://hl7.org/fhir/)
[![License: CC-BY 4.0](https://img.shields.io/badge/License-CC--BY%204.0-green)](https://creativecommons.org/licenses/by/4.0/)
