from __future__ import annotations

import json
import re
from typing import Literal

ExtractKind = Literal["clarification", "code", "parse_error"]


def _strip_json_fence(text: str) -> str:
    s = text.strip()
    fence = re.search(r"```(?:json)?\s*\n([\s\S]*?)\n```", s, re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    return s


def parse_generate_response(raw: str) -> tuple[ExtractKind, str | None, str | None, str | None]:
    """
    Parse Ollama assistant content for structured generate response.

    Returns (kind, question, lua_code, error_detail).
    question set when kind==clarification; lua_code set when kind==code.
    """
    s = _strip_json_fence(raw)
    # Try object starting at first {
    brace = s.find("{")
    if brace >= 0:
        depth = 0
        end = -1
        for i, ch in enumerate(s[brace:], start=brace):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end > brace:
            candidate = s[brace:end]
            try:
                data = json.loads(candidate)
            except json.JSONDecodeError:
                pass
            else:
                if isinstance(data, dict):
                    rk = data.get("response_kind")
                    if rk == "clarification":
                        q = data.get("question")
                        if isinstance(q, str) and q.strip():
                            return "clarification", q.strip(), None, None
                        return "parse_error", None, None, "clarification missing question"
                    if rk == "code":
                        lua = data.get("lua")
                        if isinstance(lua, str):
                            return "code", None, lua, None
                        return "parse_error", None, None, "code missing lua field"
                    return "parse_error", None, None, f"unknown response_kind: {rk!r}"

    return "parse_error", None, None, "no valid JSON object found"


def parse_debug_response(raw: str) -> tuple[str | None, str | None, str | None]:
    """Returns (problem_description, suggested_code, error)."""
    s = _strip_json_fence(raw)
    brace = s.find("{")
    if brace < 0:
        return None, None, "no JSON object"
    depth = 0
    end = -1
    for i, ch in enumerate(s[brace:], start=brace):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end <= brace:
        return None, None, "unbalanced JSON"
    try:
        data = json.loads(s[brace:end])
    except json.JSONDecodeError as e:
        return None, None, str(e)
    if not isinstance(data, dict):
        return None, None, "root must be object"
    pd = data.get("problem_description") or data.get("analysis")
    sc = data.get("suggested_code")
    if isinstance(pd, str) and isinstance(sc, str):
        return pd, sc, None
    return None, None, "missing problem_description or suggested_code"
