import shutil

import pytest

from app.code_checks import CheckStage, run_all_checks
from app.config import Settings

luac = shutil.which("luac") or shutil.which("luac5.4")


@pytest.mark.skipif(not luac, reason="luac not installed")
def test_static_violation_require():
    s = Settings(luac_path=luac)
    r = run_all_checks('require("x")', settings=s, context=None)
    assert not r.ok
    assert any(v.stage == CheckStage.static for v in r.violations)


def test_syntax_ok_when_luac_available():
    if not luac:
        pytest.skip("luac not installed")
    s = Settings(luac_path=luac)
    r = run_all_checks("return 1 + 1", settings=s, context=None)
    assert r.ok
    assert not r.violations


@pytest.mark.skipif(not luac, reason="luac not installed")
def test_syntax_error_reported():
    s = Settings(luac_path=luac)
    r = run_all_checks("return 1 +", settings=s, context=None)
    assert not r.ok
    assert any(v.stage == CheckStage.syntax for v in r.violations)


@pytest.mark.skipif(not luac, reason="luac not installed")
def test_error_lines_format():
    s = Settings(luac_path=luac)
    r = run_all_checks('require("os")', settings=s, context=None)
    lines = r.error_lines()
    assert lines
    assert any(line.startswith("static:") for line in lines)
