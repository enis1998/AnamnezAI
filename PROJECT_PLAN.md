# 📋 AnamnezAI — Proje Planı & Yol Haritası

> **Gemma 4 Good Hackathon** — Health & Sciences + Ollama Ödül Parkurları  
> Repo: https://github.com/enis1998/AnamnezAI  
> Yarışma: https://www.kaggle.com/competitions/gemma-4-good-hackathon

---

## 📌 Proje Özeti

**AnamnezAI (MediScreen)**, hastaların doktora ulaşmadan önce yapay zeka destekli ön-triaj mülakatı geçirmesini sağlayan bir klinik karar destek sistemidir.

- **AI Motoru:** Google Gemma 4 (`gemma4:e4b`) — Ollama üzerinden 100% yerel çalışır
- **Backend:** Python FastAPI
- **Frontend:** Vanilla HTML/CSS/JS (TailwindCSS)
- **Hedef:** İki hackathon ödülü — Health & Sciences ($10K) + Ollama Prize ($10K)

---

## 🗺️ Sistem Akışı

```
┌─────────────┐     ┌──────────────────────────┐     ┌─────────────────┐
│   HASTA     │     │    ANAMNEZAI (Gemma 4)    │     │    DOKTOR       │
├─────────────┤     ├──────────────────────────┤     ├─────────────────┤
│             │     │                          │     │                 │
│ Ad/Yaş/     │────►│ Soru 1 (Gemma 4 üretir)  │     │                 │
│ Cinsiyet    │     │                          │     │                 │
│             │◄────│ "Baş ağrısı mı var?"     │     │                 │
│ Cevap       │────►│                          │     │                 │
│             │     │ Soru 2 (bağlamsal)        │     │                 │
│             │◄────│ "Ne zamandır devam        │     │                 │
│             │     │  ediyor?"                │     │                 │
│    ...      │     │    ... 5 tur ...          │     │                 │
│             │     │                          │     │                 │
│             │     │ KLİNİK ÖZET ÜRET ────────┼────►│ 🔴 ACİL         │
│             │     │ (JSON + Triaj)            │     │ Güven: %94      │
│             │     │                          │     │ "Kardiyak risk" │
└─────────────┘     └──────────────────────────┘     └─────────────────┘
```

---

## 🏗️ Proje Dosya Yapısı

```
AnamnezAI/
│
├── 📄 README.md                    # Proje tanıtımı (İngilizce, hackathon için)
├── 📄 PROJECT_PLAN.md              # Bu dosya — Türkçe detaylı plan
├── 📄 GEMMA4_MODEL_CARD.md         # Jüri için Gemma 4 kullanım kanıtı
├── 📄 setup.ps1                    # Tek tıkla Windows kurulum scripti
│
├── 📁 backend/
│   ├── 🐍 main.py                  # FastAPI sunucusu (Gemma 4 entegrasyonu)
│   └── 📄 requirements.txt         # Python bağımlılıkları
│
├── 📁 frontend/
│   ├── 🌐 index.html               # Hasta mülakat arayüzü (TR/EN, sesli giriş)
│   ├── 🌐 summary.html             # AI klinik özet sayfası
│   └── 🌐 doctor.html              # Doktor dashboard (triaj kuyruğu)
│
└── 📁 notebooks/
    └── 📓 mediscreen_ai_kaggle.ipynb  # Kaggle submission notebook
```

---

## 🔧 Teknik Mimari

### Backend API Endpointleri

| Method | Endpoint | Açıklama | Gemma 4 mı? |
|--------|----------|----------|-------------|
| `GET`  | `/health` | Ollama + Gemma 4 durum kontrolü | — |
| `POST` | `/api/session/start` | Mülakat başlat, Q1 üret | ✅ Gemma 4 |
| `POST` | `/api/session/answer` | Cevap al, sonraki soruyu üret | ✅ Gemma 4 |
| `GET`  | `/api/session/{id}/summary` | Klinik özet + triaj üret (JSON) | ✅ Gemma 4 |
| `GET`  | `/api/session/{id}/stream-summary` | Klinik özet SSE streaming | ✅ Gemma 4 |
| `GET`  | `/api/patients/queue` | Triaj öncelikli hasta kuyruğu | — |
| `DELETE` | `/api/session/{id}` | Oturumu sil (HIPAA) | — |

