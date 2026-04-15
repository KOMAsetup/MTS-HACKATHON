import pytest
from fastapi.testclient import TestClient

pytest.importorskip("pydantic_settings")

import app.main as main_module
from app.models_io import GenerateResponse, ResponseKind, StopReason


def test_health_smoke(monkeypatch):
    async def fake_health(*_args, **_kwargs):
        return True, True

    monkeypatch.setattr(main_module, "ollama_http_ok_and_model_ready", fake_health)

    with TestClient(main_module.app) as client:
        r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["ollama_reachable"] is True
    assert data["model_ready"] is True
    assert isinstance(data["model"], str)


def test_generate_smoke_contract(monkeypatch):
    async def fake_run_generate_pipeline(_client, _settings, body):
        return GenerateResponse(
            response_kind=ResponseKind.code,
            code=f"return {len(body.prompt)}",
            attempts=[],
            all_checks_passed=True,
            degraded=False,
            stop_reason=StopReason.validation_ok,
            llm_rounds=1,
            repair_rounds_used=0,
        )

    monkeypatch.setattr(main_module, "run_generate_pipeline", fake_run_generate_pipeline)

    with TestClient(main_module.app) as client:
        r = client.post("/generate", json={"prompt": "abc"})
    assert r.status_code == 200
    data = r.json()
    assert data["response_kind"] == "code"
    assert isinstance(data["code"], str)


def test_refine_empty_history_returns_422():
    with TestClient(main_module.app) as client:
        r = client.post("/refine", json={"prompt": "x", "refinement_history": []})
    assert r.status_code == 422


def test_debug_missing_code_returns_422():
    with TestClient(main_module.app) as client:
        r = client.post("/debug", json={})
    assert r.status_code == 422
