from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from app.config import Settings
from app.semantic import semantic_validate
from app.validate import luac_check, static_guard_violations

logger = logging.getLogger(__name__)


class CheckStage(str, Enum):
    """Validation stage identifiers exposed to API clients."""
    static = "static"
    syntax = "syntax"
    linter = "linter"
    semantic = "semantic"


@dataclass(frozen=True)
class Violation:
    """Single failed validation item with stage and human-readable message."""
    stage: CheckStage
    message: str


@dataclass(frozen=True)
class CheckResult:
    """Aggregate validation result for one Lua snippet."""
    ok: bool
    violations: tuple[Violation, ...]

    def error_lines(self) -> list[str]:
        return [f"{v.stage.value}: {v.message}" for v in self.violations]


def _run_optional_linter(code: str, settings: Settings) -> list[Violation]:
    """Run external Lua linter when enabled and available in PATH."""
    if not settings.validation_linter:
        return []
    exe = settings.linter_path
    if not exe or not shutil.which(exe):
        return []
    violations: list[Violation] = []
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
            [exe, path],
            capture_output=True,
            text=True,
            timeout=settings.linter_timeout_s,
        )
        Path(path).unlink(missing_ok=True)
        if r.returncode != 0:
            msg = (r.stdout or r.stderr or "linter failed").strip()
            if len(msg) > 500:
                msg = msg[:500] + "..."
            violations.append(Violation(CheckStage.linter, msg))
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        violations.append(Violation(CheckStage.linter, "linter timeout"))
    except OSError as e:
        violations.append(Violation(CheckStage.linter, str(e)))
    return violations


def run_all_checks(
    code: str,
    *,
    settings: Settings,
    context: dict | None = None,
) -> CheckResult:
    """Static checks only. `context` reserved for future schema-based rules."""
    logger.debug("run_all_checks context_present=%s", context is not None)
    violations: list[Violation] = []

    for msg in static_guard_violations(code):
        violations.append(Violation(CheckStage.static, msg))

    ok_syn, syn_msg = luac_check(code, luac_path=settings.luac_path)
    if not ok_syn and syn_msg:
        violations.append(Violation(CheckStage.syntax, syn_msg))

    violations.extend(_run_optional_linter(code, settings))

    if _semantic_validation_enabled_for_request(
        settings_enabled=settings.enable_semantic_validation,
        context=context,
        context_key=settings.semantic_context_key,
    ):
        sem_ok, sem_errs = semantic_validate(
            code,
            context=context,
            lua_bin=settings.lua_path,
            context_key=settings.semantic_context_key,
        )
        if not sem_ok:
            for e in sem_errs:
                violations.append(Violation(CheckStage.semantic, e))

    return CheckResult(ok=len(violations) == 0, violations=tuple(violations))


def _semantic_validation_enabled_for_request(
    *,
    settings_enabled: bool,
    context: dict | None,
    context_key: str,
) -> bool:
    """Enable semantic checks globally or when request context provides spec."""
    if settings_enabled:
        return True
    if not isinstance(context, dict):
        return False
    return isinstance(context.get(context_key), dict)


def result_to_check_items(result: CheckResult) -> list:
    """Map violations to API CheckItem list; empty list means all checks passed."""
    from app.models_io import CheckItem

    return [
        CheckItem(
            id=f"{v.stage.value}_{i}",
            stage=v.stage.value,
            passed=False,
            message=v.message,
        )
        for i, v in enumerate(result.violations)
    ]


def log_check_outcome(
    *,
    outcome: str,
    violations: tuple[Violation, ...],
    repair_attempt: int | None,
) -> None:
    """Emit structured check outcome logs for observability."""
    stages = sorted({v.stage.value for v in violations})
    logger.info(
        "lua_check outcome=%s stages=%s repair_attempt=%s",
        outcome,
        ",".join(stages) if stages else "-",
        repair_attempt if repair_attempt is not None else "-",
    )