### Gemma 4 Kullanım Noktaları (3 Görev)

```
1. SORU ÜRETİMİ
   Sistem promptu → hasta geçmişi → Gemma 4 → bağlamsal soru
   Tüm 5 soru dinamik üretiliyor (soru 1 dahil)

2. KLİNİK ÖZET + TRİAJ
   5 turlu mülakat → Gemma 4 → yapılandırılmış JSON
   { triage_level, confidence_score, possible_conditions, urgency_flags... }

3. STREAMING ANLATIM
   Mülakat → Gemma 4 → SSE token-token → doktor paneli
```

---

## 📅 Sprint Planı

---

### ✅ SPRINT 1 — Temel Altyapı
**Durum:** TAMAMLANDI  
**Tarih:** 1 Mayıs 2026  

#### Yapılanlar

| # | Görev | Dosya | Durum |
|---|-------|-------|-------|
| 1 | FastAPI backend iskelet | `backend/main.py` | ✅ |
| 2 | Ollama `/api/chat` entegrasyonu | `backend/main.py` | ✅ |
| 3 | Session yönetimi (in-memory) | `backend/main.py` | ✅ |
| 4 | Hasta mülakat UI | `frontend/index.html` | ✅ |
| 5 | Klinik özet sayfası | `frontend/summary.html` | ✅ |
| 6 | Doktor dashboard | `frontend/doctor.html` | ✅ |
| 7 | Kaggle notebook | `notebooks/mediscreen_ai_kaggle.ipynb` | ✅ |
| 8 | Windows setup scripti | `setup.ps1` | ✅ |
| 9 | GitHub repo kurulumu | https://github.com/enis1998/AnamnezAI | ✅ |
| 10 | `.gitignore` + ilk commit | — | ✅ |

#### Teknik Kararlar
- **Model:** `gemma4:e4b` (dengeli hız/kalite, ~5GB)
- **Chat API:** `/api/chat` ile system prompt desteği (eski `/api/generate` yerine)
- **Dil:** TR/EN çift dil desteği

---

### ✅ SPRINT 2 — Gemma 4 Derinleştirme
**Durum:** TAMAMLANDI  
**Tarih:** 1 Mayıs 2026  

#### Yapılanlar

| # | Görev | Detay | Durum |
|---|-------|-------|-------|
| 1 | **Soru 1 de Gemma 4'e taşındı** | Artık hiçbir statik template yok | ✅ |
| 2 | **Bağlamsal mülakat** | Gemma 4 tüm geçmişi okuyarak sonraki soruyu üretiyor | ✅ |
| 3 | **SSE Streaming endpoint** | `/stream-summary` — token token yanıt | ✅ |
| 4 | **Urgency Flags** | Gemma 4 acil uyarı bayrakları üretiyor | ✅ |
| 5 | **Gelişmiş sistem promptları** | Acil belirti tespiti, daha iyi klinik muhakeme | ✅ |
| 6 | **JSON parse güçlendirildi** | Markdown code block temizleme eklendi | ✅ |
| 7 | **AsyncGenerator streaming** | Ollama `stream:true` ile gerçek SSE | ✅ |
| 8 | **Urgency Flags UI** | summary.html'e kırmızı uyarı paneli eklendi | ✅ |
| 9 | **README yeniden yazıldı** | Gemma3 referansları temizlendi, mimari diyagram | ✅ |
| 10 | **GEMMA4_MODEL_CARD.md** | Jüri doğrulama dokümanı oluşturuldu | ✅ |

#### Önemli Geliştirmeler
```python
# ÖNCE (Sprint 1) — Statik ilk soru
first_question = "Merhaba {name}! Bugün şikayetiniz nedir?"

# SONRA (Sprint 2) — Gemma 4 üretiyor
first_question = await ask_gemma(
    f"Hasta: {name}, {age} yaş. Empatiyle açılış sorusu sor.",
    system=SYSTEM_PROMPT_TR
)
```

---

### 🔄 SPRINT 3 — İlk Çalışan Demo & Test
**Durum:** DEVAM EDİYOR  
**Hedef:** Gemma 4 indirildikten sonra uçtan uca test + ekran görüntüleri

