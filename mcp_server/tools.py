"""
AnamnezAI — MCP-ready Clinical Intake Tool Schemas
====================================================
Bu modül, AnamnezAI klinik intake motorunun MCP (Model Context Protocol) araçlarını tanımlar.
Her araç, mevcut FastAPI arka ucuna bir adapter olarak çalışır.

Mimari:
  MCP Tool → FastAPI endpoint → AnamnezAI clinical pipeline → Local Gemma 4

ÖNEMLI: Bu katman hiçbir iş mantığını kopyalamaz.
Tüm AI inferansı, RAG, ve triaj kararları mevcut backend'de çalışır.
"""

from typing import Optional, Any

# ─────────────────────────────────────────────────────────────────────────────
#  Tool Schemas — her araç için name, description, input_schema, örnek giriş
#  ve beklenen çıkış tanımlanmıştır.
# ─────────────────────────────────────────────────────────────────────────────

ANAMNEZAI_TOOLS: list[dict] = [

    # ────────────────────────────────────────────────────────────────────────
    # 1. Yeni hasta mülakatı başlat
    # ────────────────────────────────────────────────────────────────────────
    {
        "name": "anamnezai_start_intake",
        "description": (
            "Yeni bir hasta anamnez mülakatı başlatır. "
            "İlk soruyu döndürür ve session_id üretir. "
            "Bu araç hastanın adı, yaşı, cinsiyeti ve tercih ettiği dil ile çağrılmalıdır."
        ),
        "endpoint": "POST /api/session/start",
        "input_schema": {
            "type": "object",
            "required": ["patient_name", "age", "gender"],
            "properties": {
                "patient_name": {
                    "type": "string",
                    "description": "Hastanın adı soyadı (veya takma ad / 'Anonim')"
                },
                "age": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 130,
                    "description": "Hastanın yaşı"
                },
                "gender": {
                    "type": "string",
                    "enum": ["Erkek", "Kadın", "Male", "Female", "Other"],
                    "description": "Cinsiyet"
                },
                "language": {
                    "type": "string",
                    "enum": ["tr", "en", "ar"],
                    "default": "tr",
                    "description": "Mülakat dili: tr=Türkçe, en=English, ar=العربية"
                },
                "vitals": {
                    "type": "object",
                    "description": "İsteğe bağlı vital bulgular",
                    "properties": {
                        "blood_pressure": {"type": "string", "example": "120/80 mmHg"},
                        "pulse": {"type": "integer", "description": "bpm"},
                        "temperature": {"type": "number", "description": "°C"},
                        "spo2": {"type": "integer", "description": "%"},
                        "respiratory_rate": {"type": "integer", "description": "/dk"}
                    }
                }
            }
        },
        "example_input": {
            "patient_name": "Ahmet Yılmaz",
            "age": 45,
            "gender": "Erkek",
            "language": "tr"
        },
        "expected_output": {
            "session_id": "uuid-string",
            "question": "Merhaba Ahmet! 👋 Bugün sizi buraya getiren şikayetiniz nedir?",
            "step": 1,
            "total_steps": 5
        }
    },

    # ────────────────────────────────────────────────────────────────────────
    # 2. Hasta cevabını gönder — sonraki soru al
    # ────────────────────────────────────────────────────────────────────────
    {
        "name": "anamnezai_submit_answer",
        "description": (
            "Mevcut mülakat sorusuna hastanın cevabını gönderir. "
            "Gemma 4, bir önceki cevabı analiz ederek sonraki klinik soruyu üretir. "
            "Tüm adımlar tamamlandığında soru '__COMPLETED__' olarak döner."
        ),
        "endpoint": "POST /api/session/answer",
        "input_schema": {
            "type": "object",
            "required": ["session_id", "answer"],
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "anamnezai_start_intake'ten dönen session_id"
                },
                "answer": {
                    "type": "string",
                    "description": "Hastanın mevcut soruya verdiği cevap"
                }
            }
        },
        "example_input": {
            "session_id": "uuid-string",
            "answer": "Göğsümde baskı var ve sol koluma vuruyor"
        },
        "expected_output": {
            "session_id": "uuid-string",
            "question": "Bu baskı hissi ne zamandır var ve 1-10 arasında kaç şiddetinde?",
            "step": 2,
            "total_steps": 7
        }
    },

    # ────────────────────────────────────────────────────────────────────────
    # 3. Mevcut soru durumunu kontrol et
    # ────────────────────────────────────────────────────────────────────────
    {
        "name": "anamnezai_next_question",
        "description": (
            "Oturumun mevcut durumunu (adım, soru, tamamlanma) sorgular. "
            "Bağlantı kopması veya durum senkronizasyonu için kullanılır."
        ),
        "endpoint": "GET /api/session/{session_id}/detail (doctor auth) or session state",
        "input_schema": {
            "type": "object",
            "required": ["session_id"],
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Sorgulanacak oturum ID'si"
                }
            }
        },
        "example_input": {
            "session_id": "uuid-string"
        },
        "expected_output": {
            "session_id": "uuid-string",
            "current_step": 3,
            "total_steps": 7,
            "completed": False,
            "last_question": "Bu baskı hissinin sol kola yayılımı ne kadar süredir var?",
            "language": "tr"
        }
    },

    # ────────────────────────────────────────────────────────────────────────
    # 4. Klinik özet oluştur (triaj sonucu)
    # ────────────────────────────────────────────────────────────────────────
    {
        "name": "anamnezai_finalize_summary",
        "description": (
            "Tamamlanmış mülakatı analiz ederek Gemma 4 ile klinik özet ve "
            "Manchester Triage System seviyesi üretir: RED / YELLOW / GREEN. "
            "Safety Guardrail Layer, Clinical Completeness Score, Evidence Map dahildir. "
            "Mülakat tamamlanmadan çağrılırsa 400 hatası döner."
        ),
        "endpoint": "GET /api/session/{session_id}/summary",
        "input_schema": {
            "type": "object",
            "required": ["session_id"],
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Tamamlanmış mülakat oturum ID'si"
                }
            }
        },
        "example_input": {
            "session_id": "uuid-string"
        },
        "expected_output": {
            "session_id": "uuid-string",
            "triage_level": "RED",
            "confidence_score": 98,
            "chief_complaint": "Göğüs baskısı, sol kola yayılım, terleme",
            "symptoms_summary": "45 yaş erkek hasta akut MI bulguları...",
            "possible_conditions": ["AMI/STEMI", "Kararsız angina"],
            "urgency_flags": ["Kardiyak risk faktörleri mevcut"],
            "recommended_action": "Acil kardiyak ekip uyarısı gereklidir",
            "clinical_completeness_score": 82,
            "evidence_map": [],
            "safety_guardrail_triggered": True,
            "doctor_review_required": True
        }
    },

    # ────────────────────────────────────────────────────────────────────────
    # 5. Doktor klinik inceleme paneline veri al
    # ────────────────────────────────────────────────────────────────────────
    {
        "name": "anamnezai_get_clinical_review",
        "description": (
            "Oturumun tam klinik inceleme verilerini döndürür: "
            "mülakat transkripti, evidence map, completeness score, "
            "AI execution log ve FHIR önizlemesi dahil. "
            "Doktor paneli entegrasyonu için kullanılır. (Doktor yetkisi gerekir.)"
        ),
        "endpoint": "GET /api/session/{session_id}/detail",
        "input_schema": {
            "type": "object",
            "required": ["session_id", "doctor_token"],
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Oturum ID'si"
                },
                "doctor_token": {
                    "type": "string",
                    "description": "Doktor JWT erişim token'ı"
                }
            }
        },
        "example_input": {
            "session_id": "uuid-string",
            "doctor_token": "Bearer eyJ..."
        },
        "expected_output": {
            "session_id": "uuid-string",
            "session": {"patient_name": "...", "qa_history": []},
            "summary": {"triage_level": "RED", "evidence_map": []}
        }
    },

    # ────────────────────────────────────────────────────────────────────────
    # 6. Doktor kuyruğuna gönder
    # ────────────────────────────────────────────────────────────────────────
    {
        "name": "anamnezai_send_to_doctor_queue",
        "description": (
            "Tamamlanmış oturumu doktor triaj kuyruğuna bildirir. "
            "Oturum tamamlandığında otomatik olarak kuyruğa eklenir; "
            "bu araç bir SSE (Server-Sent Events) tetikleyicidir — "
            "doktor paneli anlık güncelleme alır."
        ),
        "endpoint": "GET /api/patients/queue (doctor panel SSE)",
        "input_schema": {
            "type": "object",
            "required": ["session_id"],
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Kuyruğa bildirilecek tamamlanmış oturum ID'si"
                }
            }
        },
        "example_input": {
            "session_id": "uuid-string"
        },
        "expected_output": {
            "status": "queued",
            "session_id": "uuid-string",
            "triage_level": "RED",
            "queue_position": 1
        }
    },

    # ────────────────────────────────────────────────────────────────────────
    # 7. Kanal entegrasyonu — intake mesajı gönder (WhatsApp / Telegram / vs.)
    # ────────────────────────────────────────────────────────────────────────
    {
        "name": "anamnezai_create_queue_ticket",
        "description": (
            "Dış kanal (WhatsApp, Telegram, mobil uygulama) üzerinden tek mesajla "
            "hasta intake mesajı gönderir. Session başlatma + cevap gönderme + "
            "bir sonraki soru alma işlemlerini tek çağrıda birleştirir. "
            "Oturum tamamlandığında doktor kuyruğuna otomatik düşer."
        ),
        "endpoint": "POST /api/channel/intake/message",
        "input_schema": {
            "type": "object",
            "required": ["message", "external_user_id"],
            "properties": {
                "channel": {
                    "type": "string",
                    "enum": ["whatsapp_demo", "telegram_demo", "mobile_app", "call_center", "custom"],
                    "default": "custom",
                    "description": "Kaynak kanal türü"
                },
                "external_user_id": {
                    "type": "string",
                    "description": "Dış kanaldaki kullanıcı ID'si (WhatsApp numarası, Telegram ID vb.)"
                },
                "message": {
                    "type": "string",
                    "description": "Hastanın yazdığı mesaj"
                },
                "language": {
                    "type": "string",
                    "enum": ["tr", "en", "ar"],
                    "default": "tr"
                },
                "session_id": {
                    "type": "string",
                    "nullable": True,
                    "description": "Devam eden oturum ID'si. null ise yeni oturum başlatılır."
                }
            }
        },
        "example_input": {
            "channel": "whatsapp_demo",
            "external_user_id": "demo-user-1",
            "message": "Göğsümde baskı var ve sol koluma vuruyor",
            "language": "tr",
            "session_id": None
        },
        "expected_output_ongoing": {
            "session_id": "uuid-string",
            "reply": "Ağrınız ne zaman başladı ve 1-10 arasında kaç şiddetinde?",
            "triage_preview": None,
            "doctor_queue_created": False,
            "next_action": "ask_follow_up"
        },
        "expected_output_completed": {
            "session_id": "uuid-string",
            "reply": "Bilgileriniz doktora iletildi. Bu durum acil olabilir; lütfen sağlık personeline haber verin.",
            "triage_preview": "RED",
            "doctor_queue_created": True,
            "next_action": "completed"
        }
    },

    # ────────────────────────────────────────────────────────────────────────
    # 8. FHIR R4 export
    # ────────────────────────────────────────────────────────────────────────
    {
        "name": "anamnezai_export_fhir",
        "description": (
            "Tamamlanmış klinik özeti FHIR R4 Bundle olarak dışa aktarır. "
            "Bundle şunları içerir: Patient + ClinicalImpression + Observation (vital signs). "
            "Hastane HIS entegrasyonu ve interoperabilite için kullanılır. "
            "(Doktor yetkisi gerekir.)"
        ),
        "endpoint": "GET /api/session/{session_id}/fhir",
        "input_schema": {
            "type": "object",
            "required": ["session_id", "doctor_token"],
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "FHIR export yapılacak oturum"
                },
                "doctor_token": {
                    "type": "string",
                    "description": "Doktor JWT token"
                }
            }
        },
        "example_input": {
            "session_id": "uuid-string",
            "doctor_token": "Bearer eyJ..."
        },
        "expected_output": {
            "resourceType": "Bundle",
            "id": "uuid-string",
            "type": "collection",
            "entry": [
                {"resource": {"resourceType": "Patient", "...": "..."}},
                {"resource": {"resourceType": "ClinicalImpression", "...": "..."}}
            ]
        }
    },

    # ────────────────────────────────────────────────────────────────────────
    # 9. Yerel AI kanıtı (Ollama proof)
    # ────────────────────────────────────────────────────────────────────────
    {
        "name": "anamnezai_get_local_ai_proof",
        "description": (
            "Sistemin tamamen yerel (local-first) çalıştığını kanıtlayan meta verileri döndürür. "
            "Hiçbir bulut AI API'si kullanılmadığını, hasta verisinin dışarı çıkmadığını "
            "ve MCP katmanının hazır olduğunu doğrular."
        ),
        "endpoint": "GET /api/offline-proof",
        "input_schema": {
            "type": "object",
            "properties": {}
        },
        "example_input": {},
        "expected_output": {
            "runtime": "ollama",
            "local_inference": True,
            "external_ai_api": False,
            "remote_embeddings": False,
            "cloud_translation_enabled": False,
            "mcp_ready": True,
            "channel_adapters_optional": True,
            "patient_data_external_transfer": False,
            "privacy_guarantee": "All patient data stays on-device. No cloud API used.",
            "kvkk_gdpr_compliant": True
        }
    },

    # ────────────────────────────────────────────────────────────────────────
    # 10. AI kalite değerlendirme sonuçlarını al
    # ────────────────────────────────────────────────────────────────────────
    {
        "name": "anamnezai_get_evaluation_results",
        "description": (
            "Sistemin AI kalite değerlendirme sonuçlarını ve canlı istatistiklerini döndürür. "
            "Triaj doğruluğu, RAG metrikleri, guardrail istatistikleri ve "
            "beklenmedik artan/azalan triaj trend analizleri dahildir."
        ),
        "endpoint": "GET /api/evaluation",
        "input_schema": {
            "type": "object",
            "properties": {}
        },
        "example_input": {},
        "expected_output": {
            "summary": {
                "overall_score_pct": 93.0,
                "triage_accuracy_pct": 100.0,
                "rag_accuracy_pct": 100.0,
                "red_flag_recall_pct": 100.0,
                "local_inference": True
            },
            "live_stats": {
                "completed_sessions": 42,
                "guardrail_escalations": 7
            }
        }
    },
]


