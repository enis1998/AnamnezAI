# AnamnezAI — Kapsamlı Proje Planı
## Gemma 4 Good Hackathon — Health & Sciences + Ollama Prize Tracks

> **Son Güncelleme:** Mayıs 2026  
> **GitHub:** https://github.com/enis1998/AnamnezAI  
> **Yarışma:** https://www.kaggle.com/competitions/gemma-4-good-hackathon

---

## 🎯 Proje Özeti

**AnamnezAI**, Gemma 4'ün yerel (offline) çalışma gücünü kullanarak hastane öncesi hasta anamnez toplama işlemini yapay zeka ile otomatize eden bir tıbbi ön-triaj sistemidir.

- **Hasta Tarafı:** 5 bağlamsal (contextual) soru ile semptom mülakatı  
- **Doktor Tarafı:** Triaj önceliği ile sıralanmış hasta kuyruğu + klinik özet  
- **Yapay Zeka:** Gemma 4 via Ollama — 100% yerel, veri sunucuya gitmiyor  
- **Triaj Standardı:** Manchester Triage System (MTS) + CTAS kriterleri

---

## 📐 Tasarım Sistemi (Stitch Design Docs'dan)

### "The Empathetic Guardian" — Yaratıcı Kuzey Yıldızı
Mevcut sağlık teknolojilerinin soğuk, klinik, bunaltıcı görünümünü reddeder.  
**Yüksek Kaliteli Editoryal** yaklaşım: Tıbbi otorite + Premium wellness markası estetiği.

### Renk Paleti (Material Design Tonal)
| Token | Hex | Kullanım |
|-------|-----|---------|
| `primary` | `#002f40` | Ana aksiyonlar, kritik metinler |
| `primary-container` | `#00475e` | Hero alanlar, nav |
| `secondary` | `#006a68` | Sağlık, ilerleme, başarı durumları |
| `secondary-container` | `#a0f1ed` | Semantik vurgular |
| `surface` | `#f8fafb` | Uygulama zemini |
| `error` | `#ba1a1a` | KIRMIZI triaj, kritik uyarı |
| `tertiary` (Orange) | `#e07b26` | SARI triaj, dikkat |

### Tipografi
- **Başlıklar:** Manrope (Geometric, editorial hissiyat)
- **Gövde/Etiket:** Inter (Erişilebilirlik, okunabilirlik)

### Tasarım Kuralları
- **"No-Line" Kuralı:** Sınırlar için çizgi değil renk değişimi kullan
- **"Glass & Gradient":** Gezinti çubuğu → glassmorphism (backdrop-blur: 20px)
- **Minimum dokunma hedefi:** 48x48dp (yaşlı kullanıcılar için)
- **Tek Görev Per Ekran** kuralı — Bilişsel yükü azalt

---

## 🏆 Hackathon Hedefleri

| Ödül Takımı | Değer | Gereksinim |
|-------------|-------|------------|
| Health & Sciences Impact | $10,000 | Sağlık alanında Gemma 4 kullanımı |
| Ollama Special Track | $10,000 | Gemma 4'ün Ollama üzerinden çalıştırılması |
| Genel ($50K) | $50,000 | En yenilikçi kullanım |

**Gemma 4 Kullanımının Kanıtlanması:**
- Her API isteği `/api/chat` Ollama endpointine gider
- Model adı `gemma4:e4b` — doğrudan Gemma 4 ailesi
- Tüm triaj kararları, soru üretimi ve klinik özetler Gemma 4 tarafından yapılır
- Kaggle notebook demo eklenir (bkz. Sprint 5)

---

## 🗂 Sprint Planı

---

### SPRINT 1 — Temel Altyapı (TAMAMLANDI)
- [x] FastAPI backend kurulumu
- [x] Ollama / Gemma 4 entegrasyonu (`/api/chat`)
- [x] Temel hasta mülakatı endpoint'leri
- [x] Statik frontend sunumu
- [x] GitHub repo kurulumu: https://github.com/enis1998/AnamnezAI
- [x] `requirements.txt` oluşturma

