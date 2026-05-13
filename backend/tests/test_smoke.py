"""
Smoke tests for AnamnezAI backend.
These tests verify the app can be imported and basic structures are in place.
No Ollama or PostgreSQL connection required — DB calls are mocked.
"""
import os
import pytest
from unittest.mock import patch, MagicMock

# Test ortamı — PostgreSQL bağlantısı mock'lanır
os.environ.setdefault("GEMMA_MODEL", "test-model")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("RAG_ENABLED", "false")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-smoke-tests-only")

# Postgres pool'unu import öncesi mock'la — test ortamında PG bağlantısı yok
_mock_cursor = MagicMock()
_mock_cursor.__enter__ = MagicMock(return_value=_mock_cursor)
_mock_cursor.__exit__ = MagicMock(return_value=False)
_mock_cursor.fetchall.return_value = []
_mock_cursor.fetchone.return_value = None

_pg_patch = patch("database.get_cursor", return_value=_mock_cursor)
_pg_patch.start()


def test_main_imports():
    """App module must import without syntax errors."""
    import main
    assert main.app is not None


def test_fastapi_app_type():
    """app must be a FastAPI instance."""
    from fastapi import FastAPI
    import main
    assert isinstance(main.app, FastAPI)


def test_gemma_model_configured():
    """GEMMA_MODEL must be set."""
    import main
    assert main.GEMMA_MODEL is not None
    assert len(main.GEMMA_MODEL) > 0


def test_session_response_model():
    """SessionResponse Pydantic model must be valid."""
    from main import SessionResponse
    r = SessionResponse(
        session_id="test-id",
        question="Test soru?",
        step=1,
        total_steps=5,
    )
    assert r.session_id == "test-id"
    assert r.step == 1


def test_clinical_summary_has_trust_fields():
    """ClinicalSummaryResponse must include trust layer fields."""
    from main import ClinicalSummaryResponse
    import inspect
    fields = ClinicalSummaryResponse.model_fields
    assert "evidence" in fields, "evidence field missing from ClinicalSummaryResponse"
    assert "guideline_sources" in fields, "guideline_sources field missing"
    assert "doctor_review_required" in fields, "doctor_review_required field missing"
    assert "unsafe_to_self_manage" in fields, "unsafe_to_self_manage field missing"


def test_clean_gemma_response_strips_think_blocks():
    """clean_gemma_response must remove <think> blocks."""
    from main import clean_gemma_response
    raw = "<think>Internal reasoning here</think>Final answer."
    result = clean_gemma_response(raw)
    assert "<think>" not in result
    assert "Final answer." in result


def test_adaptive_steps_emergency():
    """Emergency keywords must trigger 7-step interview."""
    from main import _adaptive_steps
    assert _adaptive_steps("göğüs ağrısı var", age=45, lang="tr") == 7


def test_adaptive_steps_elderly_minimum():
    """Elderly patients (70+) must have at least 5 steps."""
    from main import _adaptive_steps
    steps = _adaptive_steps("öksürük var", age=72, lang="tr")
    assert steps >= 5


def test_adaptive_steps_pediatric_minimum():
    """Pediatric patients (≤12) must have at least 5 steps — fever value asked first."""
    from main import _adaptive_steps
    steps = _adaptive_steps("ateş var", age=3, lang="tr")
    assert steps >= 5, "Pediatric cases must have minimum 5 steps for proper fever protocol"


def test_auth_module_imports():
    """auth.py must import without errors."""
    import auth
    assert hasattr(auth, "create_user")
    assert hasattr(auth, "verify_password")
    assert hasattr(auth, "create_access_token")


def test_no_hardcoded_localhost_in_api():
    """No HTML file should contain hardcoded http://localhost:8000 as const API."""
    import glob, re
    html_files = glob.glob(
        os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "*.html")
    )
    pattern = re.compile(r"const\s+API\s*=\s*['\"]http://localhost:\d+['\"]")
    offenders = []
    for f in html_files:
        try:
            content = open(f, encoding="utf-8").read()
            if pattern.search(content):
                offenders.append(os.path.basename(f))
        except Exception:
            pass
    assert offenders == [], f"Hardcoded localhost API found in: {offenders}"


# ─────────────────────────────────────────────────────────────────────────────
#  Safety Guardrail Tests — test_safety_guardrails()
#  These tests verify deterministic escalation rules in safety.py.
#  They run without Ollama — proof that guardrails are LLM-independent.
# ─────────────────────────────────────────────────────────────────────────────

