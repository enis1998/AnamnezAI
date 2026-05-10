# AnamnezAI — Demo Ekran Görüntüleri

Bu klasör AnamnezAI'ın demo ekran görüntülerini içerir.

## Beklenen Dosyalar

| Dosya | İçerik |
|-------|--------|
| `interview.png` | AI mülakat ekranı (göğüs ağrısı senaryosu, bağlamsal soru) |
| `triage_result.png` | RED triaj kartı (animated SVG, %94 güven, urgency flags) |
| `icd10.png` | ICD-10 otomatik kodlama tablosu |
| `vision_analysis.png` | MedGemma EKG analizi sonucu |
| `doctor_queue.png` | SSE canlı triaj kuyruğu (RED/YELLOW/GREEN) |
| `clinical_review.png` | Tam klinik inceleme + FHIR export butonu |
| `kiosk.png` | Kiosk dokunmatik modu (QR fişi görünür) |
| `admin_analytics.png` | Chart.js dashboard |
| `patient_dashboard.png` | Hasta genel bakış |
| `patient_profile.png` | Tıbbi profil SPA section |

## Demo Adımları (Ekran Görüntüsü Almak İçin)

```bash
# 1. Uygulamayı başlat
cd mediscreen
docker compose up --build -d

# 2. Tarayıcıda http://localhost:8000 aç
# 3. Göğüs ağrısı senaryosu ile mülakat yap
# 4. Her ekrandan ekran görüntüsü al
# 5. Bu klasöre kaydet
```

> Sprint 17: Gerçek ekran görüntüleri demo sırasında bu klasöre eklenecek.

