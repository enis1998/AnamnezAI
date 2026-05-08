# 🗺️ AnamnezAI — Tam Ürün Yol Haritası

> **Proje:** AI-PAP (AI-Powered Anamnesis Platform)  
> **Organizasyon:** GNDER — Geleceği Önemseyenler Derneği  
> **Ortaklar:** T.C. Sağlık Bakanlığı, AYBU Yenimahalle Hastanesi  
> **Hedef:** Google.org AI for Government Innovation ($1M–$3M) + Ulusal ölçek  
> **Hackathon:** Gemma 4 Good Hackathon — Health $10K + Ollama $10K

---

## 📊 Proje Vizyonu (Dokümanlardan)

AI-PAP, Türkiye'nin kamu sağlık sisteminde **hastane öncesi anamnez sürecini dijitalleştiren**, ajansal AI ile çalışan çok kanallı bir platformdur:

- **4 Erişim Kanalı:** Web · Mobil (iOS/Android) · Hastane Kiosk · Personel Destekli  
- **Entegrasyon:** HBYS (Hastane Bilgi Yönetim Sistemi) · FHIR HL7 · ICD-10  
- **Uyumluluk:** KVKK · GDPR · TLS 1.3 · AES-256  
- **Diller:** Türkçe · İngilizce · Arapça (genişletilebilir)  
- **Ekip:** 13 kişi (proje, teknik, klinik danışmanlar, veri bilimi, saha)

---

## 🏃 Sprint 0 — Şu An Tamamlananlar (v4.0)

| Özellik | Durum |
|---|---|
| FastAPI backend + Gemma 4 (Ollama) | ✅ |
| 5 turlu AI anamnez mülakatı | ✅ |
| MTS Triaj (RED/YELLOW/GREEN) + AI skoru | ✅ |
| RAG (ChromaDB + MiniLM) | ✅ |
| SSE Gerçek zamanlı kuyruk | ✅ |
| SQLite kalıcılık | ✅ |
| Multimodal Vision (yara/EKG/cilt) | ✅ |
| Vital bulgular formu | ✅ |
| PDF Export (jsPDF) | ✅ |
| SSE Streaming anlatı | ✅ |
| Sunucu başlangıcında warmup | ✅ |
| Think blok temizleme | ✅ |

---

## 🔐 Sprint 1 — Authentication & Rol Yönetimi ✅ TAMAMLANDI

**Süre:** 1 gün  
**Durum:** ✅ Tam entegre

### Backend
- [x] `users` tablosu: user_id, email, password_hash, role, name, specialty, clinic_code, created_at, is_active
- [x] JWT token tabanlı auth (python-jose + passlib)
- [x] `POST /auth/register` — hasta / doktor kaydı (doktora clinic_code kontrolü)
- [x] `POST /auth/login` — JWT döndürür (role bilgisiyle)
- [x] `GET /auth/me` — mevcut kullanıcı
- [x] `GET /auth/profile` / `PUT /auth/profile` — hasta profili
- [x] `GET /auth/patients` — doktor için hasta listesi
- [x] Route koruması: `get_current_user()`, `require_auth()`, `require_doctor()`, `require_admin()`
- [x] Oturumlar kullanıcıya bağlanır (`patient_id` alanı)
- [x] Demo doktor otomatik oluşturulur: `doctor@anamnezai.tr` / `doctor123`

### Frontend
- [x] `login.html` — hasta + doktor tabbed giriş ekranı
- [x] `register.html` — hasta / doktor kayıt ekranı  
- [x] `index.html` — kullanıcı pill (isim + çıkış), token ile API çağrısı, auth nav
- [x] `doctor.html` — doktor auth guard (hasta girmeye çalışırsa index'e, giriş yoksa login'e)
- [x] Token localStorage'da saklanır, Bearer header tüm API isteklerine eklenir

### Roller
```
HASTA    → Mülakat başlatır, kendi raporlarını görür
DOKTOR   → Triaj kuyruğunu yönetir (guard korumalı)
PERSONEL → Doktor gibi erişim
ADMİN    → Tüm haklar
```