def test_safety_guardrails_cardiac_escalates_to_red():
    """Cardiac triple (chest pain + left arm + sweating) must escalate to RED."""
    from safety import apply_guardrails
    triage_data = {"triage_level": "YELLOW", "urgency_flags": []}
    qa_history = [
        {"question": "Şikayetiniz nedir?", "answer": "Göğüs ağrısı var, sol koluma yayılıyor"},
        {"question": "Başka belirtiniz?", "answer": "Terleme var ve nefes darlığı hissediyorum"},
    ]
    result, triggered = apply_guardrails(triage_data, qa_history, lang="tr")
    assert result["triage_level"] == "RED", (
        "Cardiac triple (chest + left arm + sweating) must always escalate to RED"
    )
    assert len(triggered) > 0
    assert result["safety_guardrail_triggered"] is True


def test_safety_guardrails_no_false_positive_on_minor_complaint():
    """Simple headache without red flags must NOT trigger RED guardrail."""
    from safety import apply_guardrails
    triage_data = {"triage_level": "GREEN", "urgency_flags": []}
    qa_history = [
        {"question": "Şikayetiniz?", "answer": "Hafif baş ağrısı var, 2 gündür"},
    ]
    result, triggered = apply_guardrails(triage_data, qa_history, lang="tr")
    assert result["triage_level"] == "GREEN", (
        "Simple headache without red-flag terms must remain GREEN"
    )
    assert result["safety_guardrail_triggered"] is False


def test_safety_guardrails_vital_spo2_escalates_red():
    """SpO₂ < 90% in vitals must escalate triage to RED regardless of LLM output."""
    from safety import apply_guardrails
    triage_data = {"triage_level": "GREEN", "urgency_flags": []}
    qa_history = [{"question": "Nefes?", "answer": "Hafif nefes güçlüğü"}]
    vitals = {"spo2": 86}
    result, triggered = apply_guardrails(triage_data, qa_history, lang="tr", vitals=vitals)
    assert result["triage_level"] == "RED", "SpO2=86% must trigger RED via vital-sign guardrail"
    assert any("86" in t for t in triggered)


def test_safety_guardrails_stroke_fast_escalates_red():
    """Stroke FAST criteria (facial droop / arm weakness) must escalate to RED."""
    from safety import apply_guardrails
    triage_data = {"triage_level": "YELLOW", "urgency_flags": []}
    qa_history = [
        {"question": "Şikayetiniz?", "answer": "Konuşma bozukluğu var, yüz kayması fark ettim"},
        {"question": "Süre?", "answer": "1 saattir böyle"},
    ]
    result, triggered = apply_guardrails(triage_data, qa_history, lang="tr")
    assert result["triage_level"] == "RED", "Stroke FAST signs must escalate to RED"


def test_safety_guardrails_pediatric_fever_yellow():
    """Infant fever keyword must escalate to at least YELLOW."""
    from safety import apply_guardrails
    triage_data = {"triage_level": "GREEN", "urgency_flags": []}
    qa_history = [
        {"question": "Şikayetiniz?", "answer": "Bebeğimin ateşi çok yüksek, 6 aylık"},
    ]
    result, triggered = apply_guardrails(triage_data, qa_history, lang="tr")
    assert result["triage_level"] in ("YELLOW", "RED"), (
        "Infant fever must escalate from GREEN to at least YELLOW"
    )


def test_safety_guardrails_red_never_downgrades():
    """Guardrails must NEVER downgrade an existing RED to YELLOW or GREEN."""
    from safety import apply_guardrails
    triage_data = {"triage_level": "RED", "urgency_flags": []}
    qa_history = [
        {"question": "Şikayetiniz?", "answer": "Hafif baş ağrısı"},
    ]
    result, triggered = apply_guardrails(triage_data, qa_history, lang="tr")
    assert result["triage_level"] == "RED", "Guardrails must never downgrade an existing RED"


def test_safety_guardrails_hypotension_vital_red():
    """Systolic BP < 90 mmHg must trigger RED via vital-sign guardrail."""
    from safety import apply_guardrails
    triage_data = {"triage_level": "YELLOW", "urgency_flags": []}
    qa_history = [{"question": "Durumu?", "answer": "Bayılıyormuş gibi hissediyor"}]
    vitals = {"blood_pressure": "78/50"}
    result, triggered = apply_guardrails(triage_data, qa_history, lang="tr", vitals=vitals)
    assert result["triage_level"] == "RED", "SBP=78 mmHg must escalate to RED"


def test_safety_guardrails_sah_thunderclap_red():
    """Thunderclap 'worst headache of life' must escalate to RED (SAH rule)."""
    from safety import apply_guardrails
    triage_data = {"triage_level": "YELLOW", "urgency_flags": []}
    qa_history = [
        {"question": "Baş ağrısı nasıl?", "answer": "Hayatımın en kötü baş ağrısı, ani başladı"},
    ]
    result, triggered = apply_guardrails(triage_data, qa_history, lang="tr")
    assert result["triage_level"] == "RED", "Thunderclap worst-ever headache must be RED (SAH)"


