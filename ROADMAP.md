# AnamnezAI — Gemma 4 Good Hackathon Sprint Planı

> **Proje:** AnamnezAI (AI-Powered Medical Pre-Triage Platform)  
> **Yarışma:** Gemma 4 Good Hackathon — Health & Sciences ($10K) + Ollama Prize ($10K)  
> **Model Yığını:** `gemma4:e4b` (birincil) + `medgemma:4b` (Vision — opsiyonel)  
> **Son Güncelleme:** Mayıs 2026

---

## 🎯 Yarışma Kazanma Kriterleri

| Kriter | Ağırlık | Mevcut Durum |
|--------|---------|-------------|
| Gemma 4 modeli kullanımı | Zorunlu | ✅ `gemma4:e4b` — triage + anamnez + rapor |
| Ollama ile yerel çalışma | Zorunlu (Ollama $10K) | ✅ Tamamen yerel, sıfır API maliyeti |
| Gerçek dünya etkisi | Yüksek | ✅ Türkiye kamu sağlığı — 117M yıllık başvuru |
| Teknik derinlik | Yüksek | ✅ RAG + FHIR R4 + SSE + Vision |
| Çalışan demo | Kritik | 🔧 S-14 önceliği |
| Kod kalitesi & dokümantasyon | Orta | 🔧 S-17 sonrası 9/10 |

---

## ✅ Tamamlanan Özellikler (Sprint 1–13 + ek)

| Gün | Sprint | Özellik | Durum |
|-----|--------|---------|-------|
| 0 | S-1,2 | FastAPI + Ollama/Gemma 4 altyapısı, SYSTEM_PROMPT_TR (MTS), SSE streaming | ✅ |
| 1 | S-3 | Glassmorphism UI, animated SVG güven halkası, triaj renk kartları, Docker | ✅ |
| 2 | S-4,5 | Kiosk modu, QR kod sıra fişi, kiosk kilit/açma, Kaggle notebook | ✅ |
| 3 | S-6 | Mobil responsive, patient_dashboard, bottom sheet nav | ✅ |
| 4 | S-7 | clinical_review.html — FHIR R4 export, ICD-10 tablosu, doktor notu | ✅ |
| 5 | S-8 | RAG: ChromaDB + all-MiniLM-L6-v2 + PDF ingest API + dinamik bağlam | ✅ |
| 6 | S-9 | Rate limiting (slowapi), session TTL, KVKK audit log, Kubernetes | ✅ |
| 7 | S-10 | JWT auth — 4 rol, Google OAuth2, klinik kodu, demo kullanıcılar | ✅ |
| 8 | S-11 | JWT auth — 4 rol, Google OAuth2, klinik kodu, demo kullanıcılar | ✅ |
| 9 | S-12 | Web Speech TTS+STT, Service Worker (offline PWA), Chart.js analitik | ✅ |
| 10 | S-13 | MedGemma Vision — `/api/analyze-image`, image_findings, fallback | ✅ |
| 11 | S-Plus | Profil SPA — patient_dashboard içinde 4 section (profile.html kaldırıldı) | ✅ |

---

## 🚀 Kalan Sprint Planı — Yarışma Öncesi

---

### 🔴 SPRINT 14 — Demo Güvenilirliği ✅ TAMAMLANDI

**Hedef:** Jürinin önünde sıfır hata, sorunsuz demo akışı

**Backend (`main.py`):**
- [x] `/health` endpoint'i model durumunu ayrıntılı döndürsün (model durumu, warmup bayrağı)
- [x] Ollama bağlantı kesilirse `503 Service Unavailable` + Türkçe hata mesajı
- [x] Session timeout: 30 dk boşta kalan oturumu otomatik kapat + temizle (`_session_cleanup_loop`)
- [x] Startup warmup: uygulama başlangıcında `_background_warmup` otomatik çağrılır
- [x] Think bloğu garantisi — buffer ile yarım think bloğu korunur (`think_buffer` implementasyonu)

**Frontend:**
- [x] Mülakat sırasında "Gemma 4 düşünüyor..." animasyonu — döngüsel klinik mesajlar
- [x] Network hatalarında toast notification + "Tekrar Dene" butonu (`showToastWithRetry`)
- [x] `summary.html` — "Doktor Paneline Git" butonu yalnızca doctor/admin rolünde görünüyor (önceden vardı + doğrulandı)
- [x] PDF yazdırma — html2canvas + jsPDF ile tüm tarayıcılarda çalışıyor

---

### 🟡 SPRINT 15 — Gemma 4 Farklılaştırıcılar ✅ TAMAMLANDI

**Hedef:** Jüriye Gemma 4'ün ne fark yarattığını somut, görsel olarak göster

