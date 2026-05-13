"""
AnamnezAI MCP Client — Uçtan Uca Örnek Akış
=============================================
Bu script, AnamnezAI klinik intake motorunu MCP araçları üzerinden
nasıl kullanacağınızı gösterir.

Senaryo: 45 yaşında erkek hasta, göğüs ağrısı ve sol kola yayılım.
Bu senaryo gerçek bir klinik acil (potansiyel AMI/STEMI) simüle eder.

Çalıştırma:
  pip install httpx
  python client_example.py

Not: Bu script MCP SDK gerektirmez.
Doğrudan AnamnezAI FastAPI backend'ine HTTP istekleri gönderir.
Bağlanmak için: python backend/main.py (ayrı terminalde)
"""

import asyncio
import json
import os
import sys
from datetime import datetime

try:
    import httpx
except ImportError:
    print("httpx kurulu değil. Kurun: pip install httpx")
    sys.exit(1)

# Backend URL — ortam değişkeni veya varsayılan
BASE_URL = os.getenv("ANAMNEZAI_BASE_URL", "http://localhost:8000")

# ─────────────────────────────────────────────────────────────────────────────
#  Renkli terminal çıktısı
# ─────────────────────────────────────────────────────────────────────────────
def _c(text: str, color: str) -> str:
    codes = {"red": "\033[91m", "green": "\033[92m", "yellow": "\033[93m",
             "blue": "\033[94m", "cyan": "\033[96m", "bold": "\033[1m", "reset": "\033[0m"}
    return f"{codes.get(color, '')}{text}{codes['reset']}"

def print_section(title: str):
    print(f"\n{_c('─' * 60, 'blue')}")
    print(f"{_c('  ' + title, 'bold')}")
    print(_c('─' * 60, 'blue'))

def print_tool_call(tool: str, result: dict):
    print(f"\n{_c('[TOOL]', 'cyan')} {tool}")
    print(json.dumps(result, ensure_ascii=False, indent=2)[:800])
    if len(json.dumps(result)) > 800:
        print("  ... (çıktı kısaltıldı)")


# ─────────────────────────────────────────────────────────────────────────────
#  HTTP Yardımcıları
# ─────────────────────────────────────────────────────────────────────────────

async def post(path: str, data: dict, token: str = "") -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(timeout=180.0) as c:
        r = await c.post(f"{BASE_URL}{path}", json=data, headers=headers)
        r.raise_for_status()
        return r.json()

async def get(path: str, token: str = "") -> dict:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(timeout=180.0) as c:
        r = await c.get(f"{BASE_URL}{path}", headers=headers)
        r.raise_for_status()
        return r.json()


# ─────────────────────────────────────────────────────────────────────────────
#  Örnek Akış 1: Tam Klinik Intake (Göğüs Ağrısı Senaryosu)
# ─────────────────────────────────────────────────────────────────────────────