---

### SPRINT 2 — Gemma 4 Derinleştirme (TAMAMLANDI)
- [x] `SYSTEM_PROMPT_TR` / `SYSTEM_PROMPT_EN` — MTS kriterlerine göre
- [x] `TRIAGE_SYSTEM_TR` / `TRIAGE_SYSTEM_EN` — JSON triaj çıktısı
- [x] Streaming SSE endpoint (`/api/session/{id}/stream-summary`)
- [x] Urgency flags (acil uyarı bayrakları)
- [x] Dil desteği (TR/EN)

---

### SPRINT 3 — Tam UI Yeniden Tasarımı (TAMAMLANDI)
- [x] `frontend/index.html` — Chat-style hasta mülakatı
  - Glassmorphism nav bar
  - Ses girişi (Web Speech API)
  - Yazma göstergesi (typing indicator)
  - Bağlantı durumu pill'i
- [x] `frontend/summary.html` — Klinik rapor kartı
  - Animasyonlu SVG güven halkası
  - Triaj renk kodlaması (RED/YELLOW/GREEN)
  - Yazdırma desteği
- [x] `frontend/doctor.html` — Doktor paneli
  - Sidebar triaj kuyruğu
  - Slayt-in detay paneli
  - 30 saniyede bir otomatik yenileme
  - Demo hastalar (çevrimdışı görüntüleme)
- [x] `docker-compose.yml` + `Dockerfile`
- [x] `summaries` önbelleği — doktor kuyruğu tam veri döner

---

### SPRINT 4 — Kritik Bug Düzeltmeleri + Warmup (TAMAMLANDI)
**Commit: 592f2e6**

- [x] **KRİTİK BUG DÜZELTME:** `TRIAGE_SYSTEM_EN` multi-line string'i kapatılmamıştı
  - `TRIAGE_COLOR` dict ve `get_system_prompt()`/`get_triage_system()` fonksiyonları
    string içinde kalıyordu ve gerçekte tanımlanmamıştı
  - Sunucu `__pycache__/.pyc` sayesinde eski derlenmiş dosyadan çalışıyordu
  - String'e kapanış `"""` eklenerek düzeltildi
- [x] `ask_gemma()` timeout: 60s → 180s
- [x] Frontend `AbortSignal.timeout`: 65s → 190s
- [x] `POST /api/warmup` endpoint'i eklendi
  - Sayfa yüklenince arka planda sessizce Gemma 4'ü ısındırır
  - İlk mülakat başlatıldığında model zaten hazır olur
- [x] Preparing ekranı UX iyileştirmesi:
  - Geçen süre sayacı (0s, 1s, 2s...)
  - Animasyonlu ilerleme çubuğu (0%–95%)
  - 7 saniyede bir dönen ipucu mesajları (7 adet)
  - 100s sonra "Tekrar Dene" butonu görünür

---

### SPRINT 5 — Kaggle Notebook + Hackathon Sunumu (TAMAMLANDI)
**Hedef:** Yarışma için resmi Kaggle notebook hazırla

- [x] `notebooks/mediscreen_ai_kaggle.ipynb` yeniden yazıldı:
  - Bölüm 1: Problem tanımı — Türkiye'de acil servis yükü (117M başvuru, istatistikler)
  - Bölüm 2: AnamnezAI mimarisi diyagramı (ASCII art)
  - Bölüm 3: Ollama ile Gemma 4 bağlantısı + bağlantı testi hücresi
  - Bölüm 4: Simüle hasta mülakatı (3 senaryo: RED/YELLOW/GREEN)
  - Bölüm 5: Triaj sonucu görselleştirme (ASCII tablo + güven çubukları)
  - Bölüm 6: Performans metrikleri (latency, dakika başına kapasite)
  - Bölüm 7: Gerçek uygulama entegrasyonu + API kullanım örneği
  - CC-BY 4.0 lisans başlığı
  - Gemma 4 (gemma4:e4b) referansları düzeltildi (gemma3 → gemma4)