**Thinking Mode Gösterimi:**
- [x] Mülakat sırasında "AI Düşünüyor..." animasyonu döngüsel klinik mesajlarla
- [x] `clinical_review.html`'de AI Düşünce Süreci açılır panel mevcut

**MedGemma Vision Vurgusu:**
- [x] `summary.html`'de "Görsel Bulgular" ayrı kart — `[MedGemma Vision]` · `[Gemma 4 Multimodal]` rozeti

**Model Durum Kartı (`doctor.html`):**
- [x] Sayfanın üstünde model durum bar'ı: `Gemma 4 e4b ✅ ACTIVE | MedGemma 4b (opsiyonel)`
- [x] `/health` endpoint'ten her 30 sn poll et

---

### 🟡 SPRINT 16 — RAG & Klinik Kalite ✅ TAMAMLANDI

**Hedef:** AI çıktılarının tıbbi kalitesini artır, kaynak şeffaflığı sağla

**RAG İyileştirme:**
- [x] ChromaDB'ye ek Türkçe tıbbi belgeler eklendi:
  - ICD-10 TR Kodlama Rehberi (kardiyoloji, solunum, GI, nöroloji, travma) 
  - Türkiye Acil Servis İstatistikleri 2024 (3 chunk)
  - Genişletilmiş MTS Algoritmaları (kardiyak, pediatrik, ağrı yönetimi)
- [x] RAG kaynak rozeti `summary.html`'de — `fetchRagInfo()` ile dinamik
- [x] Hasta alerji profili → `buildAllergyBanner()` ile mülakat ekranında gösterilir