def test_pediatric_interview_steps_function_exists():
    """_pediatric_interview_steps() must exist and return a non-empty list."""
    from main import _pediatric_interview_steps
    steps = _pediatric_interview_steps()
    assert isinstance(steps, list)
    assert len(steps) == 5, "Pediatric protocol must have exactly 5 interview step keys"


def test_is_pediatric_case_by_age():
    """_is_pediatric_case must return True when patient age ≤ 12."""
    from main import _is_pediatric_case
    session_child = {
        "age": 4, "language": "tr",
        "qa_history": [{"question": "Şikayet?", "answer": "ateş var"}]
    }
    session_adult = {
        "age": 35, "language": "tr",
        "qa_history": [{"question": "Şikayet?", "answer": "baş ağrısı"}]
    }
    assert _is_pediatric_case(session_child) is True
    assert _is_pediatric_case(session_adult) is False


# ─────────────────────────────────────────────────────────────────────────────
#  MCP Layer Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_mcp_tools_importable():
    """mcp_server/tools.py must import without errors."""
    import sys, os
    mcp_path = os.path.join(os.path.dirname(__file__), "..", "..", "mcp_server")
    if mcp_path not in sys.path:
        sys.path.insert(0, mcp_path)
    import tools as mcp_tools
    assert hasattr(mcp_tools, "ANAMNEZAI_TOOLS"), "ANAMNEZAI_TOOLS must be defined in tools.py"
    assert len(mcp_tools.ANAMNEZAI_TOOLS) >= 10, "Must have at least 10 MCP tools"


def test_mcp_tool_names_unique():
    """All MCP tool names must be unique."""
    import sys, os
    mcp_path = os.path.join(os.path.dirname(__file__), "..", "..", "mcp_server")
    if mcp_path not in sys.path:
        sys.path.insert(0, mcp_path)
    from tools import ANAMNEZAI_TOOLS
    names = [t["name"] for t in ANAMNEZAI_TOOLS]
    assert len(names) == len(set(names)), f"Duplicate tool names found: {[n for n in names if names.count(n) > 1]}"


def test_mcp_each_tool_has_required_fields():
    """Each MCP tool must have name, description, input_schema, example_input."""
    import sys, os
    mcp_path = os.path.join(os.path.dirname(__file__), "..", "..", "mcp_server")
    if mcp_path not in sys.path:
        sys.path.insert(0, mcp_path)
    from tools import ANAMNEZAI_TOOLS
    for tool in ANAMNEZAI_TOOLS:
        assert "name" in tool, f"Tool missing 'name': {tool}"
        assert "description" in tool, f"Tool '{tool.get('name')}' missing 'description'"
        assert "input_schema" in tool, f"Tool '{tool.get('name')}' missing 'input_schema'"
        assert "example_input" in tool, f"Tool '{tool.get('name')}' missing 'example_input'"


def test_mcp_validate_tool_input_works():
    """validate_tool_input must catch missing required fields."""
    import sys, os
    mcp_path = os.path.join(os.path.dirname(__file__), "..", "..", "mcp_server")
    if mcp_path not in sys.path:
        sys.path.insert(0, mcp_path)
    from tools import validate_tool_input
    ok, msg = validate_tool_input("anamnezai_start_intake", {"patient_name": "Ali", "age": 30, "gender": "Erkek"})
    assert ok is True and msg == "ok"
    ok2, msg2 = validate_tool_input("anamnezai_start_intake", {"age": 30})
    assert ok2 is False
    assert "patient_name" in msg2 or "gender" in msg2


def test_channel_intake_model_exists():
    """ChannelIntakeRequest Pydantic model must be defined in main.py."""
    import main
    assert hasattr(main, "ChannelIntakeRequest"), "ChannelIntakeRequest must be defined"
    req = main.ChannelIntakeRequest(
        channel="whatsapp_demo",
        external_user_id="test-user-1",
        message="Göğsüm ağrıyor",
        language="tr",
        session_id=None,
    )
    assert req.channel == "whatsapp_demo"
    assert req.message == "Göğsüm ağrıyor"


def test_channel_intake_endpoint_registered():
    """POST /api/channel/intake/message must be registered in the FastAPI app."""
    import main
    routes = [r.path for r in main.app.routes]
    assert "/api/channel/intake/message" in routes, (
        "POST /api/channel/intake/message endpoint must be registered"
    )


def test_allow_cloud_translation_default_false():
    """ALLOW_CLOUD_TRANSLATION must default to False (local-first guarantee)."""
    import main
    # Varsayılan olarak kapalı — test ortamında env set edilmedi
    # main.ALLOW_CLOUD_TRANSLATION env'den okunur; test ortamında false olmalı
    assert main.ALLOW_CLOUD_TRANSLATION is False, (
        "ALLOW_CLOUD_TRANSLATION must default to False to preserve local-first guarantee"
    )


