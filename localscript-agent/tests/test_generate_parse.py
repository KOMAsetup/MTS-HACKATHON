from app.generate_parse import parse_debug_response, parse_generate_response


def test_parse_generate_clarification():
    raw = '{"response_kind": "clarification", "question": "What is n?"}'
    kind, q, lua, err = parse_generate_response(raw)
    assert kind == "clarification"
    assert q == "What is n?"
    assert lua is None
    assert err is None


def test_parse_generate_code():
    raw = r'{"response_kind": "code", "lua": "return 1"}'
    kind, q, lua, err = parse_generate_response(raw)
    assert kind == "code"
    assert q is None
    assert lua == "return 1"
    assert err is None


def test_parse_generate_json_fence():
    raw = """Here you go:
```json
{"response_kind": "code", "lua": "return 2"}
```
"""
    kind, q, lua, err = parse_generate_response(raw)
    assert kind == "code"
    assert lua == "return 2"


def test_parse_debug_response_fields():
    raw = '{"problem_description": "bad", "suggested_code": "return 0"}'
    pd, sc, err = parse_debug_response(raw)
    assert err is None
    assert pd == "bad"
    assert sc == "return 0"


def test_parse_debug_analysis_alias():
    raw = '{"analysis": "x", "suggested_code": "return 1"}'
    pd, sc, err = parse_debug_response(raw)
    assert err is None
    assert pd == "x"
