import asyncio

import httpx
import pytest

pytest.importorskip("pydantic_settings")

from app.code_checks import CheckResult, CheckStage, Violation
from app.config import Settings
from app.models_io import StopReason
from app.pipeline import run_repair_loop


def test_repair_loop_smoke_fixes_after_one_repair(monkeypatch):
    def fake_run_all_checks(code, *, settings, context=None):
        if code.strip() == "return 1":
            return CheckResult(ok=True, violations=())
        return CheckResult(
            ok=False,
            violations=(Violation(CheckStage.static, "mock violation"),),
        )

    async def fake_chat_completion(_client, _settings, _messages):
        return "return 1"

    monkeypatch.setattr("app.pipeline.run_all_checks", fake_run_all_checks)
    monkeypatch.setattr("app.pipeline.chat_completion", fake_chat_completion)

    async def _run():
        async with httpx.AsyncClient() as client:
            return await run_repair_loop(
                client,
                Settings(),
                task_prompt="demo",
                context=None,
                feedback=None,
                initial_code="bad",
                max_repair_attempts=2,
            )

    (
        final_code,
        attempts,
        all_ok,
        degraded,
        stop_reason,
        repair_used,
        first_ok,
        _log,
    ) = asyncio.run(_run())

    assert final_code == "return 1"
    assert len(attempts) == 2
    assert all_ok is True
    assert degraded is False
    assert stop_reason == StopReason.validation_ok
    assert repair_used == 1
    assert first_ok is False


def test_repair_loop_smoke_marks_degraded_when_repairs_exhausted(monkeypatch):
    def always_fail_checks(_code, *, settings, context=None):
        return CheckResult(
            ok=False,
            violations=(Violation(CheckStage.syntax, "mock syntax error"),),
        )

    async def fake_chat_completion(_client, _settings, _messages):
        return "still_bad"

    monkeypatch.setattr("app.pipeline.run_all_checks", always_fail_checks)
    monkeypatch.setattr("app.pipeline.chat_completion", fake_chat_completion)

    async def _run():
        async with httpx.AsyncClient() as client:
            return await run_repair_loop(
                client,
                Settings(),
                task_prompt="demo",
                context=None,
                feedback=None,
                initial_code="bad",
                max_repair_attempts=2,
            )

    (
        _final_code,
        attempts,
        all_ok,
        degraded,
        stop_reason,
        repair_used,
        first_ok,
        _log,
    ) = asyncio.run(_run())

    assert len(attempts) == 3  # initial + 2 repairs
    assert all_ok is False
    assert degraded is True
    assert stop_reason == StopReason.max_repairs_exhausted
    assert repair_used == 2
    assert first_ok is False
