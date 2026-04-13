from app.prompts import (
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
