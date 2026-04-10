from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.config import Settings


def _ollama_options(settings: Settings) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "num_ctx": settings.num_ctx,
        "num_predict": settings.num_predict,
        "num_batch": settings.num_batch,
        "temperature": settings.temperature,
        "top_p": settings.top_p,
    }
    if settings.ollama_num_gpu:
        opts["num_gpu"] = settings.ollama_num_gpu
    return opts


async def chat_completion(
    client: httpx.AsyncClient,
    settings: Settings,
    messages: list[dict[str, str]],
) -> str:
    url = f"{settings.ollama_host.rstrip('/')}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": False,
        "options": _ollama_options(settings),
    }
    last_err: Exception | None = None
    for attempt in range(settings.ollama_max_retries):
        try:
            r = await client.post(url, json=payload, timeout=settings.ollama_timeout_s)
            r.raise_for_status()
            data = r.json()
            msg = data.get("message") or {}
            content = msg.get("content")
            if not content:
                raise RuntimeError("empty Ollama response")
            return str(content)
        except Exception as e:
            last_err = e
            if attempt + 1 < settings.ollama_max_retries:
                await asyncio.sleep(settings.ollama_retry_backoff_s * (attempt + 1))
            continue
    raise RuntimeError(f"Ollama request failed after retries: {last_err}")


async def ollama_health(client: httpx.AsyncClient, settings: Settings) -> bool:
    url = f"{settings.ollama_host.rstrip('/')}/api/tags"
    try:
        r = await client.get(url, timeout=5.0)
        return r.status_code == 200
    except Exception:
        return False
