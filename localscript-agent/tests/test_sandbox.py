import shutil

import pytest

from app.sandbox import run_lua_with_wf

lua_bin = shutil.which("lua") or shutil.which("lua5.4")
pytestmark = pytest.mark.skipif(not lua_bin, reason="lua interpreter not installed")


def test_sandbox_return_last_email():
    wf = {"vars": {"emails": ["a", "b", "c"]}}
    code = "return wf.vars.emails[#wf.vars.emails]"
    ok, out, err = run_lua_with_wf(code, wf, lua_bin=lua_bin)
    assert ok
    assert out == "c"
    assert not err