**Doktor Demo:** `doctor@anamnezai.tr` / `doctor123`  
**Yeni Doktor Kaydı:** Klinik kodu `DEMO2026`

---

## 📋 Sprint 2 — Hasta Profili & Tıbbi Geçmiş ✅ TAMAMLANDI

**Süre:** 1 gün  
**Durum:** ✅ Tam entegre

- [x] `patient_profiles` tablosu: doğum yılı, cinsiyet, kan grubu, kronik hastalıklar, ilaçlar, alerjiler, notlar
- [x] `GET /api/patient/history` — hastanın tüm tamamlanmış oturumları ve triaj özetleri
- [x] `GET /auth/profile` / `PUT /auth/profile` — tıbbi profil alma/güncelleme
- [x] `profile.html` — hasta profil sayfası (tag tabanlı ilaç/kronik/alerji, ziyaret geçmişi)
- [x] Geçmiş ziyaretler listesi (triaj rengiyle, tarih/saat, şikayet özeti)
- [x] Profile istatistikleri: toplam/acil/rutin sayaç
- [x] index.html dropdown menü: "Profilim & Geçmiş" linki

---

## 🏥 Sprint 3 — Doktor İş Akışı Geliştirme ✅ TAMAMLANDI

**Süre:** 1 gün  
**Durum:** ✅ Tam entegre

- [x] `POST /api/session/{id}/note` — doktor notu ekleme (birden fazla not)
- [x] `PUT /api/session/{id}/triage` — triaj seviyesi override (doktor değiştirebilir, kayıt tutulur)
- [x] `PUT /api/session/{id}/seen` — "Görüldü" işareti (kuyruktan çıkarma)
- [x] `GET /api/session/{id}/icd10` — Gemma 4 ile otomatik ICD-10 kod önerisi (max 3 kod)
- [x] `DELETE /api/session/{id}` — artık doktor yetkisi gerektiriyor
- [x] doctor.html güncellendi: not ekleme formu, triaj override butonları, görüldü butonu, ICD-10 öneri
- [x] Raporlarda override/görüldü badge'leri görünür

---

## 📱 Sprint 4 — Mobil Uygulama (3-4 hafta)

**Öncelik:** Yüksek — Kırsal erişim için kritik

- [ ] React Native veya Flutter ile cross-platform uygulama
- [ ] Offline mode: 5 soruluk form önbelleğe alınsın, bağlantı gelince sync
- [ ] Sesli yönlendirme (yaşlı/düşük okuryazarlık)
- [ ] Push notification: "Sıranız geldi"
- [ ] Kamera ile cilt/yara fotoğrafı çekip Vision analiz
- [ ] QR kod ile kliniğe gelince oturumu sürdür

---

## 🖥️ Sprint 5 — Hastane Kiosk Modu ✅ TAMAMLANDI (temel)

**Durum:** ✅ Temel kiosk entegre

- [x] `kiosk.html` — dokunmatik ekran dostu tam ekran UI (koyu tema, büyük butonlar)
- [x] 5 ekranlı akış: Karşılama → Form → Mülakat → Tamamlandı → Giriş
- [x] `GET /api/kiosk/status` — anonim sistem durumu + kuyruk bilgisi
- [x] Inaktivite koruması: 3 dakika hareketsizlikte ana ekrana dön
- [x] Giriş yapmış hastalar için profil entegrasyonu
- [ ] QR kod oturum başlatma
- [ ] Yazıcı entegrasyonu (sıra fişi)
- [ ] Admin panelinden kiosk kilit/açık

---

## 🔗 Sprint 6 — HBYS & FHIR Entegrasyonu ✅ TAMAMLANDI (temel)

**Durum:** ✅ FHIR R4 export entegre