**Klinik Rapor Kalitesi:**
- [x] Vital bulgular tablosunda normal aralık dışı değerler renk kodlu (zaten vardı: ateş ≥38.5°C → err rengi, SpO2 <95 → err)
- [x] Mülakat ekranında aktif alerji varsa kırmızı sabit banner (localStorage'dan alerji profili okunur)
- [x] `summary.html` — olası tanılar ICD-10 ara linki ile (`icd10data.com`)

---

### 🟢 SPRINT 17 — Demo Materyali & Sunum ✅ TAMAMLANDI

**Hedef:** Jüriyi ikna eden, eksiksiz dokümantasyon

**Ekran Görüntüleri (`frontend/screens/`):**
- [x] `frontend/screens/` klasörü oluşturuldu
- [x] `README.md` placeholder ve demo talimatları eklendi

**README Son Hali:**
- [x] Sprint history tablosu güncellendi (S-14 → S-17)
- [x] "Yargıçlar için doğrulama" bölümü — tüm 6 endpoint test komutu eklendi
- [x] Ekran görüntüsü dizini belgelenendi

---

### 🔵 SPRINT 18 — Bonus ✅ TAMAMLANDI

- [x] Admin panel: RAG belge yönetimi UI — belgeleri listele, metin ekle, PDF yükle, yerleşik bilgiyi yenile
- [x] Admin panel: Model test sekmesi — `gemma4:e4b` canlı prompt test UI
- [x] `/api/model/compare` endpoint — Gemma 4 ile tek model prompt test desteği

---

### 🔵 SPRINT 19 — Kalite Güvencesi & Son Dokunuşlar ✅ TAMAMLANDI

**Hedef:** Hackathon demosuna hazır, hatasız sistem

**Frontend Düzeltmeleri:**
- [x] `admin.html` — RAG sekmesi tab butonu eksikti, eklendi
- [x] `clinical_review.html` — AI Düşünce Süreci açılır paneli eklendi (Sprint 15 gereksinimi karşılandı)
- [x] `clinical_review.html` — ICD-10 endpoint uyumu (`icd10_suggestions` fallback) düzeltildi
- [x] `clinical_review.html` — FHIR export `blob()` → `json()` düzeltildi
- [x] `clinical_review.html` — Q&A transkriptinde model rozeti eklendi
- [x] `register.html` — hasta kaydı sonrası `patient_dashboard.html`'e yönlendirme düzeltildi
- [x] `sw.js` — `profile.html` (kaldırılmış) yerine `patient_dashboard.html`, `clinical_review.html`, `landing.html` eklendi
- [x] `summary.html` — "tilbbi" yazım hatası düzeltildi
- [x] `index.html` — Sabit `gemma4:e4b` etiketi her AI mesajında gösteriliyor

**Backend İyileştirmeleri:**
- [x] `clean_gemma_response()` — thinking blokları temizlenir, markdown fence kaldırılır
- [x] Offline/degraded mod — Ollama bağlantısı yoksa net hata mesajı

---

## 📊 Puan Tahmini

```
Teknik Derinlik     ████████████ 9/10  — RAG + FHIR + SSE + Vision
Gemma 4 Kullanımı   ████████████ 9/10  — e4b birincil + MedGemma (opsiyonel)
Ollama Uyumu        ████████████ 10/10 — Tamamen yerel, sıfır API maliyeti
Gerçek Etki         ████████████ 9/10  — Türkiye kamu sağlığı, 117M yıllık başvuru
Demo Kalitesi       █████████░░░ 8/10  — Sprint 14 sonrası → 9/10
Kod & Dokümantasyon ████████████ 9/10  — Sprint 17 sonrası
──────────────────────────────────────────────────────────────
TOPLAM              ████████████ ~9.0/10 → 🏆 Top 3 potansiyeli
```

---

## 🛠️ Sistem Mimarisi

```
┌─────────────────────────────────────────────────────────────────┐
│                       KULLANICI KATMANI                         │
│  ┌──────────┐  ┌───────────┐  ┌───────────────┐  ┌──────────┐  │
│  │   Web    │  │   Kiosk   │  │    Doktor     │  │  Admin   │  │
│  │ (Hasta)  │  │  TR / EN  │  │  SSE Kuyruk   │  │ Analitik │  │
│  │ PWA+ses  │  │ QR+dokunma│  │  Override     │  │ Chart.js │  │
│  └────┬─────┘  └─────┬─────┘  └───────┬───────┘  └────┬─────┘  │
│       └──────────────┴────────────────┴───────────────┘        │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP / SSE
┌────────────────────────────▼────────────────────────────────────┐
│                   FastAPI Backend v5.0                          │
│   JWT Auth │ Rate Limit (200/min) │ Audit Log │ SSE │ FHIR R4  │
└──────────┬───────────────┬──────────────────┬────────────────────┘
           │               │                  │
┌──────────▼────┐  ┌───────▼──────────┐  ┌───▼──────────────────┐
│    Ollama     │  │    ChromaDB      │  │       SQLite         │
│  gemma4:e4b   │  │  ~810 chunk      │  │  sessions            │
│  medgemma:4b  │  │  all-MiniLM-L6   │  │  summaries           │
│  (opsiyonel)  │  │  MTS / ICD-10    │  │  users + roles       │
│               │  │  top-k cosine    │  │  audit_log           │
└───────────────┘  └──────────────────┘  └──────────────────────┘
⚡ Tüm modeller YEREL (Ollama) — Sıfır API maliyeti
⚡ Hasta verisi asla buluta gitmiyor — KVKK uyumlu
```

---

## 🌍 Hackathon Sonrası Vizyon

| Dönem | Hedef |
|-------|-------|
| **Q3 2026** | Türkiye Sağlık Bakanlığı pilot görüşmeleri (2 ASM) |
| **Q3 2026** | Arapça + Kürtçe dil desteği — Gemma 4 çok dilli kapasitesi |
| **Q4 2026** | PostgreSQL'e geçiş — çok klinikte ortak veri |
| **Q4 2026** | Doktor mobil uygulaması (React Native) — SSE kuyruk telefonda |
| **Q1 2027** | FHIR R4 tam API sunucu — hastane HIS sistemleriyle entegrasyon |
| **Q1 2027** | Gemma 4 fine-tuning — Türkiye klinik veri setiyle ince ayar |
| **2027** | Orta Doğu / Orta Asya — düşük kaynaklı sağlık sistemi ortakları |

---

## ⚡ Hızlı Başlangıç

```bash
# 1. Modeli indir (~9.6 GB)
ollama pull gemma4:e4b
# Opsiyonel: Vision analizi için
# ollama pull medgemma:4b

# 2. Projeyi başlat
cd mediscreen
docker compose up --build -d

# 3. Tarayıcıda aç
# http://localhost:8000          → Hasta mülakatı
# http://localhost:8000/doctor.html   → Doktor paneli
# http://localhost:8000/kiosk.html    → Kiosk modu
```

## 👤 Demo Kullanıcıları

| Rol | E-posta | Şifre | Kapsam |
|-----|---------|-------|--------|
| Doktor | `doctor@anamnezai.tr` | `doctor123` | Triaj kuyruğu, klinik inceleme, override |
| Admin | `admin@anamnezai.tr` | `admin123` | Analitik, audit log, CSV export, RAG |
| Yeni Doktor | Herhangi e-posta | — | Klinik kodu: **DEMO2026** |
| Hasta | `register.html` ile kayıt | — | Mülakat, geçmiş, profil |

---

*AnamnezAI — Gemma 4 Good Hackathon 2026 | Health & Sciences ($10K) + Ollama Prize ($10K)*
