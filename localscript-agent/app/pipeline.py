from __future__ import annotations

import json

import httpx

from app.code_checks import CheckResult, log_check_outcome, result_to_check_items, run_all_checks
from app.config import Settings
from app.extract import extract_lua
from app.generate_parse import parse_debug_response, parse_generate_response
from app.models_io import (
    AttemptRecord,
    DebugHistoryTurn,
    DebugRequest,
    DebugResponse,
    GenerateRequest,
    GenerateResponse,
    RefineRequest,
    ResponseKind,
    StopReason,
)
from app.ollama_client import chat_completion
from app.prompts import (
    build_debug_user_message,
    build_generate_user_message,
    build_refinement_user_message,
    messages_for_chat,
    messages_for_debug_chat,
    messages_for_generate_chat,
    repair_user_message_compact,
)


def effective_max_repair(settings: Settings, override: int | None) -> int:
    cap = settings.max_repair_server_cap
    if override is not None:
        return min(override, cap)
    return min(settings.max_repair_attempts, cap)


def _extract_context_from_prompt(prompt: str) -> dict | None:
    marker = "\n\nContext:\n"
    pos = prompt.find(marker)
    if pos < 0:
        return None
    raw = prompt[pos + len(marker) :].strip()
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


async def run_repair_loop(
    client: httpx.AsyncClient,
    settings: Settings,
    *,
    task_prompt: str,
    context: dict | None,
    feedback: str | None,
    initial_code: str,
    max_repair_attempts: int,
) -> tuple[
    str,
    list[AttemptRecord],
    bool,
    bool,
    StopReason,
    int,
    bool,
    list[str],
]:
    """
    Validate initial_code and optionally run repair LLM rounds.

    Returns:
        final_code, attempts, all_checks_passed, degraded, stop_reason,
        repair_rounds_used, first_validation_ok, log
    """
    log: list[str] = []
    attempts: list[AttemptRecord] = []
    code = initial_code.strip()
    result = run_all_checks(code, settings=settings, context=context)
    first_validation_ok = result.ok
    attempts.append(
        AttemptRecord(
            index=0,
            kind="initial",
            code=code,
            checks=result_to_check_items(result),
        )
    )

    if result.ok:
        log.append("validate: pass (initial)")
        log_check_outcome(outcome="pass", violations=(), repair_attempt=None)
        return (
            code,
            attempts,
            True,
            False,
            StopReason.validation_ok,
            0,
            first_validation_ok,
            log,
        )

    log.append(f"validate: fail initial: {'; '.join(result.error_lines())}")
    log_check_outcome(outcome="fail", violations=result.violations, repair_attempt=None)

    repair_rounds_used = 0
    for i in range(max_repair_attempts):
        repair_msg = repair_user_message_compact(
            task_prompt=task_prompt,
            context=context,
            broken_code=code,
            error_lines=result.error_lines(),
            feedback=feedback,
        )
        repair_messages = messages_for_chat(repair_msg, include_few_shot=False)
        raw = await chat_completion(client, settings, repair_messages)
        repair_rounds_used += 1
        code = extract_lua(raw)
        result = run_all_checks(code, settings=settings, context=context)
        attempts.append(
            AttemptRecord(
                index=repair_rounds_used,
                kind="repair",
                code=code,
                checks=result_to_check_items(result),
            )
        )
        if result.ok:
            log.append(f"validate: pass after repair {repair_rounds_used}")
            log_check_outcome(outcome="pass", violations=(), repair_attempt=repair_rounds_used)
            return (
                code,
                attempts,
                True,
                False,
                StopReason.validation_ok,
                repair_rounds_used,
                first_validation_ok,
                log,
            )
        log.append(f"validate: fail repair {repair_rounds_used}: {'; '.join(result.error_lines())}")
        log_check_outcome(
            outcome="fail",
            violations=result.violations,
            repair_attempt=repair_rounds_used,
        )

    log.append("validate: returning last attempt despite errors")
    log_check_outcome(outcome="fail_final", violations=result.violations, repair_attempt=None)
    return (
        code,
        attempts,
        False,
        True,
        StopReason.max_repairs_exhausted,
        repair_rounds_used,
        first_validation_ok,
        log,
    )


