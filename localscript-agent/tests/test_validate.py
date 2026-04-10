import shutil

import pytest

from app.validate import static_guard_violations, validate_code

luac = shutil.which("luac") or shutil.which("luac5.4")


def test_static_reject_require():
    code = 'require("os")'
    assert static_guard_violations(code)


def test_static_ok():
    code = "return wf.vars.x + 1"
    assert not static_guard_violations(code)


def test_static_allows_os_time_and_package_field():
    code = "return os.time({year=2023}) + package.items"
    assert not static_guard_violations(code)


def test_static_rejects_package_load():
    code = "return package.load('x')"
    assert static_guard_violations(code)


def test_static_rejects_os_execute():
    code = 'os.execute("rm -rf /")'
    assert static_guard_violations(code)


@pytest.mark.skipif(not luac, reason="luac not installed")
def test_luac_simple():
    ok, errs = validate_code("return 1 + 1", luac_path=luac)
    assert ok
    assert not errs