def test_offline_proof_has_mcp_fields():
    """offline_proof function annotations must include new MCP fields."""
    import main, inspect
    src = inspect.getsource(main.offline_proof)
    assert "mcp_ready" in src, "offline_proof must include mcp_ready field"
    assert "channel_adapters_optional" in src, "offline_proof must include channel_adapters_optional"
    assert "cloud_translation_enabled" in src, "offline_proof must include cloud_translation_enabled"


def test_healthz_not_broken():
    """The /healthz endpoint must still return {status: ok} — regression check."""
    from fastapi.testclient import TestClient
    import main
    client = TestClient(main.app)
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "ok"


# ─────────────────────────────────────────────────────────────────────────────
#  Pre-Visit Intake Mode Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_previsit_endpoints_registered():
    """Pre-visit endpoints must be registered in the FastAPI app."""
    import main
    routes = [r.path for r in main.app.routes]
    assert "/api/appointments/demo" in routes, "POST /api/appointments/demo must be registered"
    assert "/api/appointments/{appointment_id}/previsit/start" in routes
    assert "/api/appointments/{appointment_id}/previsit/message" in routes
    assert "/api/appointments/{appointment_id}/brief" in routes
    assert "/api/appointments/today" in routes


def test_previsit_message_model_exists():
    """PreVisitMessageRequest Pydantic model must be defined in main.py."""
    import main
    assert hasattr(main, "PreVisitMessageRequest"), "PreVisitMessageRequest must be defined"
    req = main.PreVisitMessageRequest(message="Baş ağrım var", language="tr")
    assert req.message == "Baş ağrım var"
    assert req.language == "tr"


def test_previsit_message_model_defaults():
    """PreVisitMessageRequest must have language='tr' as default."""
    import main
    req = main.PreVisitMessageRequest(message="Test")
    assert req.language == "tr"


def test_appointments_storage_initialized():
    """_appointments and _appt_sessions dicts must exist in main."""
    import main
    assert hasattr(main, "_appointments"), "_appointments dict must exist"
    assert hasattr(main, "_appt_sessions"), "_appt_sessions dict must exist"
    assert isinstance(main._appointments, dict)
    assert isinstance(main._appt_sessions, dict)


def test_previsit_system_prompt_function():
    """_previsit_system_prompt must return a non-empty string for tr/en."""
    import main
    prompt_tr = main._previsit_system_prompt("tr", "Dr. Test", "10:00")
    prompt_en = main._previsit_system_prompt("en", "Dr. Test", "10:00")
    assert len(prompt_tr) > 50, "TR pre-visit system prompt must be meaningful"
    assert len(prompt_en) > 50, "EN pre-visit system prompt must be meaningful"
    assert "randevu" in prompt_tr.lower() or "öncesi" in prompt_tr.lower()
    assert "appointment" in prompt_en.lower() or "visit" in prompt_en.lower()


def test_previsit_start_returns_404_for_unknown_appt():
    """Start pre-visit for unknown appointment must return 404."""
    from fastapi.testclient import TestClient
    import main
    client = TestClient(main.app)
    # Inject a doctor token
    from auth import create_access_token
    token = create_access_token({"sub": "test@test.com", "role": "doctor", "user_id": "test-doc-1"})
    headers = {"Authorization": f"Bearer {token}"}
    res = client.post("/api/appointments/nonexistent-id/previsit/start", headers=headers)
    assert res.status_code == 404


def test_previsit_html_exists():
    """previsit.html must exist in the frontend directory."""
    import os
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
    previsit_path = os.path.join(frontend_dir, "previsit.html")
    assert os.path.exists(previsit_path), "frontend/previsit.html must exist"


def test_previsit_html_has_key_elements():
    """previsit.html must contain key UI elements."""
    import os
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
    previsit_path = os.path.join(frontend_dir, "previsit.html")
    with open(previsit_path, encoding="utf-8") as f:
        content = f.read()
    assert "previsit/start" in content or "previsit/message" in content, \
        "previsit.html must call pre-visit API endpoints"
    assert "appointment_id" in content or "appt" in content, \
        "previsit.html must handle appointment ID parameter"
    assert "wait_warning" in content, \
        "previsit.html must handle wait_warning red flag"


def test_intake_type_previsit_in_session():
    """Pre-visit sessions must have intake_type='pre_visit' field."""
    # Verify the code sets intake_type — inspect source
    import main, inspect
    src = inspect.getsource(main.start_previsit)
    assert "intake_type" in src, "start_previsit must set intake_type field"
    assert "pre_visit" in src, "start_previsit must set intake_type to 'pre_visit'"