- [ ] Demo ekran görüntüleri pipeline'a ekle

---

### SPRINT 6 — Mobil UI (PLANLI)
**Hedef:** Stitch AI Interview Mobile ekranını uygula

- [ ] `frontend/index.html` → tamamen responsive
  - Stitch `ai_interview_mobile` referansı
  - Alt sabit cevap girişi (bottom sheet)
  - Büyük dokunma hedefleri (min 56px)
- [ ] Progress dots stepper (5 adım görsel göstergesi)
- [ ] `frontend/patient_home_mobile.html` — hasta ana ekranı

---

### SPRINT 7 — Clinical Review + Hasta Geçmişi (PLANLI)
**Hedef:** Doktor panelini stitch tasarımlarıyla tam eşleştir

- [ ] `frontend/clinical_review.html`
  - Stitch `clinical_review_web` referansı
  - Soru-cevap transkripti
  - Doktor notları ekleme alanı
- [ ] `frontend/clinical_summary.html`
  - Stitch `clinical_summary_web` referansı
  - PDF export (`window.print`)
- [ ] Backend: `PUT /api/session/{id}/doctor-notes`
- [ ] Son 20 tamamlanan mülakatın listesi

---

### SPRINT 8 — Yapay Zeka Fine-tuning (OPSİYONEL / DEĞERLENDİRME)

**Soru:** Unsloth prize track için fine-tuning gerekli mi?

#### Analiz

**Mevcut durum: Zero-shot Prompting**
- Gemma 4 system prompt + few-shot örneklerle kullanılıyor
- Tıbbi bilgi Gemma 4'ün pre-training'inden geliyor
- Hackathon için bu YETERLİ

**Fine-tuning Gereksinimleri (Unsloth ödülü için):**
| Gereksinim | Detay |
|-----------|-------|
| Veri seti | Anonimize hasta-doktor diyalog örnekleri |
| Hardware | Min 16GB VRAM (RTX 3090 / A100) |
| Araçlar | Unsloth + PEFT/LoRA + HuggingFace |
| Süre | 8-24 saat eğitim |
| Çıktı | GGUF formatında Ollama'ya import |

**Önerilen Veri Setleri:**
- `medical_dialog` (HuggingFace) — 260K hasta-doktor diyaloğu
- `MedQA-USMLE` — sorular + açıklamalar
- `PubMedQA` — biyomedikal soru cevaplama

**Karar:** Hackathon için fine-tuning YAPILMIYOR.  
Health & Sciences ($10K) + Ollama ($10K) ödülleri zero-shot ile yeterince destekleniyor.

---

### SPRINT 9 — Production Hazırlık (PLANLI)

- [ ] Rate limiting (slowapi)
- [ ] Session TTL (24 saat sonra otomatik temizle)
- [ ] Retry logic (3 deneme, exponential backoff)
- [ ] `/api/session/{id}` GET — session durumu sorgula
- [ ] KVKK uyumu: veri işleme bildirimi

---

## 📁 Proje Yapısı

```
mediscreen/
├── backend/
│   ├── main.py              <- FastAPI + Gemma 4 entegrasyonu (v2.0)
│   └── requirements.txt
├── frontend/
│   ├── index.html           <- Hasta mülakatı (chat UI) + Landing
│   ├── summary.html         <- Klinik rapor kartı (SVG confidence ring)
│   └── doctor.html          <- Doktor triaj paneli (sidebar + detail)
├── notebooks/
│   └── mediscreen_ai_kaggle.ipynb
├── Dockerfile
├── docker-compose.yml
├── setup.ps1
├── README.md
├── PROJECT_PLAN.md
└── GEMMA4_MODEL_CARD.md
```

---

## 🏃 Hızlı Başlangıç