async def run_generate_pipeline(
    client: httpx.AsyncClient,
    settings: Settings,
    body: GenerateRequest,
) -> GenerateResponse:
    clarification_mode = settings.clarification_mode
    user_msg = build_generate_user_message(
        body.prompt,
        body.clarification_history,
    )
    messages = messages_for_generate_chat(user_msg, clarification_mode=clarification_mode)
    raw = await chat_completion(client, settings, messages)

    kind, question, lua, parse_err = parse_generate_response(raw)
    if kind == "clarification" and question:
        return GenerateResponse(
            response_kind=ResponseKind.clarification,
            clarification_question=question,
            code=None,
            attempts=[],
            all_checks_passed=None,
            degraded=None,
            stop_reason=None,
            llm_rounds=1,
            repair_rounds_used=0,
        )

    parse_warning: str | None = None
    if kind == "parse_error":
        lua = extract_lua(raw)
        parse_warning = f"JSON parse failed ({parse_err}); used extract_lua fallback"
    elif kind == "code":
        lua = lua or ""

    if not lua or not str(lua).strip():
        raise ValueError("empty Lua after generate parse and extract_lua fallback")

    context = _extract_context_from_prompt(body.prompt)
    max_r = effective_max_repair(settings, body.max_repair_attempts)
    (
        final_code,
        attempts,
        all_ok,
        degraded,
        stop_reason,
        repair_used,
        _first_ok,
        _log,
    ) = await run_repair_loop(
        client,
        settings,
        task_prompt=body.prompt,
        context=context,
        feedback=None,
        initial_code=str(lua).strip(),
        max_repair_attempts=max_r,
    )

    return GenerateResponse(
        response_kind=ResponseKind.code,
        code=final_code,
        attempts=attempts,
        all_checks_passed=all_ok,
        degraded=degraded,
        stop_reason=stop_reason,
        llm_rounds=1 + repair_used,
        repair_rounds_used=repair_used,
        parse_warning=parse_warning,
    )


async def run_refine_pipeline(
    client: httpx.AsyncClient,
    settings: Settings,
    body: RefineRequest,
) -> GenerateResponse:
    user_msg = build_refinement_user_message(
        body.prompt,
        body.refinement_history,
    )
    messages = messages_for_chat(user_msg, include_few_shot=True)
    raw = await chat_completion(client, settings, messages)
    code = extract_lua(raw)
    if not code or not code.strip():
        raise ValueError("empty Lua after refine generation")

    context = _extract_context_from_prompt(body.prompt)
    feedback = body.refinement_history[-1].user_feedback
    max_r = effective_max_repair(settings, body.max_repair_attempts)
    (
        final_code,
        attempts,
        all_ok,
        degraded,
        stop_reason,
        repair_used,
        _first_ok,
        _log,
    ) = await run_repair_loop(
        client,
        settings,
        task_prompt=body.prompt,
        context=context,
        feedback=feedback,
        initial_code=code.strip(),
        max_repair_attempts=max_r,
    )

    return GenerateResponse(
        response_kind=ResponseKind.code,
        code=final_code,
        attempts=attempts,
        all_checks_passed=all_ok,
        degraded=degraded,
        stop_reason=stop_reason,
        llm_rounds=1 + repair_used,
        repair_rounds_used=repair_used,
    )


def _checks_text_for_debug(result: CheckResult) -> str:
    """Compact summary for the debug LLM prompt (not the full checks array)."""
    if result.ok:
        return "all_checks_passed: true"
    lines = ["all_checks_passed: false", "Failed checks:"]
    lines.extend(f"- {line}" for line in result.error_lines())
    return "\n".join(lines)


async def run_debug_pipeline(
    client: httpx.AsyncClient,
    settings: Settings,
    body: DebugRequest,
) -> DebugResponse:
    result = run_all_checks(body.code, settings=settings)
    checks = result_to_check_items(result)
    hist: list[DebugHistoryTurn] = list(body.debug_history)
    checks_text = _checks_text_for_debug(result)
    user_msg = build_debug_user_message(body.code, body.prompt, hist, checks_text)
    messages = messages_for_debug_chat(user_msg)
    raw = await chat_completion(client, settings, messages)
    problem, suggested, err = parse_debug_response(raw)
    if err or problem is None or suggested is None:
        raise ValueError(f"debug response parse failed: {err or 'missing fields'}")
    if not str(suggested).strip():
        suggested = body.code.strip()
    if not str(problem).strip():
        problem = "No textual analysis returned; treating suggested_code as echo of input."
    return DebugResponse(
        checks=checks,
        all_checks_passed=result.ok,
        problem_description=problem,
        suggested_code=suggested,
    )
