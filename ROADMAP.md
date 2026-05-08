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

## 🖥️ Sprint 5 — Hastane Kiosk Modu (2-3 hafta)

**Öncelik:** Orta — Kurumsal satış için gösterişli

- [ ] Büyük ekran (touch) dostu UI
- [ ] QR kod ile oturum başlat (telefonsuz hastalar)
- [ ] Büyük yazı tipi, yüksek kontrast, sade akış
- [ ] Personel yardımlı mod: hemşire/sekreter hastanın yerine doldurur
- [ ] Yazıcı entegrasyonu: sıra fişi bas
- [ ] Admin panelden kiosk kilit/açık yönetimi

---

## 🔗 Sprint 6 — HBYS & FHIR Entegrasyonu (4-6 hafta)

**Öncelik:** Orta-Yüksek — Google.org demo için şart

- [ ] FHIR R4 Patient resource oluşturma
- [ ] FHIR Observation (vital signs)
- [ ] FHIR Condition (olası tanılar)
- [ ] FHIR ClinicalImpression (triaj raporu)
- [ ] HBYS staging ortam bağlantısı (AYBU Yenimahalle)
- [ ] Otomatik hasta kaydı HBYS'ye yazma
- [ ] ICD-10 kod önerisi AI ile
- [ ] HL7 FHIR format PDF

---

## 🌍 Sprint 7 — Çok Dil & Erişilebilirlik (2-3 hafta)

**Öncelik:** Orta — Eşitlikçi erişim için

- [ ] Arapça dil desteği (Suriyeli göçmenler için kritik)
- [ ] Kürtçe temel destek
- [ ] Sesli soru/cevap (Text-to-Speech + STT)
- [ ] WCAG 2.1 AA uyumu tam kontrol
- [ ] Yüksek kontrast modu, ekran okuyucu desteği
- [ ] Renkten bağımsız triaj gösterimi

---

## 📊 Sprint 8 — Analitik Dashboard & Raporlama ✅ TAMAMLANDI (temel)

**Durum:** ✅ Temel analitik entegre

- [x] `GET /api/analytics` — triaj istatistikleri: toplam, renk dağılımı, cinsiyet, yaş grupları, ortalama güven
- [x] Günlük aktivite (son 7 gün)
- [x] En sık urgency flag listesi
- [x] doctor.html → sidebar "Analitik" butonu ile açılabilen panel
- [ ] Admin analitik sayfası (ayrı `analytics.html`)
- [ ] Semptom paterni analizi (grip dalgası tespiti vb.)
- [ ] Bölge/il bazlı dağılım haritası
- [ ] Anonimleştirilmiş CSV/JSON export
- [ ] BigQuery entegrasyon (Google Cloud)

---

## 🔒 Sprint 9 — Güvenlik & Uyumluluk (2-3 hafta)

**Öncelik:** Düşük-Orta (pilot öncesi zorunlu)

- [ ] KVKK uyumluluk audit checklist
- [ ] GDPR veri silme hakkı (`DELETE /user/{id}/all-data`)
- [ ] Veri anonimleştirme pipeline
- [ ] Penetrasyon testi bulguları
- [ ] Audit log (tüm veri erişimleri loglu)
- [ ] Rate limiting ve DDoS koruması
- [ ] Sağlık Bakanlığı güvenlik sertifikası süreci

---

## ☁️ Sprint 10 — Cloud & Ölçekleme (4-6 hafta)

**Öncelik:** Düşük (ulusal ölçek için)

- [ ] Docker Compose → Kubernetes (GKE)
- [ ] Vertex AI + Gemini API entegrasyonu (cloud fallback)
- [ ] Load balancer ve auto-scaling
- [ ] PostgreSQL'e geçiş (SQLite → production)
- [ ] Redis cache (oturum hızlandırma)
- [ ] Google Cloud Run deployment
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Monitoring: Cloud Monitoring + Alerting

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
7. ✅ Triaj override (PUT /api/session/{id}/triage)
8. ✅ Görüldü işareti (PUT /api/session/{id}/seen)
9. ✅ ICD-10 otomatik kod önerisi (Gemma 4)
10. ✅ Temel analitik dashboard (GET /api/analytics)
11. 🔄 RAG fine-tune: Gemma 4 medical LoRA (kaggle notebook)
12. ⏳ Hasta geçmişini mülakata entegre (kronik hastalık → prompt)
13. ⏳ PDF rapor e-posta gönderme
14. ⏳ Alerji uyarısı kırmızı bayrak
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

*Son güncelleme: Mayıs 2026 | AnamnezAI v4.0 | Gemma 4 Good Hackathon*

