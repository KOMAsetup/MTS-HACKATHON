from __future__ import annotations

import httpx

from app.config import Settings
from app.extract import extract_lua
from app.ollama_client import chat_completion
from app.prompts import build_user_message, messages_for_chat, repair_user_message
from app.validate import validate_code


async def generate_lua(
    client: httpx.AsyncClient,
    settings: Settings,
    prompt: str,
    context: dict | None = None,
    previous_code: str | None = None,
    feedback: str | None = None,
) -> tuple[str, list[str]]:
    """
    Full loop: build prompt -> Ollama -> extract -> validate -> optional repair.
    Returns (final_code, log_lines).
    """
    log: list[str] = []
    user_content = build_user_message(prompt, context, previous_code, feedback)
    messages = messages_for_chat(user_content, include_few_shot=True)
    raw = await chat_completion(client, settings, messages)
    code = extract_lua(raw)
    ok, errs = validate_code(code, luac_path=settings.luac_path)
    if ok:
        log.append("validate: pass (initial)")
        return code, log

    log.append(f"validate: fail initial: {'; '.join(errs)}")
    for i in range(settings.max_repair_attempts):
        repair_msg = repair_user_message(code, "; ".join(errs))
        repair_messages = messages_for_chat(repair_msg, include_few_shot=False)
        raw = await chat_completion(client, settings, repair_messages)
        code = extract_lua(raw)
        ok, errs = validate_code(code, luac_path=settings.luac_path)
        if ok:
            log.append(f"validate: pass after repair {i + 1}")
            return code, log
        log.append(f"validate: fail repair {i + 1}: {'; '.join(errs)}")

    log.append("validate: returning last attempt despite errors")
    return code, log
