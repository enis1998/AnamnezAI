# AnamnezAI — MCP-ready Developer Layer

> **AnamnezAI is not a chatbot API; it is a local-first clinical intake engine that turns unstructured patient complaints into doctor-reviewable, safety-guarded, evidence-linked clinical summaries.**

Bu klasör, AnamnezAI klinik intake motoruna harici geliştirici erişimi için **MCP (Model Context Protocol) adapter katmanını** içerir.

---

## Ne Yapar?

```
WhatsApp / Telegram / Mobile App / Call Center / Kiosk
                    ↓
        AnamnezAI MCP-ready Developer Layer
                    ↓
     Existing FastAPI Clinical Intake Engine
                    ↓
  Local Gemma 4 + Local RAG + Safety Guardrails
                    ↓
     Doctor Review + PDF + FHIR + Evaluation
```

---

## Önemli: Gizlilik Modları

Bu sistem iki modda çalışabilir:

### 🔒 Strict Local Mode (Varsayılan)

Web/kiosk üzerinden kurumun kendi ağında çalışır.
Hasta verisi **hiçbir zaman** dış AI API'lerine gitmez.
Gemma 4 ve RAG tamamen yerel donanımda çalışır.
KVKK / GDPR tam uyumlu.

```bash
ALLOW_CLOUD_TRANSLATION=false  # Varsayılan — bulut çeviri kapalı
```

### 📡 Channel Adapter Mode (Opsiyonel)

WhatsApp, Telegram gibi dış kanallar `/api/channel/intake/message` üzerinden
MCP araçlarını kullanabilir.

> ⚠️ **Bu modda** ilgili mesajlaşma sağlayıcısının (Meta, Telegram vb.) veri politikaları geçerli olabilir.
> AI inferansı ve RAG yine tamamen yereldir — sadece mesajın kendisi dış platform üzerinden taşınır.
> Kanal adapter modu açıkça "opsiyonel" ve "channel demo" olarak etiketlenmiştir.

---

## Örnek Kanallar

- **WhatsApp-style patient intake** — `/api/channel/intake/message`
- **Hospital kiosks** — `kiosk.html` (mevcut, tam çalışıyor)
- **Call-center assistants** — kanal adapter üzerinden entegrasyon
- **Mobile health apps** — session API + kanal adapter
- **Telemedicine platforms** — FHIR R4 export + session API
- **Ambulance / field triage tools** — offline PWA + intake engine

---

## Dosyalar

| Dosya | Açıklama |
|-------|----------|
| `tools.py` | 10 MCP araç şeması — her araç için name, description, input_schema, örnek giriş/çıkış |
| `server.py` | MCP sunucu iskeleti — SDK varsa gerçek, yoksa fallback mode |
| `client_example.py` | Uçtan uca örnek akış — 3 senaryo (tam intake, WhatsApp-style, evaluasyon) |
| `README.md` | Bu dosya |

---

## MCP Araçları

| Araç | Endpoint | Açıklama |
|------|----------|----------|
| `anamnezai_start_intake` | `POST /api/session/start` | Yeni hasta mülakatı başlat |
| `anamnezai_submit_answer` | `POST /api/session/answer` | Cevap gönder, sonraki soru al |
| `anamnezai_next_question` | `GET /api/session/{id}/detail` | Oturum durumunu sorgula |
| `anamnezai_finalize_summary` | `GET /api/session/{id}/summary` | Klinik özet ve triaj üret |
| `anamnezai_get_clinical_review` | `GET /api/session/{id}/detail` | Tam klinik inceleme verisi |
| `anamnezai_send_to_doctor_queue` | `GET /api/patients/queue` | Doktor kuyruğunu kontrol et |
| `anamnezai_create_queue_ticket` | `POST /api/channel/intake/message` | Dış kanal mesajı gönder |
| `anamnezai_export_fhir` | `GET /api/session/{id}/fhir` | FHIR R4 Bundle export |
| `anamnezai_get_local_ai_proof` | `GET /api/offline-proof` | Yerel AI kanıtı |
| `anamnezai_get_evaluation_results` | `GET /api/evaluation` | AI kalite metrikleri |

---

## Kurulum

### Backend Çalıştırma (önce yapılmalı)

```bash
cd mediscreen/backend
pip install -r requirements.txt
python main.py
# Backend: http://localhost:8000
```

### Tool Şemalarını İnceleme

```bash
cd mcp_server
python tools.py
# Tüm araç şemalarını listeler
```

### MCP SDK ile Resmi Sunucu

```bash
pip install mcp httpx
python server.py
# MCP stdio sunucu başlatılır
```

### MCP SDK Olmadan Fallback

```bash
pip install httpx
python server.py --fallback
# Tool listesi + backend bağlantı testi
```

### Client Örneği

```bash
pip install httpx
python client_example.py            # Tüm senaryolar
python client_example.py intake     # Sadece intake akışı
python client_example.py channel    # WhatsApp-style demo
python client_example.py eval       # Değerlendirme
```

---

## Kanal Intake API

### `POST /api/channel/intake/message`

Dış kanaldan (WhatsApp, Telegram, mobil uygulama) mesaj gönderir.
Session başlatma + cevap gönderme + sonraki soru alma işlemlerini birleştirir.

**Request:**
```json
{
  "channel": "whatsapp_demo",
  "external_user_id": "demo-user-1",
  "message": "Göğsümde baskı var ve sol koluma vuruyor",
  "language": "tr",
  "session_id": null
}
```

**Response (devam eden mülakat):**
```json
{
  "session_id": "uuid-string",
  "reply": "Ağrınız ne zaman başladı ve 1-10 arasında kaç şiddetinde?",
  "triage_preview": null,
  "doctor_queue_created": false,
  "next_action": "ask_follow_up"
}
```

**Response (tamamlandı):**
```json
{
  "session_id": "uuid-string",
  "reply": "Bilgileriniz doktora iletildi. Bu durum acil olabilir; lütfen sağlık personeline haber verin.",
  "triage_preview": "RED",
  "doctor_queue_created": true,
  "next_action": "completed"
}
```

---

## Yerel AI Kanıtı

`GET /api/offline-proof` endpoint'i şunu döndürür:

```json
{
  "local_inference": true,
  "runtime": "Ollama",
  "external_ai_api": false,
  "remote_embeddings": false,
  "cloud_translation_enabled": false,
  "mcp_ready": true,
  "channel_adapters_optional": true,
  "patient_data_external_transfer": false
}
```

---

## Mimari Notlar

Bu MCP katmanı **hiçbir iş mantığı içermez**.
Sadece mevcut FastAPI backend endpoint'lerini çağıran bir adapter'dır.

- Tüm AI inferansı → Gemma 4 via Ollama (yerel)
- Tüm RAG → ChromaDB (yerel)
- Tüm triaj kararları → `main.py` + `safety.py` (yerel)
- MCP layer → sadece HTTP proxy

> ⚠️ **Güvenlik Notu:** AnamnezAI tanı koymaz, tedavi önermez.
> Sistemin tüm çıktıları doktor incelemesi gerektiren klinik karar destek araçlarıdır.
> "safety_guardrail_triggered" ve "doctor_review_required" alanlarına dikkat edin.

---

## Lisans

CC-BY 4.0 — AnamnezAI · Gemma 4 Good Hackathon 2026