- [x] `GET /api/session/{id}/fhir` — FHIR R4 Bundle (Patient + ClinicalImpression + Observation)
- [x] Vital signs → FHIR Observation (LOINC kodlarıyla: KB, nabız, ateş, SpO2)
- [x] Olası tanılar → FHIR ClinicalImpression finding list
- [x] Triaj seviyesi + AI skoru → custom extension
- [x] doctor.html → "FHIR R4 Export" butonu (JSON indirme)
- [ ] HBYS staging ortam bağlantısı
- [ ] HL7 v2 mesajlaşma
- [ ] ICD-10 FHIR Condition resource

---

## 🌍 Sprint 7 — Çok Dil & Erişilebilirlik ✅ TAMAMLANDI

**Durum:** ✅ TR/EN/AR + WCAG 2.1 AA

- [x] **Türkçe / İngilizce / Arapça** dil desteği — kiosk.html + index.html tam i18n
- [x] RTL desteği — Arapça seçilince `dir="rtl"` + `lang="ar"` otomatik uygulanır
- [x] Dil tercihi `localStorage`'da kalıcı tutulur
- [x] `GET /api/kiosk/status` → `message_tr`, `message_en`, `message_ar` döndürür
- [x] **WCAG 2.1 AA uyumu** — aria-label, role="alert", aria-live, aria-pressed, aria-modal
- [x] **Yüksek kontrast modu** toggle butonu (kiosk.html, localStorage'da saklanır)
- [x] **Büyük yazı tipi** toggle (kiosk.html)
- [x] **Klavye navigasyonu** — :focus-visible, goTo() ilk fokuslanabilir elemana focus verir
- [x] **.sr-only** yardımcı teknoloji (ekran okuyucu) class'ı eklendi
- [x] Tüm semantik HTML — role="main", role="toolbar", role="region", role="figure"
- [x] index.html AR butonu + setLang() RTL/LTR toggle
- [ ] Kürtçe temel destek (v2 roadmap)
- [ ] Sesli soru/cevap STT+TTS (v2 roadmap)

---

## 📊 Sprint 8 — Analitik Dashboard & Raporlama ✅ TAMAMLANDI

**Durum:** ✅ Tam admin analitik sayfası + CSV export

- [x] `GET /api/analytics` — triaj istatistikleri: toplam, renk dağılımı, cinsiyet, yaş grupları, ortalama güven
- [x] Günlük aktivite (son 7 gün)
- [x] En sık urgency flag listesi
- [x] doctor.html → sidebar "Analitik" butonu ile açılabilen panel
- [x] **`analytics.html`** — ayrı admin analitik sayfası (Chart.js ile 4 grafik: donut, line, bar, pie)
- [x] KPI kartları: Toplam/Kırmızı/Sarı/Yeşil/Güven/Görüldü/Bekleyen
- [x] **`GET /api/analytics/export/csv`** — admin için anonimleştirilmiş CSV export (audit log kaydıyla)
- [x] 60 saniyede bir otomatik yenileme
- [ ] Semptom paterni analizi (grip dalgası tespiti) — v2
- [ ] Bölge/il bazlı dağılım haritası — v2
- [ ] BigQuery entegrasyon — v2

---

## 🔒 Sprint 9 — Güvenlik & Uyumluluk ✅ TAMAMLANDI

**Durum:** ✅ Rate limiting + audit log + KVKK/GDPR

- [x] `audit_log` tablosu: tüm kritik işlemler (session_start, fhir_export, gdpr_delete, doctor_actions) loglanıyor
- [x] `GET /api/audit-log` — admin için audit log listesi
- [x] `DELETE /api/user/{id}/all-data` — KVKK/GDPR veri silme hakkı
- [x] Tüm doktor işlemleri (not, override, görüldü) audit'e kaydediliyor
- [x] **Rate limiting — `slowapi`** (`requirements.txt`'e eklendi, app.state.limiter kurulumu)
- [x] Kiosk lock/unlock işlemleri audit loguna kaydediliyor
- [x] CSV export işlemleri audit loguna kaydediliyor
- [ ] Penetrasyon testi bulguları — v2
- [ ] Sağlık Bakanlığı güvenlik sertifikası — v2

---

## ☁️ Sprint 10 — Cloud & Ölçekleme ✅ TAMAMLANDI

**Durum:** ✅ CI/CD pipeline + Docker + Kubernetes hazır

- [x] **`.github/workflows/ci.yml`** — GitHub Actions pipeline:
  - Lint (ruff) + pytest + coverage
  - Frontend HTML + PWA asset validation
  - Docker build (Buildx + cache)
  - Cloud Run auto-deploy (main branch → production)
- [x] `Dockerfile` — mevcut, production hazır
- [x] `docker-compose.yml` — mevcut, local dev
- [x] **`kubernetes/deployment.yaml`** — tam Kubernetes manifests:
  - Namespace, ConfigMap, Secret
  - Backend Deployment (2 replicas, rolling update)
  - Ollama Deployment
  - Services (ClusterIP)
  - Ingress (HTTPS + TLS + cert-manager)
  - HorizontalPodAutoscaler (2–10 replicas, CPU/Memory)
  - PersistentVolumeClaim (5Gi SQLite storage)
- [ ] Vertex AI + Gemini API cloud fallback
- [ ] PostgreSQL geçişi (SQLite → production)
- [ ] Redis cache
- [ ] Cloud Monitoring + Alerting

---

## 🎯 Hackathon Öncelik Listesi (Gemma 4 Good Hackathon)

> Bu proje Sağlık Bakanlığı değil, **Gemma 4 Good Hackathon** için geliştirilmektedir.  
> Tamamen yerel (Ollama) çalışır, hasta verisi sunucuya gitmez.

```
1. ✅ Gemma 4 think bloğu fix
2. ✅ Authentication (doktor/hasta login + JWT)
3. ✅ login.html + register.html
4. ✅ Doctor guard + kullanıcı nav
5. ✅ Hasta profil sayfası (profile.html) — geçmiş raporlar, tıbbi geçmiş
6. ✅ Doktor notu ekleme (POST /api/session/{id}/note)
7. ✅ Triaj override + Görüldü işareti + ICD-10 öneri
8. ✅ Temel analitik dashboard
9. ✅ Hasta profili → mülakat entegrasyonu (kronik/ilaç/alerji → AI prompt)
10. ✅ Alerji uyarısı kırmızı bayrak (önce listeye, doktor panelinde badge)
11. ✅ Kiosk modu (kiosk.html — dokunmatik ekran UI)
12. ✅ FHIR R4 export (Bundle: Patient + ClinicalImpression + Observation)
13. ✅ Audit log (KVKK/GDPR uyumu)
14. ✅ GDPR veri silme hakkı (DELETE /api/user/{id}/all-data)
15. ✅ commit.py ile UTF-8 encoding düzeltmesi
16. 🔄 RAG fine-tune: Gemma 4 medical LoRA (kaggle notebook)
```

### 🤖 Fine-Tune & RAG Planı (Hackathon için kritik)

```
MEVCUT:
  RAG: ChromaDB + MiniLM — tıbbi bilgi tabanı (✅)
  Model: Gemma 4 e4b via Ollama (✅)

PLANLANAN:
  LoRA Fine-Tune:
    - Dataset: Turkish medical QA + symptom-triage pairs
    - Base model: google/gemma-4-it (Kaggle notebook)
    - Adapter: LoRA r=16, alpha=32
    - Hedef: Türkçe tıbbi terminoloji + MTS triaj kararları
    
  RAG Güçlendirme:
    - PDF ingest: Acil Tıp kılavuzu, MTS, CTAS
    - Embed model: paraphrase-multilingual-MiniLM-L12-v2
    - Chunk size: 512 token, overlap: 64
    - Collection: medical_tr + medical_en
```

---

## 📐 Teknik Mimari (Hedef)

```
┌─────────────────────────────────────────────────────────────────┐
│                    AnamnezAI — Tam Mimari                        │
│                                                                   │
│  KULLANICI KATMANI                                               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │  Web     │ │  Mobil   │ │  Kiosk   │ │ Personel Destekli│   │
│  │ (Mevcut) │ │   App    │ │  Modu    │ │      Mod         │   │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────────┬─────────┘   │
│       └────────────┴────────────┴─────────────────┘             │
│                              │                                    │
│  API KATMANI                 ▼                                   │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │  FastAPI v4.0   │  JWT Auth  │  Rate Limit  │  Audit Log │   │
│  └───────────────────────────────────────────────────────────┘   │
│                              │                                    │
│  AI KATMANI                  ▼                                   │
│  ┌───────────────┐  ┌───────────────────┐  ┌─────────────────┐  │
│  │  Gemma 4      │  │  RAG (ChromaDB)   │  │  Vision API     │  │
│  │  (Ollama)     │  │  MiniLM Embeddings│  │  Multimodal     │  │
│  │  Lokal        │  │  12+ Tıbbi Chunk  │  │  Görüntü Analiz │  │
│  └───────────────┘  └───────────────────┘  └─────────────────┘  │
│                              │                                    │
│  VERİ KATMANI                ▼                                   │
│  ┌──────────────┐  ┌──────────────────┐  ┌────────────────────┐ │
│  │  SQLite      │  │  FHIR R4 Store   │  │  Analytics (anon)  │ │
│  │  (Mevcut)    │  │  (Sprint 6)      │  │  (Sprint 8)        │ │
│  └──────────────┘  └──────────────────┘  └────────────────────┘ │
│                              │                                    │
│  ENTEGRASYON                 ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │  HBYS API  │  ICD-10  │  KVKK/GDPR  │  HL7 FHIR         │    │
│  └──────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 👥 Kullanıcı Yolculukları

### Hasta Yolculuğu
```
Kayıt/Giriş → Profil Doldur → Mülakat Başlat → 
Vital Gir → 5 Soru Cevapla → Görüntü Yükle (opsiyonel) → 
Triaj Raporu Gör → PDF İndir → Doktora Git
```

### Doktor Yolculuğu
```
Giriş → Triaj Kuyruğunu Gör (SSE canlı) → 
Hasta Detayına Tıkla → Vision Bulguları + Vital Gör → 
Not Ekle → Triaj Onayla/Değiştir → "Görüldü" İşaretle
```

### Sağlık Personeli Yolculuğu
```
Giriş (Personel rolü) → Yeni Hasta Başlat → 
Hasta Adına Formu Doldur → Sesli Yönlendir → 
Raporu Doktora İlet
```

---

## 📈 Başarı Metrikleri

| Metrik | Hedef (6 ay) | Hedef (36 ay) |
|---|---|---|
| Günlük aktif kullanıcı | 100 | 50,000 |
| İşlenen anamnez | 500/ay | 100,000/ay |
| Triaj doğruluk oranı | %85 | %92 |
| Doktor başına tasarruf | 15-20 dk/hasta | 20-25 dk/hasta |
| Desteklenen hastane | 1 (pilot) | 50+ |
| Dil desteği | 2 (TR+EN) | 5+ |

---

## 🏆 Yarışma Durumu

| Özellik | Hackathon Değeri |
|---|---|
| Gemma 4 lokal (Ollama) | ✅ Ollama $10K qualification |
| Multimodal Vision | ✅ Gemma 4 differentiator |
| SSE Streaming | ✅ Real-time demo |
| Türkiye sağlık sistemi | ✅ Health $10K qualification |
| Authentication (JWT) | ✅ Professional full-product |
| Fine-tune LoRA plan | 🔄 AI depth bonus |
| FHIR formatı | ⏳ Enterprise bonus |

---

*Son güncelleme: Mayıs 2026 | AnamnezAI v5.0 | Gemma 4 Good Hackathon*
*Sprint 4 (PWA) ✅ | Sprint 7 (i18n TR/EN/AR + WCAG) ✅ | Sprint 8 (Analytics) ✅ | Sprint 9 (Rate Limiting) ✅ | Sprint 10 (CI/CD) ✅*

