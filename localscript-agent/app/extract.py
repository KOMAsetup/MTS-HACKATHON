from __future__ import annotations

import re


def extract_lua(text: str) -> str:
    """Strip markdown fences and lua{...}lua wrappers; return best-effort Lua body."""
    s = text.strip()

    fence = re.search(r"```(?:lua)?\s*\n([\s\S]*?)\n```", s, re.IGNORECASE)
    if fence:
        s = fence.group(1).strip()

    lua_wrap = re.search(r"lua\{([\s\S]*?)\}lua", s, re.IGNORECASE)
    if lua_wrap and "```" not in s:
        return lua_wrap.group(1).strip()

    if s.startswith("```"):
        lines = s.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()

    return s.strip()
