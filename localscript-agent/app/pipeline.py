from __future__ import annotations

import httpx

from app.code_checks import log_check_outcome, run_all_checks
from app.config import Settings
from app.extract import extract_lua
from app.models_io import GenerateDebugMeta
from app.ollama_client import chat_completion
from app.prompts import build_user_message, messages_for_chat, repair_user_message_compact


async def generate_lua(
    client: httpx.AsyncClient,
    settings: Settings,
    prompt: str,
    context: dict | None = None,
    previous_code: str | None = None,
    feedback: str | None = None,
    *,
    return_debug: bool = False,
) -> tuple[str, list[str], GenerateDebugMeta | None]:
    """
    Full loop: build prompt -> Ollama -> extract -> static checks -> optional repair.
    Returns (final_code, log_lines, debug_meta or None).
    """
    log: list[str] = []
    llm_rounds = 0
    repair_rounds_used = 0

    user_content = build_user_message(prompt, context, previous_code, feedback)
    messages = messages_for_chat(user_content, include_few_shot=True)
    raw = await chat_completion(client, settings, messages)
    llm_rounds += 1
    code = extract_lua(raw)
    result = run_all_checks(code, settings=settings, context=context)
    first_validation_ok = result.ok

    if result.ok:
        log.append("validate: pass (initial)")
        log_check_outcome(outcome="pass", violations=(), repair_attempt=None)
        meta = (
            _debug_meta(
                first_validation_ok=first_validation_ok,
                final_validation_ok=True,
                llm_rounds=llm_rounds,
                repair_rounds_used=0,
                settings=settings,
                log=log,
            )
            if return_debug
            else None
        )
        return code, log, meta

    log.append(f"validate: fail initial: {'; '.join(result.error_lines())}")
    log_check_outcome(outcome="fail", violations=result.violations, repair_attempt=None)

    for i in range(settings.max_repair_attempts):
        repair_msg = repair_user_message_compact(
            task_prompt=prompt,
            context=context,
            broken_code=code,
            error_lines=result.error_lines(),
            feedback=feedback,
        )
        repair_messages = messages_for_chat(repair_msg, include_few_shot=False)
        raw = await chat_completion(client, settings, repair_messages)
        llm_rounds += 1
        repair_rounds_used += 1
        code = extract_lua(raw)
        result = run_all_checks(code, settings=settings, context=context)
        if result.ok:
            log.append(f"validate: pass after repair {i + 1}")
            log_check_outcome(outcome="pass", violations=(), repair_attempt=i + 1)
            meta = (
                _debug_meta(
                    first_validation_ok=first_validation_ok,
                    final_validation_ok=True,
                    llm_rounds=llm_rounds,
                    repair_rounds_used=repair_rounds_used,
                    settings=settings,
                    log=log,
                )
                if return_debug
                else None
            )
            return code, log, meta
        log.append(f"validate: fail repair {i + 1}: {'; '.join(result.error_lines())}")
        log_check_outcome(outcome="fail", violations=result.violations, repair_attempt=i + 1)

    log.append("validate: returning last attempt despite errors")
    log_check_outcome(outcome="fail_final", violations=result.violations, repair_attempt=None)
    meta = (
        _debug_meta(
            first_validation_ok=first_validation_ok,
            final_validation_ok=False,
            llm_rounds=llm_rounds,
            repair_rounds_used=repair_rounds_used,
            settings=settings,
            log=log,
        )
        if return_debug
        else None
    )
    return code, log, meta


def _debug_meta(
    *,
    first_validation_ok: bool,
    final_validation_ok: bool,
    llm_rounds: int,
    repair_rounds_used: int,
    settings: Settings,
    log: list[str],
) -> GenerateDebugMeta:
    return GenerateDebugMeta(
        first_validation_ok=first_validation_ok,
        final_validation_ok=final_validation_ok,
        llm_rounds=llm_rounds,
        repair_rounds_used=repair_rounds_used,
        max_repair_attempts=settings.max_repair_attempts,
        degraded=not final_validation_ok,
        log=list(log),
    )
