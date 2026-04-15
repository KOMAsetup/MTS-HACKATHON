from app.models_io import (
    CheckItem,
    GenerateRequest,
    GenerateResponse,
    RefinementStep,
    ResponseKind,
    StopReason,
)


def test_generate_request_no_legacy_debug_field():
    r = GenerateRequest(prompt="x")
    d = r.model_dump()
    assert "debug" not in d
    assert "context" not in d


def test_generate_response_code_branch_dump():
    r = GenerateResponse(
        response_kind=ResponseKind.code,
        code="return 1",
        attempts=[],
        all_checks_passed=True,
        degraded=False,
        stop_reason=StopReason.validation_ok,
        llm_rounds=1,
        repair_rounds_used=0,
    )
    d = r.model_dump(exclude_none=True)
    assert d["response_kind"] == "code"
    assert d["code"] == "return 1"
    assert "clarification_question" not in d


def test_generate_response_clarification_branch():
    r = GenerateResponse(
        response_kind=ResponseKind.clarification,
        clarification_question="Which format?",
        attempts=[],
        llm_rounds=1,
        repair_rounds_used=0,
    )
    d = r.model_dump(exclude_none=True)
    assert d["response_kind"] == "clarification"
    assert d["clarification_question"] == "Which format?"
    assert "code" not in d


def test_refinement_step_requires_checks_list():
    RefinementStep(
        assistant_code="return 1",
        user_feedback="ok",
        checks=[],
    )
    step = RefinementStep(
        assistant_code="return 1",
        user_feedback="ok",
        checks=[CheckItem(id="syntax_0", stage="syntax", passed=True, message="")],
    )
    assert len(step.checks) == 1
