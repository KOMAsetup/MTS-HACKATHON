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

RESPONSE_LOG_BUFFER_MAX = 25


def _banner(base_url: str) -> None:
    print(
        "LocalScript demo CLI\n"
        f"  API: {base_url.rstrip('/')}\n"
        "  Plain line — POST /generate (new task; local refine chain reset)\n"
        "  Commands: /help  /health  /settings  /url <base>\n"
        "            /ctx <file.json>|clear|show  (merge JSON into prompt as Context:)\n"
        "            /verbose on|off|status\n"
        "            /log [N|all|clear]  (last N full JSON responses; max "
        f"{RESPONSE_LOG_BUFFER_MAX})\n"
        "            /refine  (multi-line feedback; uses refinement_history)\n"
        "            /debug …          POST /debug (см. README «Демо CLI: команда /debug»)\n"
        "            /debug new        сброс debug_history и подсказки suggestion\n"
        "            /quit\n"
    )


def _cmd_help() -> None:
    print(
        "Commands:\n"
        "  /help           this text\n"
        "  /health         GET /health\n"
        "  /settings       effective CLI settings\n"
        "  /url <url>      base URL for this session\n"
        "  /ctx …          load/show/clear JSON merged into generate prompt\n"
        "  /verbose on|off|status   verbose prints full JSON after each call\n"
        "  /log [N|all|clear]      ring buffer of full server JSON (generate/refine/debug)\n"
        "  /refine         refine last code (multi-line feedback, empty line to cancel)\n"
        "  /debug …        POST /debug — подробности в README (раздел «Демо CLI: команда /debug»)\n"
        "  /debug new      сброс debug_history и last_debug_suggested_code\n"
        "  /quit           exit\n"
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


def _read_lua_for_debug(
    *,
    last_debug_suggested: str | None,
    last_assistant_code: str | None,
) -> str | None:
    print("Lua >")
    first = input()
    if first == "":
        if last_debug_suggested and last_debug_suggested.strip():
            return last_debug_suggested.strip()
        if last_assistant_code and last_assistant_code.strip():
            return last_assistant_code.strip()
        print("Нечего подставить — отмена.", file=sys.stderr)
        return None
    lines = [first]
    while True:
        line = input()
        if line == "":
            break
        lines.append(line)
    return "\n".join(lines)


def _read_optional_problem_note() -> str | None:
    print("Вопрос (пустая строка — пропуск):")
    first = input()
    if not first.strip():
        return None
    out: list[str] = [first]
    while True:
        line = input()
        if line == "":
            break
        out.append(line)
    return "\n".join(out)


def _merge_context_into_prompt(prompt: str, context: dict[str, Any] | None) -> str:
    if not context:
        return prompt
    return (
        f"{prompt}\n\nContext:\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )


def _final_checks_from_response(data: dict[str, Any]) -> list[dict[str, Any]]:
    attempts = data.get("attempts") or []
    if not attempts:
        return []
    last = attempts[-1]
    return last.get("checks") or []


def _print_response_summary(data: dict[str, Any], *, verbose: bool) -> None:
    if verbose:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return
    rk = data.get("response_kind")
    if rk == "clarification":
        print("--- clarification ---")
        print(data.get("clarification_question") or "")
        return
    code = data.get("code") or ""
    print("--- code ---")
    print(code)
    print("--- end ---")
    if rk == "code":
        if not data.get("all_checks_passed", True):
            print(
                "Warning: not all static checks passed.",
                file=sys.stderr,
            )
            failed = [
                c
                for c in (_final_checks_from_response(data) or [])
                if not c.get("passed", True)
            ]
            for c in failed:
                print(
                    f"  [{c.get('stage')}] {c.get('message', '')}",
                    file=sys.stderr,
                )
        if data.get("degraded"):
            print("Warning: degraded=true (repairs exhausted with remaining issues).", file=sys.stderr)


def _append_log(buf: deque[dict[str, Any]], entry: dict[str, Any]) -> None:
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
        "--verbose",
        action="store_true",
        help="Start with verbose on (full JSON after each request)",
    )
    args = parser.parse_args()

    settings = CliSettings()
    if args.base_url:
        settings = settings.model_copy(update={"base_url": args.base_url})
    if args.timeout is not None:
        settings = settings.model_copy(update={"http_timeout_s": args.timeout})
    if args.context_file:
        settings = settings.model_copy(update={"default_context_file": args.context_file})
    if args.verbose:
        settings = settings.model_copy(update={"verbose": True})

    base_url = settings.base_url.rstrip("/")
    timeout = httpx.Timeout(settings.http_timeout_s)
    verbose: bool = settings.verbose
    response_log: deque[dict[str, Any]] = deque(maxlen=RESPONSE_LOG_BUFFER_MAX)

    context: dict[str, Any] | None = None
    if settings.default_context_file:
        try:
            context = load_json_context(settings.default_context_file)
            print(f"Loaded default context from {settings.default_context_file}")
        except OSError as e:
            print(f"Warning: could not load default context file: {e}", file=sys.stderr)

    last_code: str | None = None
    last_prompt: str | None = None
    last_checks: list[dict[str, Any]] | None = None
    refinement_chain: list[dict[str, Any]] = []
    clarification_history: list[dict[str, str]] = []
    debug_history: list[dict[str, Any]] = []
    # Last POST /debug suggested_code — подставляется при пустом вводе Lua и в /debug <prompt>
    last_debug_suggested_code: str | None = None

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
                            "verbose": verbose,
                            "response_log_entries": len(response_log),
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

            if raw == "/verbose on":
                verbose = True
                print("verbose=true")
                continue
            if raw == "/verbose off":
                verbose = False
                print("verbose=false")
                continue
            if raw == "/verbose status":
                print(f"verbose={verbose!r}")
                continue

            if raw == "/log" or raw == "/log 1":
                if not response_log:
                    print("(log empty)")
                else:
                    print(json.dumps(response_log[-1], indent=2, ensure_ascii=False))
                continue

            if raw == "/log all":
                if not response_log:
                    print("(log empty)")
                else:
                    print(json.dumps(list(response_log), indent=2, ensure_ascii=False))
                continue

            if raw == "/log clear":
                response_log.clear()
                print("Log cleared.")
                continue

            if raw.startswith("/log ") and len(raw) > 5:
                rest = raw[5:].strip()
                if rest.isdigit():
                    n = int(rest)
                    if n < 1:
                        print("Use positive n for /log N.", file=sys.stderr)
                        continue
                    if not response_log:
                        print("(log empty)")
                        continue
                    buf_list = list(response_log)
                    tail = buf_list[-min(n, len(buf_list)) :]
                    print(json.dumps(tail, indent=2, ensure_ascii=False))
                    continue

            if raw == "/debug new":
                debug_history.clear()
                last_debug_suggested_code = None
                print("debug_history and last debug suggestion cleared.")
                continue

            if raw == "/debug" or raw.startswith("/debug "):
                note: str | None
                code_for_debug: str | None
                if raw == "/debug":
                    code_for_debug = _read_lua_for_debug(
                        last_debug_suggested=last_debug_suggested_code,
                        last_assistant_code=last_code,
                    )
                    if code_for_debug is None:
                        continue
                    note = _read_optional_problem_note()
                else:
                    rest = raw[6:].strip()
                    if not rest:
                        print("Use /debug alone for interactive input, or /debug <text> with a prompt.", file=sys.stderr)
                        continue
                    if last_debug_suggested_code and last_debug_suggested_code.strip():
                        code_for_debug = last_debug_suggested_code.strip()
                    elif last_code and last_code.strip():
                        code_for_debug = last_code.strip()
                    else:
                        print(
                            "No code to reuse for shortcut. Run /generate or /debug with pasted Lua first.",
                            file=sys.stderr,
                        )
                        continue
                    note = rest
                body: dict[str, Any] = {
                    "code": code_for_debug,
                    "debug_history": debug_history,
                }
                if note:
                    body["prompt"] = note
                try:
                    r = client.post(f"{base_url}/debug", json=body)
                    r.raise_for_status()
                    data = r.json()
                    _append_log(response_log, {"kind": "debug", "response": data})
                    if verbose:
                        print(json.dumps(data, indent=2, ensure_ascii=False))
                    else:
                        print("--- problem_description ---")
                        print(data.get("problem_description", ""))
                        print("--- suggested_code ---")
                        print(data.get("suggested_code", ""))
                        print("--- end ---")
                    sug_raw = (data.get("suggested_code") or "").strip()
                    sug_store = sug_raw if sug_raw else (code_for_debug or "").strip()
                    turn = {
                        "user_code": code_for_debug,
                        "user_prompt": note,
                        "checks": data.get("checks", []),
                        "problem_description": data.get("problem_description", ""),
                        "suggested_code": sug_store,
                    }
                    debug_history.append(turn)
                    if sug_raw:
                        last_debug_suggested_code = sug_raw
                    elif last_debug_suggested_code:
                        pass
                    else:
                        last_debug_suggested_code = sug_store or None
                except httpx.HTTPError as e:
                    print(f"Error: {e}", file=sys.stderr)
                    if isinstance(e, httpx.HTTPStatusError) and e.response is not None:
                        print(e.response.text[:2000], file=sys.stderr)
                continue

            if raw == "/refine":
                if not last_code or not last_prompt or last_checks is None:
                    print(
                        "Nothing to refine yet — run a successful code generate first.",
                        file=sys.stderr,
                    )
                    continue
                fb = _read_multiline_feedback()
                if fb is None:
                    print("Cancelled.")
                    continue
                code_before = last_code
                checks_before = last_checks
                hist = refinement_chain + [
                    {
                        "assistant_code": code_before,
                        "user_feedback": fb,
                        "checks": checks_before,
                    }
                ]
                body = {
                    "prompt": last_prompt,
                    "refinement_history": hist,
                }
                try:
                    r = client.post(f"{base_url}/refine", json=body)
                    r.raise_for_status()
                    data = r.json()
                    _append_log(response_log, {"kind": "refine", "response": data})
                    _print_response_summary(data, verbose=verbose)
                    refinement_chain.append(
                        {
                            "assistant_code": code_before,
                            "user_feedback": fb,
                            "checks": checks_before,
                        }
                    )
                    last_code = data.get("code") or ""
                    last_checks = _final_checks_from_response(data)
                    last_debug_suggested_code = None
                except httpx.HTTPError as e:
                    print(f"Error: {e}", file=sys.stderr)
                    if isinstance(e, httpx.HTTPStatusError) and e.response is not None:
                        print(e.response.text[:2000], file=sys.stderr)
                continue

            if raw.startswith("/"):
                print("Unknown command. Type /help", file=sys.stderr)
                continue

            prompt = _merge_context_into_prompt(raw, context)
            body: dict[str, Any] = {
                "prompt": prompt,
                "clarification_history": clarification_history,
            }
            try:
                while True:
                    r = client.post(f"{base_url}/generate", json=body)
                    r.raise_for_status()
                    data = r.json()
                    _append_log(response_log, {"kind": "generate", "response": data})
                    rk = data.get("response_kind")
                    if rk == "clarification":
                        q = data.get("clarification_question") or ""
                        _print_response_summary(data, verbose=verbose)
                        if not verbose:
                            print("--- clarification ---")
                            print(q)
                        ans = input("Your answer (empty to skip): ").strip()
                        if not ans:
                            break
                        clarification_history.append(
                            {"model_question": q, "user_answer": ans}
                        )
                        body = {
                            "prompt": prompt,
                            "clarification_history": clarification_history,
                        }
                        continue

                    _print_response_summary(data, verbose=verbose)
                    last_code = data.get("code") or ""
                    last_prompt = prompt
                    last_checks = _final_checks_from_response(data)
                    refinement_chain = []
                    clarification_history = []
                    debug_history.clear()
                    last_debug_suggested_code = None
                    break
            except httpx.HTTPError as e:
                print(f"Error: {e}", file=sys.stderr)
                if isinstance(e, httpx.HTTPStatusError) and e.response is not None:
                    print(e.response.text[:2000], file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
