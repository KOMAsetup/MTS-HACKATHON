from app.extract import extract_lua


def test_extract_from_fence():
    s = "```lua\nreturn 1\n```"
    assert extract_lua(s) == "return 1"


def test_extract_lua_wrap():
    s = "lua{return x}lua"
    assert extract_lua(s) == "return x"


def test_extract_plain():
    assert extract_lua("  return 42\n") == "return 42"


def test_extract_does_not_strip_lua_literals_inside_code():
    s = (
        "local n = tonumber(wf.vars.num) or 0\n"
        'return string.format(\'lua{"num":%d,"squared":%d}lua\', n, n * n)'
    )
    assert extract_lua(s) == s


def test_extract_outer_lua_block_with_nested_braces_in_string():
    s = 'lua{local x = "}"\nreturn x\n}lua'
    assert extract_lua(s) == 'local x = "}"\nreturn x'