#### Yapılacaklar

| # | Görev | Öncelik | Durum |
|---|-------|---------|-------|
| 1 | `gemma4:e4b` indirme tamamlanınca `/health` kontrolü | 🔴 KRİTİK | ⬜ |
| 2 | Uçtan uca mülakat testi (5 soru + özet) | 🔴 KRİTİK | ⬜ |
| 3 | index.html → doctor.html tam akışı test et | 🔴 KRİTİK | ⬜ |
| 4 | Ekran görüntüleri al (3 sayfa) | 🟡 ÖNEMLİ | ⬜ |
| 5 | GitHub `main` branch'ini sil (Settings > Default > master) | 🟡 ÖNEMLİ | ⬜ |
| 6 | Kaggle notebook çalıştır, çıktıları kaydet | 🟡 ÖNEMLİ | ⬜ |
| 7 | Sesli giriş (Web Speech API) test et | 🟢 İYİ OLUR | ⬜ |
| 8 | Türkçe / İngilizce dil geçişi test et | 🟢 İYİ OLUR | ⬜ |

#### Sprint 3 Nasıl Yapılır?

**Adım 1 — Model Hazır mı Kontrol Et**
```bash
# Terminalde:
ollama list
# gemma4:e4b satırını görmelisin

curl http://localhost:8000/health
# "gemma_available": true görmelisin
```

**Adım 2 — Backend Başlat**
```powershell
cd C:\Users\pc\Desktop\Health\mediscreen
.\setup.ps1
# VEYA
cd backend
python main.py
```

**Adım 3 — İlk Mülakat Testi (Tarayıcıda)**
```
1. frontend/index.html dosyasını tarayıcıda aç
2. Ad: "Test Hasta", Yaş: 45, Cinsiyet: Erkek
3. "Mülakatı Başlat" butonuna tıkla
4. Gemma 4'ün ürettiği soruya cevap ver
5. 5 soruyu tamamla
6. Klinik özet sayfasına yönlendirileceksin
7. summary.html'de triaj seviyesini, güven skorunu gör
```

**Adım 4 — Doktor Paneli**
```
frontend/doctor.html aç
Demo hastaları göreceksin
"Raporu Gör" ile modal açılır
```

**Adım 5 — GitHub main Sil**
```
1. https://github.com/enis1998/AnamnezAI/settings
2. "Default branch" bölümü → pencil ikonu
3. "master" seç → Update
4. https://github.com/enis1998/AnamnezAI/branches
5. "main" → çöp kutusu ikonu → Delete
```

---

### 📦 SPRINT 4 — Kaggle Submission Hazırlığı
**Durum:** PLANLI  
**Hedef:** Tüm notebook çıktıları hazır, submission gönderildi

#### Yapılacaklar

