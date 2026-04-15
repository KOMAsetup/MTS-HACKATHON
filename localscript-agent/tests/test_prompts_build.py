from app.models_io import CheckItem, DebugHistoryTurn, RefinementStep
from app.prompts import (
    build_debug_user_message,
    build_refinement_user_message,
    build_user_message,
    compress_context_for_repair,
    repair_user_message_compact,
)


def test_build_user_message_appends_lua_wrapper_constraint():
    p = 'Верни lua{"x":1}lua и поля num, squared в формате lua{...}lua.'
    u = build_user_message(p)
    assert "Hard constraint" in u
    assert "lua{" in u
    assert "tonumber" in u


def test_build_user_message_no_extra_constraint_without_markers():
    u = build_user_message("return 1+1")
    assert "Hard constraint" not in u


def test_compress_context_for_repair_truncates_long_strings():
    ctx = {"wf": {"vars": {"x": "a" * 200}}}
    out = compress_context_for_repair(ctx, str_limit=20)
    assert "…" in out
    assert len(out) < 250


def test_compress_context_for_repair_empty():
    assert compress_context_for_repair(None) == "{}"


def test_build_debug_user_message_includes_history_transcript():
    hist = [
        DebugHistoryTurn(
            user_code="return 1",
            user_prompt="why?",
            checks=[CheckItem(id="syntax_0", stage="syntax", passed=True, message="")],
            problem_description="Looks fine.",
            suggested_code="return 2",
        )
    ]
    msg = build_debug_user_message(
        "return 3",
        "what is 2+2?",
        hist,
        "All static checks passed.",
    )
    assert "what is 2+2?" in msg
    assert "PRIMARY TASK" in msg
    assert msg.index("PRIMARY TASK") > msg.index("return 3")
    assert "Earlier debug round 1" in msg
    assert "User's code then:" in msg and "return 1" in msg
    assert "Static checks then" in msg and "all_checks_passed: true" in msg
    assert "User question / note then:" in msg and "why?" in msg
    assert "Assistant problem_description then:" in msg and "Looks fine." in msg
    assert "Assistant suggested_code then:" in msg and "return 2" in msg
    assert "return 3" in msg


def test_build_debug_user_message_history_only_failed_checks_listed():
    hist = [
        DebugHistoryTurn(
            user_code="bad",
            user_prompt=None,
            checks=[
                CheckItem(id="s0", stage="syntax", passed=False, message="near '='"),
                CheckItem(id="st0", stage="static", passed=True, message=""),
            ],
            problem_description="fix",
            suggested_code="return 0",
        )
    ]
    msg = build_debug_user_message("return 1", None, hist, "all_checks_passed: true")
    assert "all_checks_passed: false" in msg
    assert "Failed checks:" in msg
    assert "syntax: near '='" in msg
    assert "static:" not in msg


def test_build_refinement_user_message_compact_checks_only():
    hist = [
        RefinementStep(
            assistant_code="return 1",
            user_feedback="fix it",
            checks=[
                CheckItem(id="s0", stage="syntax", passed=False, message="near '+'"),
                CheckItem(id="st0", stage="static", passed=True, message=""),
            ],
        )
    ]
    msg = build_refinement_user_message("Do math", hist)
    assert "all_checks_passed: false" in msg
    assert "Failed checks:" in msg
    assert "syntax: near '+'" in msg
    assert "stage:True" not in msg


def test_repair_user_message_compact_contains_errors_and_code():
    msg = repair_user_message_compact(
        task_prompt="Return sum of a and b",
        context={"wf": {"vars": {"a": 1, "b": 2}}},
        broken_code="return a +",
        error_lines=["syntax: unexpected symbol"],
        feedback="Use wf.vars",
    )
    assert "Task (reminder)" in msg
    assert "Validation errors" in msg
    assert "syntax: unexpected symbol" in msg
    assert "User feedback" in msg
    assert "```lua" in msg
    assert "return a +" in msg
    assert "wf" in msg
