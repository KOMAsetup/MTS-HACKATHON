from app.extract import extract_lua


def test_extract_from_fence():
    s = "```lua\nreturn 1\n```"
    assert extract_lua(s) == "return 1"


def test_extract_lua_wrap():
    s = "lua{return x}lua"
    assert extract_lua(s) == "return x"


def test_extract_plain():
    assert extract_lua("  return 42\n") == "return 42"
