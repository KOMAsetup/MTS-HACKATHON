#!/usr/bin/env python3
"""Interactive CLI against a running LocalScript API (e.g. Docker on :8080)."""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.cli_settings import CliSettings, load_json_context

DEBUG_BUFFER_MAX = 32
REFINE_ALL_HISTORY_MAX_STEPS = 40


def _refine_count(history: list[dict[str, Any]]) -> int:
    return sum(1 for h in history if h.get("type") == "refine")


def _merge_refine_context(
    base: dict[str, Any] | None,
    refine_history: list[dict[str, Any]],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if base:
        out.update(base)
    trimmed = refine_history[-REFINE_ALL_HISTORY_MAX_STEPS:]
    out["refine_all_history"] = trimmed
    return out


def _banner(base_url: str) -> None:
    print(
        "LocalScript demo CLI\n"
        f"  API: {base_url.rstrip('/')}\n"
        "  Type a task and Enter — POST /generate\n"
        "  Commands: /help  /health  /settings  /url <base>  /ctx <file.json>|clear|show\n"
        "            /refine  /refine all  (see /help)\n"
        "            /debug  /debug N  /debug all  /debug clear  /debug on  /debug off  /debug status\n"
        "            /attach on|off|status  (append last code to next /generate as previous_code)\n"
        "            /quit\n"
    )


def _cmd_help() -> None:
    print(
        "Commands:\n"
        "  /help          this text\n"
        "  /health        GET /health\n"
        "  /settings      show effective CLI settings\n"
        "  /url <url>     set base URL for this session\n"
        "  /ctx <path>    load JSON context from file\n"
        "  /ctx clear     drop context\n"
        "  /ctx show      print compact JSON preview\n"
        "  /refine        refine last code (multi-line feedback, empty line to send)\n"
        "  /refine all    after ≥1 /refine: next /refine adds full chain to context.refine_all_history\n"
        "  /debug         print last buffered validation/repair meta (no extra generate)\n"
        "  /debug N       print last N buffer entries (newest last)\n"
        "  /debug all     print full buffer (newest last)\n"
        "  /debug clear   empty the buffer\n"
        "  /debug on|off  ask API for debug JSON on each request (fills buffer)\n"
        "  /debug status  show on/off and buffer size\n"
        "  /attach on|off  next plain prompts send API previous_code=last printed Lua\n"
        "  /attach status  show attach mode and whether last_code exists\n"
        "  /quit          exit\n"
    )


def _read_multiline_feedback() -> str | None:
    print("Feedback (empty line immediately to cancel, or type lines then empty line to send):")
    lines: list[str] = []
    first = input()
    if first == "":
        return None
    lines.append(first)
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    return "\n".join(lines)


def _append_debug_buffer(
    buf: deque[dict[str, Any]],
    *,
    kind: str,
    label: str,
    data: dict[str, Any],
    request_debug: bool,
) -> None:
    if not request_debug:
        return
    entry: dict[str, Any] = {"kind": kind, "label": label}
    if "debug" in data and data["debug"] is not None:
        entry["debug"] = data["debug"]
    else:
        entry["note"] = "response had no debug field (server image may be older than client)"
    buf.append(entry)


def main() -> int:
    parser = argparse.ArgumentParser(description="REPL for LocalScript /generate and /refine")
    parser.add_argument("--base-url", default=None, help="Override LOCALSCRIPT_CLI_BASE_URL")
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Override HTTP timeout (seconds)",
    )
    parser.add_argument(
        "--context-file",
        default=None,
        help="Load JSON context from file (same as LOCALSCRIPT_CLI_DEFAULT_CONTEXT_FILE)",
    )
    parser.add_argument(
        "--no-server-debug",
        action="store_true",
        help="Do not send debug:true by default (use /debug on later)",
    )
    parser.add_argument(
        "--attach-previous-code",
        action="store_true",
        help="Start with attach on: each /generate sends last code as previous_code when available",
    )
    args = parser.parse_args()

    settings = CliSettings()
    if args.base_url:
        settings = settings.model_copy(update={"base_url": args.base_url})
    if args.timeout is not None:
        settings = settings.model_copy(update={"http_timeout_s": args.timeout})
    if args.context_file:
        settings = settings.model_copy(update={"default_context_file": args.context_file})
    if args.no_server_debug:
        settings = settings.model_copy(update={"request_server_debug": False})
    if args.attach_previous_code:
        settings = settings.model_copy(update={"attach_previous_code": True})

    base_url = settings.base_url.rstrip("/")
    timeout = httpx.Timeout(settings.http_timeout_s)
    request_debug: bool = settings.request_server_debug
    attach_previous_code: bool = settings.attach_previous_code
    debug_buffer: deque[dict[str, Any]] = deque(maxlen=DEBUG_BUFFER_MAX)

    context: dict[str, Any] | None = None
    if settings.default_context_file:
        try:
            context = load_json_context(settings.default_context_file)
            print(f"Loaded default context from {settings.default_context_file}")
        except OSError as e:
            print(f"Warning: could not load default context file: {e}", file=sys.stderr)

    last_code: str | None = None
    last_prompt: str | None = None
    session_history: list[dict[str, Any]] = []
    pending_refine_all_chain: bool = False

    _banner(base_url)

    with httpx.Client(timeout=timeout) as client:
        while True:
            try:
                raw = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBye.")
                return 0

            if not raw:
                continue

            if raw in ("/quit", "/exit", "/q"):
                print("Bye.")
                return 0

            if raw == "/help":
                _cmd_help()
                continue

            if raw == "/health":
                try:
                    r = client.get(f"{base_url}/health")
                    r.raise_for_status()
                    print(json.dumps(r.json(), indent=2, ensure_ascii=False))
                except httpx.HTTPError as e:
                    print(f"Error: {e}", file=sys.stderr)
                continue

            if raw == "/settings":
                print(
                    json.dumps(
                        {
                            "base_url": base_url,
                            "http_timeout_s": settings.http_timeout_s,
                            "default_context_file": settings.default_context_file,
                            "active_context": context is not None,
                            "request_server_debug": request_debug,
                            "debug_buffer_len": len(debug_buffer),
                            "attach_previous_code": attach_previous_code,
                            "has_last_code": last_code is not None,
                            "pending_refine_all_chain": pending_refine_all_chain,
                            "session_history_steps": len(session_history),
                            "refine_steps": _refine_count(session_history),
                        },
                        indent=2,
                        ensure_ascii=False,
                    )
                )
                continue

            if raw.startswith("/url "):
                base_url = raw[5:].strip().rstrip("/")
                print(f"Base URL set to {base_url}")
                continue

            if raw.startswith("/ctx "):
                arg = raw[5:].strip()
                if arg.lower() == "clear":
                    context = None
                    print("Context cleared.")
                elif arg.lower() == "show":
                    if context is None:
                        print("(no context)")
                    else:
                        preview = json.dumps(context, ensure_ascii=False, indent=2)
                        if len(preview) > 4000:
                            print(preview[:4000] + "\n… (truncated)")
                        else:
                            print(preview)
                else:
                    try:
                        context = load_json_context(arg)
                        print(f"Context loaded from {arg}")
                    except (OSError, ValueError) as e:
                        print(f"Error: {e}", file=sys.stderr)
                continue

            if raw == "/debug":
                if not debug_buffer:
                    print("(debug buffer empty)")
                else:
                    print(json.dumps(debug_buffer[-1], indent=2, ensure_ascii=False))
                continue

            if raw == "/debug all":
                if not debug_buffer:
                    print("(debug buffer empty)")
                else:
                    print(json.dumps(list(debug_buffer), indent=2, ensure_ascii=False))
                continue

            if raw == "/debug clear":
                debug_buffer.clear()
                print("Debug buffer cleared.")
                continue

            if raw == "/debug on":
                request_debug = True
                print("Will send debug:true on generate/refine (buffer fills on each reply).")
                continue

            if raw == "/debug off":
                request_debug = False
                print("Will not send debug:true (buffer only gets notes on next calls).")
                continue

            if raw == "/debug status":
                print(
                    f"request_server_debug={request_debug!r}  buffer_entries={len(debug_buffer)}"
                )
                continue

            if raw.startswith("/debug ") and len(raw) > 7:
                rest = raw[7:].strip()
                if rest.isdigit():
                    n = int(rest)
                    if n < 1:
                        print("Use positive n for /debug N.", file=sys.stderr)
                        continue
                    if not debug_buffer:
                        print("(debug buffer empty)")
                        continue
                    buf_list = list(debug_buffer)
                    tail = buf_list[-min(n, len(buf_list)) :]
                    print(json.dumps(tail, indent=2, ensure_ascii=False))
                    continue

            if raw.startswith("/debug"):
                print("Unknown /debug subcommand. See /help.", file=sys.stderr)
                continue

            if raw == "/attach on":
                attach_previous_code = True
                print("Attach on: next /generate will include previous_code when last code exists.")
                continue

            if raw == "/attach off":
                attach_previous_code = False
                print("Attach off: /generate sends only your prompt (no automatic previous_code).")
                continue

            if raw == "/attach status":
                print(
                    f"attach_previous_code={attach_previous_code!r}  "
                    f"last_code={'yes' if last_code else 'no'}"
                )
                continue

            if raw.startswith("/attach"):
                print("Use /attach on, /attach off, or /attach status.", file=sys.stderr)
                continue

            if raw == "/refine all":
                if _refine_count(session_history) < 1:
                    print(
                        "Неверная команда: нет истории /refine. "
                        "Сначала выполните обычный /refine с правками.",
                        file=sys.stderr,
                    )
                    continue
                pending_refine_all_chain = True
                print(
                    "Включено: при следующем /refine в context попадёт refine_all_history "
                    f"({len(session_history)} шагов, последние {REFINE_ALL_HISTORY_MAX_STEPS} "
                    "если длиннее)."
                )
                continue

            if raw == "/refine":
                if not last_code or not last_prompt:
                    print("Nothing to refine yet — run a normal prompt first.", file=sys.stderr)
                    continue
                fb = _read_multiline_feedback()
                if fb is None:
                    print("Cancelled.")
                    continue
                use_chain = pending_refine_all_chain
                if use_chain:
                    ctx_body = _merge_refine_context(context, session_history)
                    print(
                        f"[refine all] refine_all_history: "
                        f"{len(ctx_body.get('refine_all_history', []))} шагов",
                        file=sys.stderr,
                    )
                else:
                    ctx_body = context

                body = {
                    "prompt": last_prompt,
                    "previous_code": last_code,
                    "feedback": fb,
                    "context": ctx_body,
                }
                if request_debug:
                    body["debug"] = True
                try:
                    r = client.post(f"{base_url}/refine", json=body)
                    r.raise_for_status()
                    data = r.json()
                    code = data.get("code", "")
                    print("--- code ---")
                    print(code)
                    print("--- end ---")
                    _append_debug_buffer(
                        debug_buffer,
                        kind="refine",
                        label=last_prompt[:80],
                        data=data,
                        request_debug=request_debug,
                    )
                    last_code = code
                    session_history.append(
                        {
                            "type": "refine",
                            "prompt": last_prompt,
                            "feedback": fb,
                            "code": code,
                        }
                    )
                    if use_chain:
                        pending_refine_all_chain = False
                except httpx.HTTPError as e:
                    print(f"Error: {e}", file=sys.stderr)
                    if isinstance(e, httpx.HTTPStatusError) and e.response is not None:
                        print(e.response.text[:2000], file=sys.stderr)
                continue

            if raw.startswith("/"):
                print("Unknown command. Type /help", file=sys.stderr)
                continue

            prompt = raw
            body: dict[str, Any] = {"prompt": prompt, "context": context}
            if attach_previous_code and last_code is not None:
                body["previous_code"] = last_code
                print("[attach] previous_code sent", file=sys.stderr)
            elif attach_previous_code:
                print("[attach] no last code yet, plain generate", file=sys.stderr)
            if request_debug:
                body["debug"] = True
            try:
                r = client.post(f"{base_url}/generate", json=body)
                r.raise_for_status()
                data = r.json()
                code = data.get("code", "")
                print("--- code ---")
                print(code)
                print("--- end ---")
                _append_debug_buffer(
                    debug_buffer,
                    kind="generate",
                    label=prompt[:120],
                    data=data,
                    request_debug=request_debug,
                )
                last_code = code
                last_prompt = prompt
                session_history = [
                    {
                        "type": "generate",
                        "prompt": prompt,
                        "code": code,
                    }
                ]
                pending_refine_all_chain = False
            except httpx.HTTPError as e:
                print(f"Error: {e}", file=sys.stderr)
                if isinstance(e, httpx.HTTPStatusError) and e.response is not None:
                    print(e.response.text[:2000], file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