async def demo_full_intake():
    print_section("SENARYO 1: Potansiyel AMI — Göğüs Ağrısı")
    print(_c("⚠️  Bu bir DEMO simülasyondur. Gerçek klinik karar doktor incelemesi gerektirir.", "yellow"))

    # ── Adım 1: anamnezai_start_intake ──────────────────────────────────────
    print_section("ARAÇ: anamnezai_start_intake")
    result = await post("/api/session/start", {
        "patient_name": "Mehmet Yılmaz",
        "age": 58,
        "gender": "Erkek",
        "language": "tr"
    })
    session_id = result["session_id"]
    print_tool_call("anamnezai_start_intake", result)
    print(f"\n{_c('🤖 AI:', 'cyan')} {result['question']}")

    # ── Adım 2: Şikayet Cevabı ──────────────────────────────────────────────
    conversation = [
        "Göğsümde baskı var ve sol koluma vuruyor",
        "Sabahtan beri, yaklaşık 3 saattir. Şiddet 8/10",
        "Evet, terliyorum ve nefes almakta güçlük çekiyorum",
        "70 yaşındaki babam kalp krizi geçirdi, sigara içiyorum",
        "Hayır, daha önce böyle bir şey olmamıştı",
        "Evet, 2 yıldır hipertansiyonum var, KB ilacı kullanıyorum",
    ]

    print_section("ARAÇ: anamnezai_submit_answer (çoklu tur)")
    for answer in conversation:
        print(f"\n{_c('👤 Hasta:', 'green')} {answer}")
        try:
            result = await post("/api/session/answer", {
                "session_id": session_id,
                "answer": answer
            })
            print_tool_call("anamnezai_submit_answer", result)
            if result.get("question") == "__COMPLETED__":
                print(f"\n{_c('✅ Mülakat tamamlandı!', 'green')}")
                break
            print(f"\n{_c('🤖 AI:', 'cyan')} {result['question']}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                print(f"{_c('ℹ️  Mülakat zaten tamamlandı', 'yellow')}")
                break
            raise

    # ── Adım 3: anamnezai_finalize_summary ──────────────────────────────────
    print_section("ARAÇ: anamnezai_finalize_summary")
    try:
        summary = await get(f"/api/session/{session_id}/summary")
        triage = summary.get("triage_level", "?")
        color = "red" if triage == "RED" else "yellow" if triage == "YELLOW" else "green"
        print(f"\n{_c(f'🚨 TRİAJ SONUCU: {triage}', color)}")
        print(f"  Güven skoru: {summary.get('confidence_score')}%")
        print(f"  Ana şikayet: {summary.get('chief_complaint', '')}")
        print(f"  Önerilen eylem: {summary.get('recommended_action', '')}")
        if summary.get("urgency_flags"):
            print(f"  Acil bayraklar: {summary['urgency_flags']}")
        if summary.get("safety_guardrail_triggered"):
            print(f"  {_c('⚠️  SAFETY GUARDRAIL TETİKLENDİ', 'red')}: {summary.get('guardrail_rules_fired', [])}")
        print(f"  Klinik tamamlanma skoru: {summary.get('clinical_completeness_score')}%")
    except Exception as e:
        print(f"{_c('❌ Özet alınamadı:', 'red')} {e}")
        return None

    # ── Adım 4: anamnezai_get_local_ai_proof ────────────────────────────────
    print_section("ARAÇ: anamnezai_get_local_ai_proof")
    proof = await get("/api/offline-proof")
    print_tool_call("anamnezai_get_local_ai_proof", proof)
    mcp_ready = proof.get("mcp_ready", False)
    print(f"\n  {_c('✅ MCP Ready:', 'green') if mcp_ready else _c('❌ MCP Not Ready', 'red')} {mcp_ready}")
    print(f"  Bulut API: {_c('❌ Yok (local-first)', 'green') if not proof.get('external_ai_api') else _c('⚠️  Var', 'red')}")

    # ── Adım 5: FHIR Export ─────────────────────────────────────────────────
    print_section("ARAÇ: anamnezai_export_fhir (doctor auth gerekir)")
    print(_c("  Not: FHIR export doktor JWT token'ı gerektirir.", "yellow"))
    print("  Demo: POST /auth/login ile doctor@anamnezai.tr token alın")
    print("  Sonra: GET /api/session/{id}/fhir ile FHIR Bundle alın")
    print("\n  Örnek FHIR Bundle yapısı:")
    print(json.dumps({
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [
            {"resource": {"resourceType": "Patient", "name": [{"text": "Mehmet Yılmaz"}]}},
            {"resource": {"resourceType": "ClinicalImpression", "description": "Göğüs ağrısı..."}},
        ]
    }, indent=2, ensure_ascii=False))

    return session_id


# ─────────────────────────────────────────────────────────────────────────────
#  Örnek Akış 2: Kanal Adapter (WhatsApp-style)
# ─────────────────────────────────────────────────────────────────────────────

async def demo_channel_intake():
    print_section("SENARYO 2: WhatsApp-Style Kanal Adapter Demo")
    print(_c("⚠️  Bu gerçek WhatsApp entegrasyonu değildir. Kanal adapter demosu.", "yellow"))
    print("   Gerçek WhatsApp/Telegram entegrasyonu için Meta/Telegram API gerekir.")
    print("   Bu demo, /api/channel/intake/message endpoint'ini kullanır.\n")

    channel_messages = [
        "Göğsümde baskı var ve sol koluma vuruyor",
        "3 saattir var, 8/10 şiddetinde",
        "Evet terliyorum ve nefes alması zor",
        "70'inde babam kalp krizi geçirdi, sigara içiyorum",
        "Evet hipertansiyonum var",
    ]

    session_id = None
    for i, msg in enumerate(channel_messages):
        print(f"{_c('👤 WhatsApp:', 'green')} {msg}")
        result = await post("/api/channel/intake/message", {
            "channel": "whatsapp_demo",
            "external_user_id": "demo-user-wp-001",
            "message": msg,
            "language": "tr",
            "session_id": session_id
        })
        session_id = result.get("session_id", session_id)
        print(f"{_c('🤖 AnamnezAI:', 'cyan')} {result.get('reply', '')}")

        next_action = result.get("next_action", "")
        if next_action == "completed":
            triage = result.get("triage_preview", "")
            color = "red" if triage == "RED" else "yellow" if triage == "YELLOW" else "green"
            print(f"\n{_c(f'✅ Tamamlandı — Triaj: {triage}', color)}")
            print(f"   Doktor kuyruğu oluşturuldu: {result.get('doctor_queue_created', False)}")
            break


# ─────────────────────────────────────────────────────────────────────────────
#  Örnek Akış 3: AI Kalite Değerlendirme
# ─────────────────────────────────────────────────────────────────────────────

async def demo_evaluation():
    print_section("ARAÇ: anamnezai_get_evaluation_results")
    result = await get("/api/evaluation")
    summary = result.get("summary", {})
    print(f"\n  Genel Skor: {_c(str(summary.get('overall_score_pct', 0)) + '%', 'green')}")
    print(f"  Triaj Doğruluğu: {summary.get('triage_accuracy_pct', 0)}%")
    print(f"  Kırmızı Bayrak Tespiti: {summary.get('red_flag_recall_pct', 0)}%")
    print(f"  Yerel Inferans: {summary.get('local_inference', False)}")
    print(f"  Bulut API: {summary.get('cloud_api_used', True)}")


# ─────────────────────────────────────────────────────────────────────────────
#  Ana fonksiyon
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    print(_c("\n" + "="*60, "bold"))
    print(_c("  AnamnezAI MCP Client — Uçtan Uca Örnek Akış", "bold"))
    print(_c("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "blue"))
    print(_c("  Backend: " + BASE_URL, "blue"))
    print(_c("="*60, "bold"))

    # Backend sağlık kontrolü
    print_section("Backend Sağlık Kontrolü")
    try:
        health = await get("/healthz")
        print(f"  {_c('✅ Backend çalışıyor:', 'green')} {health}")
    except Exception as e:
        print(f"  {_c('❌ Backend bağlantısı başarısız!', 'red')} {e}")
        print(f"\n  Çözüm: Backend'i başlatın:")
        print(f"    cd mediscreen/backend && python main.py")
        return

    # Hangi senaryoyu çalıştıralım?
    mode = "all"
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()

    if mode in ("intake", "all"):
        try:
            await demo_full_intake()
        except Exception as e:
            print(f"\n{_c('Demo 1 hatası:', 'red')} {e}")

    if mode in ("channel", "all"):
        try:
            await demo_channel_intake()
        except Exception as e:
            print(f"\n{_c('Demo 2 hatası:', 'red')} {e}")

    if mode in ("eval", "all"):
        try:
            await demo_evaluation()
        except Exception as e:
            print(f"\n{_c('Demo 3 hatası:', 'red')} {e}")

    print_section("Demo Tamamlandı")
    print(_c("\n  AnamnezAI — Local-first clinical intake engine", "bold"))
    print(_c("  'not a chatbot API — a local-first clinical intake engine that", "blue"))
    print(_c("   turns unstructured patient complaints into doctor-reviewable,", "blue"))
    print(_c("   safety-guarded, evidence-linked clinical summaries.'", "blue"))
    print()


if __name__ == "__main__":
    print("Kullanım:")
    print("  python client_example.py          # Tüm senaryolar")
    print("  python client_example.py intake   # Sadece tam intake akışı")
    print("  python client_example.py channel  # Sadece WhatsApp-style demo")
    print("  python client_example.py eval     # Sadece değerlendirme")
    print()
    asyncio.run(main())

