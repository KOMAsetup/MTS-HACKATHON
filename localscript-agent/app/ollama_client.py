from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


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
    *,
    timeout_s: float | None = None,
    keep_alive: str | None = None,
    allow_empty_content: bool = False,
) -> str:
    base = settings.ollama_host.rstrip("/")
    url = f"{base}/api/chat"
    payload: dict[str, Any] = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": False,
        "options": _ollama_options(settings),
    }
    if keep_alive is not None:
        payload["keep_alive"] = keep_alive

    timeout = float(timeout_s or settings.ollama_timeout_s)
    last_err: Exception | None = None
    for attempt in range(settings.ollama_max_retries):
        try:
            r = await client.post(url, json=payload, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            msg = data.get("message") or {}
            content = msg.get("content")
            if not content:
                if allow_empty_content:
                    return ""
                raise RuntimeError("empty Ollama response")
            return str(content)
        except Exception as e:
            last_err = e
            if attempt + 1 < settings.ollama_max_retries:
                await asyncio.sleep(settings.ollama_retry_backoff_s * (attempt + 1))
            continue
    raise RuntimeError(f"Ollama request failed after retries: {last_err}")


async def ollama_warmup(client: httpx.AsyncClient, settings: Settings) -> None:
    """Prime model weights (useful right after container start / cold GPU)."""
    _ = await chat_completion(
        client,
        settings,
        [{"role": "user", "content": "ping"}],
        timeout_s=settings.ollama_warmup_timeout_s,
        keep_alive="5m",
        allow_empty_content=True,
    )


async def ollama_tags_payload(
    client: httpx.AsyncClient, settings: Settings
) -> dict[str, Any] | None:
    base = settings.ollama_host.rstrip("/")
    url = f"{base}/api/tags"
    try:
        r = await client.get(url, timeout=settings.ollama_health_timeout_s)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, dict) else None
    except httpx.HTTPError:
        return None
    except Exception:
        logger.exception("ollama_tags_unexpected")
        return None


def _model_names_from_tags(payload: dict[str, Any]) -> list[str]:
    models = payload.get("models") or []
    names: list[str] = []
    if not isinstance(models, list):
        return names
    for item in models:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if isinstance(name, str):
            names.append(name)
    return names


def _model_is_present(want: str, names: list[str]) -> bool:
    if want in names:
        return True
    root = want.split(":", 1)[0]
    return any(n.split(":", 1)[0] == root for n in names)


async def ollama_http_ok_and_model_ready(
    client: httpx.AsyncClient, settings: Settings
) -> tuple[bool, bool]:
    """Return (ollama_http_ok, model_present_in_tags)."""
    payload = await ollama_tags_payload(client, settings)
    if payload is None:
        return False, False
    names = _model_names_from_tags(payload)
    return True, _model_is_present(settings.ollama_model, names)


async def ollama_reachable_and_model_ready(
    client: httpx.AsyncClient, settings: Settings
) -> tuple[bool, bool]:
    """Backward-compatible alias for ``ollama_http_ok_and_model_ready``."""
    return await ollama_http_ok_and_model_ready(client, settings)


async def ollama_health(client: httpx.AsyncClient, settings: Settings) -> bool:
    """Backward-compatible health: True if Ollama responds on /api/tags."""
    payload = await ollama_tags_payload(client, settings)
    return payload is not None
