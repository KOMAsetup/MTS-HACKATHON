from __future__ import annotations

import re
from typing import Literal

State = Literal["code", "sq", "dq", "long", "line_comment", "block_comment"]


def extract_lua_code(text: str) -> str:
    """Extract executable Lua from model output.

    Order:
    1) Outermost ``lua{...}lua`` wrapper (brace-balanced; ignores braces in strings/comments).
    2) First fenced ``` / ```lua block.
    3) Plain stripped text.
    """
    stripped = text.strip()
    if not stripped:
        return stripped

    unwrapped = _unwrap_outer_lua_block(stripped)
    if unwrapped is not None:
        return unwrapped.strip()

    fence = _extract_first_markdown_fence(stripped)
    if fence is not None:
        return fence.strip()

    return stripped


def extract_lua(text: str) -> str:
    """Backward-compatible alias used across the codebase."""
    return extract_lua_code(text)


def _extract_first_markdown_fence(text: str) -> str | None:
    match = re.search(r"```(?:lua)?\s*\n?(.*?)```", text, flags=re.S | re.I)
    if match:
        return match.group(1)
    return None


def _unwrap_outer_lua_block(text: str) -> str | None:
    """If *text* is a single outer ``lua{ ... }lua`` envelope, return inner part."""
    if not (text.startswith("lua{") and text.endswith("}lua")):
        return None
    inner = _balanced_inner_after_lua_prefix(text)
    if inner is None:
        return None
    return inner


def _balanced_inner_after_lua_prefix(text: str) -> str | None:
    """text starts with ``lua{`` and ends with ``}lua``; find inner using bracket depth."""
    n = len(text)
    if n < 8:
        return None
    i = 4  # char after ``lua{``
    depth = 1
    state: State = "code"
    long_eq = 0

    while i < n:
        ch = text[i]

        if state == "line_comment":
            if ch in "\n\r":
                state = "code"
            i += 1
            continue

        if state == "block_comment":
            end_seq = "]" + ("=" * long_eq) + "]"
            if text.startswith(end_seq, i):
                i += len(end_seq)
                state = "code"
                continue
            i += 1
            continue

        if state == "sq":
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == "'":
                state = "code"
            i += 1
            continue

        if state == "dq":
            if ch == "\\" and i + 1 < n:
                i += 2
                continue
            if ch == '"':
                state = "code"
            i += 1
            continue

        if state == "long":
            end_seq = "]" + ("=" * long_eq) + "]"
            if text.startswith(end_seq, i):
                i += len(end_seq)
                state = "code"
                continue
            i += 1
            continue

        # state == code
        if ch == "-" and text.startswith("--", i):
            j = i + 2
            if j < n and text[j] == "[":
                k = j + 1
                eq = 0
                while k < n and text[k] == "=":
                    eq += 1
                    k += 1
                if k < n and text[k] == "[":
                    long_eq = eq
                    state = "block_comment"
                    i = k + 1
                    continue
            state = "line_comment"
            i += 2
            continue

        if ch == "'":
            state = "sq"
            i += 1
            continue
        if ch == '"':
            state = "dq"
            i += 1
            continue
        if ch == "[":
            k = i + 1
            eq = 0
            while k < n and text[k] == "=":
                eq += 1
                k += 1
            if k < n and text[k] == "[":
                long_eq = eq
                state = "long"
                i = k + 1
                continue

        if ch == "{":
            depth += 1
            i += 1
            continue
        if ch == "}":
            depth -= 1
            if depth == 0:
                if text.startswith("lua", i + 1) and i + 4 == n:
                    return text[4:i]
                return None
            i += 1
            continue

        i += 1

    return None
