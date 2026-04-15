from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

FORBIDDEN_PATTERNS = [
    r"\brequire\s*\(",
    r"\bdofile\s*\(",
    r"\bloadfile\s*\(",
    r"\bload\s*\(",
    r"\bio\.",
    # Allow os.time / os.date / os.difftime for timestamps; block risky os APIs.
    r"\bos\.execute\b",
    r"\bos\.exit\b",
    r"\bos\.remove\b",
    r"\bos\.rename\b",
    r"\bos\.getenv\b",
    r"\bos\.setlocale\b",
    r"\bos\.tmpname\b",
    # Block package loaders; allow a local variable named `package` (e.g. loop iterator).
    r"\bpackage\.load\b",
    r"\bpackage\.preload\b",
    r"\bpackage\.loaded\b",
    r"\bpackage\.searchers\b",
    r"\bpackage\.path\b",
    r"\bpackage\.cpath\b",
    r"\bpackage\.config\b",
    r"\bdebug\.",
]


def static_guard_violations(code: str) -> list[str]:
    """Return forbidden-pattern matches for potentially unsafe Lua code."""
    violations: list[str] = []
    for pat in FORBIDDEN_PATTERNS:
        if re.search(pat, code, re.IGNORECASE):
            violations.append(f"forbidden pattern: {pat}")
    return violations


def luac_check(code: str, luac_path: str = "luac") -> tuple[bool, str]:
    """Run luac parser check and return success flag plus message."""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".lua",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(code)
            path = f.name
        r = subprocess.run(
            [luac_path, "-p", path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        Path(path).unlink(missing_ok=True)
        if r.returncode == 0:
            return True, ""
        return False, (r.stderr or r.stdout or "luac failed").strip()
    except FileNotFoundError:
        return False, f"luac not found at {luac_path!r}"
    except subprocess.TimeoutExpired:
        return False, "luac timeout"


def validate_code(code: str, luac_path: str = "luac") -> tuple[bool, list[str]]:
    """Compose static and syntax checks into legacy validate_code output."""
    errors: list[str] = []
    for v in static_guard_violations(code):
        errors.append(f"static: {v}")
    ok, msg = luac_check(code, luac_path=luac_path)
    if not ok and msg:
        errors.append(f"syntax: {msg}")
    return len(errors) == 0, errors
