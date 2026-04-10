from app.prompts import build_user_message


def test_build_user_message_appends_lua_wrapper_constraint():
    p = 'Верни lua{"x":1}lua и поля num, squared в формате lua{...}lua.'
    u = build_user_message(p)
    assert "Hard constraint" in u
    assert "lua{" in u
    assert "tonumber" in u


def test_build_user_message_no_extra_constraint_without_markers():
    u = build_user_message("return 1+1")
    assert "Hard constraint" not in u
