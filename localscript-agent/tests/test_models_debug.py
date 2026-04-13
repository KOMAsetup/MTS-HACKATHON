from app.models_io import GenerateDebugMeta, GenerateRequest, GenerateResponse


def test_generate_request_debug_default_false():
    r = GenerateRequest(prompt="x")
    assert r.debug is False


def test_generate_response_exclude_none_omits_debug():
    r = GenerateResponse(code="return 1")
    d = r.model_dump(exclude_none=True)
    assert d == {"code": "return 1"}
    r2 = GenerateResponse(
        code="return 1",
        debug=GenerateDebugMeta(
            first_validation_ok=True,
            final_validation_ok=True,
            llm_rounds=1,
            repair_rounds_used=0,
            max_repair_attempts=2,
            degraded=False,
            log=["validate: pass (initial)"],
        ),
    )
    d2 = r2.model_dump(exclude_none=True)
    assert "debug" in d2
    assert d2["debug"]["llm_rounds"] == 1
    assert d2["debug"]["degraded"] is False