```powershell
# 1. Ollama kur ve gemma4 indir
ollama pull gemma4:e4b

# 2. Ollama başlat (arka planda)
ollama serve

# 3. Bağımlılıkları kur
cd mediscreen/backend
pip install -r requirements.txt

# 4. Backend başlat
python main.py
# http://localhost:8000       <- Frontend
# http://localhost:8000/docs  <- Swagger UI
```

Docker ile:
```powershell
cd mediscreen
docker compose up --build
```

---

## 🔌 API Referansı

| Method | Endpoint | Açıklama |
|--------|---------|----------|
| GET | `/health` | Ollama + Gemma 4 bağlantı durumu |
| POST | `/api/warmup` | Gemma 4 modelini önceden ısındır |
| POST | `/api/session/start` | Yeni hasta mülakatı başlat |
| POST | `/api/session/answer` | Cevap gönder, sonraki soruyu al |
| GET | `/api/session/{id}/summary` | Klinik özet + triaj (JSON) |
| GET | `/api/session/{id}/stream-summary` | SSE streaming klinik özet |
| GET | `/api/patients/queue` | Triaj kuyruğu (doktor paneli) |
| DELETE | `/api/session/{id}` | Oturumu sil (KVKK) |

---

## 🧠 Gemma 4 Kullanım Akışı

```
HASTA                    GEMMA 4 (via Ollama)              DOKTOR
─────                   ──────────────────────             ──────
[Başlat]  -> /start  -> ilk soruyu üret (SYSTEM_PROMPT_TR)
[Cevap]   -> /answer -> bağlamsal soru üret (history aware)
... x5 tur ...
[Biter]   -> /summary-> MTS triaj JSON üret (TRIAGE_SYSTEM_TR)
          -> /stream  -> klinik özet SSE akışı
                                                   <- [Kuyruk Görür]
                                                   <- [Rapor Okur]
```

### Triaj Seviyeleri
| Seviye | Renk | Anlamı | Örnekler |
|--------|------|--------|--------|
| RED | `#ba1a1a` | Hayati risk | AMI, inme, anafilaksi, GCS<8 |
| YELLOW | `#e07b26` | Acil | Yüksek ateş, orta ağrı, HT krizi |
| GREEN | `#006a68` | Rutin | Hafif semptom, kronik takip, USYE |

---

## 📊 İncelenen Materyaller

### Stitch Tasarım Ekranları
| Ekran | Durum |
|-------|-------|
| patient_landing_web | Uygulandı (index.html landing) |
| ai_interview_web | Uygulandı (index.html interview) |
| doctor_dashboard_web | Uygulandı (doctor.html) |
| clinical_summary_web | Kısmi (summary.html) |
| ai_interview_mobile | Sprint 6 |
| clinical_review_web | Sprint 7 |
| patient_dashboard_web | Sprint 7 |
| patient_home_mobile | Sprint 6 |

### Design System (design.md)
- Renk paleti Tailwind config'e uygulandı
- Manrope + Inter tipografi uygulandı
- Glassmorphism nav uygulandı
- "No-Line" kuralı uygulandı
- Minimum dokunma hedefleri uygulandı

### PDF / DOCX Dokümanlar
- `Architecting_Intelligent_Healthcare.pdf` — Klinik akış referansı
- `The_AI_Health_Revolution.pdf` — Pitch destekleyici
- `AIPAP_Business_Plan_*.docx` — Uzun vadeli iş planı (post-hackathon)

---

## 📝 Önemli Notlar

- **Veri Gizliliği:** Tüm veriler bellekte (oturum süresi), diske yazılmaz
- **Lisans:** CC-BY 4.0 (yarışma kazanması durumunda zorunlu)
- **Submission:** 1 takım = 1 submission (dikkat!)
- **Fine-tuning:** Hackathon için gerekli değil — zero-shot yeterli
- **Hukuki:** California hukuku geçerli (yarışma kuralı)
