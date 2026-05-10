"""
Smoke tests for AnamnezAI backend.
These tests verify the app can be imported and basic structures are in place.
No Ollama connection required.
"""
import os
import pytest

# Set test env before importing app
os.environ.setdefault("DB_PATH", ":memory:")
os.environ.setdefault("GEMMA_MODEL", "test-model")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("RAG_ENABLED", "false")


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