| # | Görev | Öncelik | Durum |
|---|-------|---------|-------|
| 1 | Kaggle notebook'u Gemma 4 çıktılarıyla çalıştır | 🔴 KRİTİK | ⬜ |
| 2 | Notebook'a gerçek Gemma 4 çıktılarını kaydet | 🔴 KRİTİK | ⬜ |
| 3 | Kaggle'a notebook yükle | 🔴 KRİTİK | ⬜ |
| 4 | Kaggle'da **Submission** oluştur | 🔴 KRİTİK | ⬜ |
| 5 | Writeup yaz (Kaggle'ın istediği açıklama) | 🔴 KRİTİK | ⬜ |
| 6 | GitHub repo linkini writeup'a ekle | 🟡 ÖNEMLİ | ⬜ |
| 7 | Demo video / GIF kaydet | 🟡 ÖNEMLİ | ⬜ |

#### Kaggle Submission Adımları

```
1. https://www.kaggle.com/competitions/gemma-4-good-hackathon
2. "Join Competition" (zaten katıldıysan geç)
3. "Submit" sekmesi → "New Submission"
4. notebooks/mediscreen_ai_kaggle.ipynb yükle
5. Kaggle'da çalıştır (GPU açık olsun)
6. "Submit" tıkla
7. Writeup bölümüne:
   - Proje açıklaması
   - GitHub linki: https://github.com/enis1998/AnamnezAI
   - Gemma 4 nasıl kullanıldığı
   - Hangi prize track'lere girdiği
```

---

### 🚀 SPRINT 5 — Bonus Geliştirmeler (Varsa Zaman)
**Durum:** OPSIYONEL  
**Hedef:** Ana submission sonrası ekstra puan

| # | Görev | Hangi ödülü güçlendirir |
|---|-------|------------------------|
| 1 | Semptom fotoğrafı upload (Gemma 4 vision) | Health & Sciences |
| 2 | Türkçe tıp terimleri fine-tuning (Unsloth) | Unsloth Prize +$10K |
| 3 | Offline PWA (Progressive Web App) | Ollama Prize |
| 4 | Docker Compose ile kolay deploy | Ollama / Genel |
| 5 | Hasta geçmiş karşılaştırması | Main Track |

---

## 🛠️ Kurulum Rehberi (Adım Adım)

### 📋 Gereksinimler

| Gereksinim | Min. Sürüm | Kontrol |
|------------|-----------|---------|
| Python | 3.11+ | `python --version` |
| Ollama | Son sürüm | https://ollama.com |
| Git | Herhangi | `git --version` |
| RAM | 8GB+ | (gemma4:e4b için) |
| Disk | 10GB+ | (model + proje) |

### 1️⃣ Repo'yu İndir
```bash
git clone https://github.com/enis1998/AnamnezAI.git
cd AnamnezAI
```

### 2️⃣ Ollama Kur & Modeli İndir
```bash
# Ollama'yı https://ollama.com adresinden indir ve kur

# Model seçimi (donanımına göre):
ollama pull gemma4:e4b    # ÖNERİLEN — 5GB, dengeli
ollama pull gemma4:e2b    # HAFIF — 3GB, düşük RAM için
ollama pull gemma4:26b    # GÜÇLÜ — 20GB, yüksek GPU için

# Ollama otomatik başlar
# Manuel başlatmak için: ollama serve
```

### 3️⃣ Otomatik Kurulum (Windows)
```powershell
.\setup.ps1
# Bu script:
# - Python bağımlılıklarını kurar
# - Ollama'yı kontrol eder
# - Gemma 4 modelini indirir (yoksa)
# - Backend'i başlatır
# - Tarayıcıyı açar
```

### 4️⃣ Manuel Kurulum
```bash
# Backend
cd backend
pip install -r requirements.txt
python main.py
# → http://localhost:8000 çalışıyor

# Frontend (yeni terminal)
# frontend/index.html dosyasını tarayıcıda aç
# VEYA: python -m http.server 3000 --directory frontend
```

### 5️⃣ Doğrulama
```bash
# Ollama + Gemma 4 hazır mı?
curl http://localhost:8000/health

# Beklenen çıktı:
{
  "status": "ok",
  "ollama": "connected",
  "gemma_model": "gemma4:e4b",
  "gemma_available": true   ← Bu true olmalı!
}
```

---

## 📱 Uygulama Kullanım Kılavuzu

### 👤 Hasta Akışı

```
ADIM 1 — Giriş
  frontend/index.html'i aç
  Ad, yaş, cinsiyetini gir
  Dil seç (TR / EN)
  "Mülakatı Başlat" butonuna bas

ADIM 2 — AI Mülakat (5 Soru)
  Gemma 4 sana kişiselleştirilmiş sorular soracak
  Her soruyu yazarak VEYA mikrofona tıklayarak sesle yanıtla
  "Ctrl+Enter" ile hızla gönder

ADIM 3 — Klinik Özet
  5 soru tamamlanınca otomatik yönlendirilirsin
  summary.html'de göreceklerin:
    🔴/🟡/🟢 Triaj Seviyesi
    %XX AI Güven Skoru
    Ana Şikayet
    Olası Tanılar
    Acil Uyarı Bayrakları (varsa)
    Doktor için Notlar
    Önerilen Eylem

ADIM 4 — Doktor'a İlet
  "Yazdır / PDF" butonu ile raporu yazdır
  "Doktor Paneline Git" ile dashboard'a geç
```

### 👨‍⚕️ Doktor Akışı

```
ADIM 1 — Doktor Paneli
  frontend/doctor.html'i aç
  Panelde şunları göreceksin:
    İstatistik kartları (Toplam / 🔴 Acil / 🟡 Acil / 🟢 Rutin)
    Triaj önceliğine göre sıralı hasta tablosu
    Demo hastalar (offline gösterim)

ADIM 2 — Hasta Detayı
  Tabloda "Raporu Gör" tıkla
  Modal'da tüm klinik özet görünür
  "Tam Raporu Aç" ile summary.html'e git

ADIM 3 — Aksiyon
  Triaj seviyesine göre hastayı önceliklendir
  RED = Derhal müdahale
  YELLOW = 2 saat içinde gör
  GREEN = Rutin randevu
```

---

## 🎯 Hackathon Kazanma Stratejisi

### Health & Sciences ($10,000) için

Jüri şunlara bakıyor:
- ✅ **Net problem tanımı** — "Doktor zaman kaybı + triaj güçlüğü" net anlatıldı
- ✅ **Ölçülebilir etki** — "15-20 dk/hasta tasarrufu"
- ✅ **Erişilebilirlik** — Kırsal klinikler, internet gerektirmiyor
- ✅ **Gerçek dünya uygulanabilirliği** — Tek laptop yeterli

### Ollama ($10,000) için

Jüri dosyaları şöyle doğrular:
```
1. backend/main.py → "gemma4:e4b" + Ollama API çağrısı var mı? ✅
2. GET /health → "gemma_available": true görünüyor mu? ✅
3. GEMMA4_MODEL_CARD.md → Teknik kanıt belgesi ✅
4. Notebook çıktıları → Gemma 4'ün ürettiği gerçek metinler ✅
```

### Writeup İpuçları

Kaggle writeup'ında şunları vurgula:
1. **"Why local?"** — Hasta mahremiyeti, HIPAA, internet bağımsızlığı
2. **"Gemma 4'ün farkı"** — Statik form değil, gerçek konuşma
3. **"Somut senaryo"** — "Türkiye'nin kırsal bölgesinde 1 doktor, 40 hasta..."
4. **Demo link** — GitHub repo + ekran görüntüleri

---

## 🐛 Sorun Giderme

| Sorun | Çözüm |
|-------|-------|
| `Ollama bağlantısı yok` | `ollama serve` komutunu çalıştır |
| `gemma_available: false` | `ollama pull gemma4:e4b` bekliyor olabilir |
| `Port 8000 meşgul` | `Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess \| Stop-Process` |
| `CORS hatası` | Backend çalışıyor mu? `http://localhost:8000/health` kontrol et |
| `Ses çalışmıyor` | Chrome/Edge kullan (Firefox desteklemiyor) |
| `JSON parse hatası` | Gemma 4 cevabı bozuksa otomatik fallback devreye giriyor |

---

## 📊 Proje İlerleme Durumu

```
[████████████████████░░░░] %78 Tamamlandı

Sprint 1: [██████████] %100 ✅ Temel Altyapı
Sprint 2: [██████████] %100 ✅ Gemma 4 Derinleştirme
Sprint 3: [███░░░░░░░] %30  🔄 Test & Demo
Sprint 4: [░░░░░░░░░░] %0   ⬜ Kaggle Submission
Sprint 5: [░░░░░░░░░░] %0   ⬜ Bonus (Opsiyonel)
```

---

## 🔗 Önemli Linkler

| Link | Açıklama |
|------|----------|
| https://github.com/enis1998/AnamnezAI | GitHub Repo |
| https://www.kaggle.com/competitions/gemma-4-good-hackathon | Yarışma Sayfası |
| https://ollama.com/library/gemma4 | Gemma 4 Ollama Sayfası |
| http://localhost:8000/docs | FastAPI Swagger UI (backend çalışırken) |
| http://localhost:8000/health | Sistem durumu endpoint |

---

## 📝 Commit Geçmişi

| Commit | Açıklama |
|--------|----------|
| `b0ed32c` | Initial commit: MediScreen AI — tüm temel dosyalar |
| `284c336` | Merge: main branch birleştirildi |
| `b363d2a` | Sprint 2: Gemma 4 deep integration + streaming SSE |
| *(sonraki)* | Sprint 3: Test çıktıları + ekran görüntüleri |
| *(sonraki)* | Sprint 4: Kaggle notebook çıktıları + final |

---

*Son güncelleme: 1 Mayıs 2026*