def get_tool(name: str) -> Optional[dict]:
    """İsme göre araç şemasını döndürür."""
    for tool in ANAMNEZAI_TOOLS:
        if tool["name"] == name:
            return tool
    return None


def list_tool_names() -> list[str]:
    """Tüm araç isimlerini listeler."""
    return [t["name"] for t in ANAMNEZAI_TOOLS]


def validate_tool_input(tool_name: str, input_data: dict) -> tuple[bool, str]:
    """
    Basit input doğrulama — sadece required alanların varlığını kontrol eder.
    Üretimde: jsonschema kütüphanesi kullanılabilir.
    """
    tool = get_tool(tool_name)
    if not tool:
        return False, f"Araç bulunamadı: {tool_name}"

    schema = tool.get("input_schema", {})
    required = schema.get("required", [])

    missing = [r for r in required if r not in input_data]
    if missing:
        return False, f"Eksik zorunlu alanlar: {missing}"

    return True, "ok"


if __name__ == "__main__":
    print("AnamnezAI MCP Tool Şemaları")
    print("=" * 50)
    for tool in ANAMNEZAI_TOOLS:
        print(f"\n[{tool['name']}]")
        print(f"  Açıklama: {tool['description'][:80]}...")
        print(f"  Endpoint: {tool['endpoint']}")
        schema = tool.get("input_schema", {})
        required = schema.get("required", [])
        print(f"  Zorunlu alanlar: {required}")

