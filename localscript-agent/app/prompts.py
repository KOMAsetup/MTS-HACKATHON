from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.models_io import ClarificationTurn, RefinementStep

SYSTEM_PROMPT = """You are a code generator for LowCode Lua scripts (Lua 5.x style).

Rules:
- Match the task language (Russian or English) in comments only if needed; the code itself
  stays Lua identifiers and strings as required by the task.
- Output ONLY executable Lua (no markdown fences, no explanations). If the user explicitly
  asks for JSON with lua{...}lua wrappers, output valid JSON as requested.
- Use wf.vars for workflow variables and wf.initVariables for input variables from the schema.
- For new arrays use _utils.array.new(); use _utils.array.markAsArray(arr) when a variable
  must be treated as array.
- Do NOT use JsonPath. Use direct field chains, e.g. wf.vars.json.IDOC.ZCDF_HEAD.DATUM
- Do NOT use require(), dofile(), load(), io.*, or run external commands. You MAY use
  os.time, os.date, os.difftime for date/time math; do NOT use os.execute, os.getenv,
  os.remove, os.rename, etc.
- If REST data has `result` as an array of rows, loop over `wf.vars....result` with
  pairs/ipairs and change fields on each row table — do not treat `result` as one object
  when the context shows a list of objects.
- For ISO 8601 from YYYYMMDD and HHMMSS strings (e.g. DATUM=20231015, TIME=153000),
  parse with string.sub + tonumber into year,month,day,hour,min,sec then Lua
  string.format(\"%04d-%02d-%02dT%02d:%02d:%02dZ\", ...) so the result visibly contains
  hyphens and colons (e.g. 2023-10-15T15:30:00Z). Do not concatenate raw DATUM+TIME without parsing.
- When filtering tables like `wf.vars.parsedCsv`, build the result with `_utils.array.new()`,
  push rows with table.insert, then `_utils.array.markAsArray(arr)` before return if the platform
  expects an array type.
- If the task asks for LowCode JSON with `lua{...}lua` wrappers, emit **valid Lua**: use
  `local n = tonumber(wf.vars.<field>) or 0` then
  `return string.format('lua{"num":%d,"squared":%d}lua', n, n * n)` (rename keys to match the task).
  Never output JS-style fragments like `num = ..., squared = ...` without `local`/`return` and
  without a surrounding Lua statement.
- For those tasks, never return only plain JSON like string.format('{\"num\":%d,...}'); the Lua
  source must literally contain `lua{` then the JSON fields then `}lua` inside the format pattern
  (see few-shot: string.format('lua{\"num\":%d,\"squared\":%d}lua', ...)).
- Prefer clear, minimal code. End with return of the main value when the task asks for a result.

If the user message includes a JSON block under "Context:", treat it as read-only data
available as the global `wf` at runtime."""

FEW_SHOT_USER_1 = """Task: From list emails return the last element.

Context:
{"wf":{"vars":{"emails":["a@x.com","b@x.com","c@x.com"]}}}"""

FEW_SHOT_ASSISTANT_1 = "return wf.vars.emails[#wf.vars.emails]"

FEW_SHOT_USER_2 = """Task: Increment try_count_n by 1.

Context:
{"wf":{"vars":{"try_count_n": 3}}}"""

FEW_SHOT_ASSISTANT_2 = "return wf.vars.try_count_n + 1"

FEW_SHOT_USER_3 = (
    "Task: Квадрат числа; JSON с полями num и squared в формате lua{...}lua (LowCode).\n\n"
    'Context:\n{"wf":{"vars":{"num":5}}}'
)

FEW_SHOT_ASSISTANT_3 = (
    "local n = tonumber(wf.vars.num) or 0\n"
    'return string.format(\'lua{"num":%d,"squared":%d}lua\', n, n * n)'
)


def build_user_message(
    prompt: str,
    context: dict | None = None,
    previous_code: str | None = None,
    feedback: str | None = None,
) -> str:
    parts = [f"Task:\n{prompt.strip()}"]
    if context is not None:
        parts.append("Context:\n" + json.dumps(context, ensure_ascii=False, indent=2))
    if previous_code is not None:
        parts.append("Previous Lua (fix or improve):\n```lua\n" + previous_code.strip() + "\n```")
    if feedback is not None:
        parts.append("User feedback / constraints:\n" + feedback.strip())
    if "lua{" in prompt and "}lua" in prompt:
        parts.append(
            "Hard constraint: include literal substrings lua{ and }lua in the Lua source and "
            'a tonumber(...) call; use return string.format(\'lua{"num":%d,"squared":%d}lua\', '
            "n, n*n) style with single-quoted format string (adjust field names if needed)."
        )
    return "\n\n".join(parts)


def compress_context_for_repair(
    context: dict | None,
    *,
    max_chars: int = 1800,
    max_depth: int = 4,
    str_limit: int = 96,
    list_limit: int = 4,
) -> str:
    def prune(obj: object, depth: int) -> object:
        if depth >= max_depth:
            return "…"
        if isinstance(obj, dict):
            return {str(k): prune(v, depth + 1) for k, v in obj.items()}
        if isinstance(obj, list):
            head = [prune(x, depth + 1) for x in obj[:list_limit]]
            if len(obj) > list_limit:
                head.append(f"… (+{len(obj) - list_limit} items)")
            return head
        if isinstance(obj, str):
            s = obj
            if len(s) > str_limit:
                return s[: str_limit - 1] + "…"
            return s
        if isinstance(obj, (int, float, bool)) or obj is None:
            return obj
        return str(obj)[:str_limit]

    if context is None:
        return "{}"
    pruned = prune(context, 0)
    text = json.dumps(pruned, ensure_ascii=False, indent=2)
    if len(text) > max_chars:
        return text[: max_chars - 24] + "\n… (truncated)"
    return text


def repair_user_message_compact(
    *,
    task_prompt: str,
    context: dict | None,
    broken_code: str,
    error_lines: list[str],
    task_max_chars: int = 600,
    feedback: str | None = None,
    feedback_max_chars: int = 400,
) -> str:
    task = task_prompt.strip()
    if len(task) > task_max_chars:
        task = task[: task_max_chars - 1] + "…"
    schema = compress_context_for_repair(context)
    errs = "\n".join(error_lines)
    code = broken_code.strip()
    parts = [
        f"Task (reminder):\n{task}",
        f"Context (compact wf/schema):\n{schema}",
        f"Validation errors:\n{errs}",
        "Output ONLY the corrected Lua (no markdown, no explanation).",
        f"Broken code:\n```lua\n{code}\n```",
    ]
    if feedback is not None and feedback.strip():
        fb = feedback.strip()
        if len(fb) > feedback_max_chars:
            fb = fb[: feedback_max_chars - 1] + "…"
        parts.insert(1, f"User feedback:\n{fb}")
    return "\n\n".join(parts)


def messages_for_chat(
    user_content: str,
    include_few_shot: bool = True,
) -> list[dict[str, str]]:
    msgs: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if include_few_shot:
        msgs.extend(
            [
                {"role": "user", "content": FEW_SHOT_USER_1},
                {"role": "assistant", "content": FEW_SHOT_ASSISTANT_1},
                {"role": "user", "content": FEW_SHOT_USER_2},
                {"role": "assistant", "content": FEW_SHOT_ASSISTANT_2},
                {"role": "user", "content": FEW_SHOT_USER_3},
                {"role": "assistant", "content": FEW_SHOT_ASSISTANT_3},
            ]
        )
    msgs.append({"role": "user", "content": user_content})
    return msgs


SYSTEM_PROMPT_GENERATE_JSON = """You are a code generator for LowCode Lua scripts (Lua 5.x style).

You MUST respond with exactly one JSON object and no other text before or after it (no markdown fences unless you put JSON inside a single ```json fenced block — prefer raw JSON only).

Use one of these shapes:
1) If the task is ambiguous or you need one specific detail from the user before you can write correct Lua:
{"response_kind":"clarification","question":"<your question in the task language>"}

2) If you can write the Lua now:
{"response_kind":"code","lua":"<full Lua source as a single JSON string with proper escaping>"}

Rules for the code path (same platform rules as production Lua):
- Match task language in clarification questions only; Lua identifiers stay ASCII as needed.
- Use wf.vars, wf.initVariables, _utils.array.new / markAsArray as in the platform.
- Do NOT use require(), dofile(), load(), io.*; you MAY use os.time, os.date, os.difftime.
- Output valid Lua in the "lua" string; escape quotes and newlines for JSON.

If the user message includes "Previous clarifications:", incorporate those answers — do not ask again for information already answered."""


SYSTEM_PROMPT_GENERATE_JSON_CODE_ONLY = """You are a code generator for LowCode Lua scripts. You MUST respond with exactly one JSON object:
{"response_kind":"code","lua":"<full Lua source>"}
No clarification mode: always produce code. Same Lua platform rules as the full generator."""


SYSTEM_PROMPT_DEBUG = """You are a senior reviewer for Lua 5.x workflow scripts (LowCode).

Message layout: (1) static checks + current Lua, (2) optional earlier /debug transcript, (3) **PRIMARY
TASK** last — the user's current question.

**problem_description** rules:
- The PRIMARY TASK is often a direct question. You MUST give a **concrete answer first** (the fact,
  the number, the name). Examples: "What language?" → start with **Lua** (Lua 5.x / LowCode workflow
  Lua), not with "The user is asking about the programming language". "What is 5+3?" → start with
  **8**, not with "The user wants to know the sum".
- **Forbidden:** only restating or describing the user's question without answering it.
- After the direct answer, you may add one short sentence on checks/code if still useful.

**suggested_code** must be non-empty, complete, syntactically valid Lua. If the PRIMARY TASK is not
about changing code, still return the best fix for the current snippet (or the same snippet if it is
already valid Lua).

You MUST respond with exactly one JSON object (no markdown outside it):
{"problem_description":"<concrete answer first, then optional notes>","suggested_code":"<full Lua>"}
Escape strings properly for JSON."""


def build_generate_user_message(
    prompt: str,
    clarification_history: list[ClarificationTurn],
    context: dict | None = None,
) -> str:
    parts: list[str] = [f"Task:\n{prompt.strip()}"]
    if context is not None:
        parts.append("Context:\n" + json.dumps(context, ensure_ascii=False, indent=2))
    if clarification_history:
        lines = []
        for i, turn in enumerate(clarification_history):
            lines.append(
                f"Round {i + 1}\nQuestion: {turn.model_question}\nAnswer: {turn.user_answer}"
            )
        parts.append("Previous clarifications:\n" + "\n\n".join(lines))
    if "lua{" in prompt and "}lua" in prompt:
        parts.append(
            "Hard constraint: include literal substrings lua{ and }lua in the Lua source when required."
        )
    return "\n\n".join(parts)


def build_refinement_user_message(
    prompt: str,
    refinement_history: list["RefinementStep"],
    context: dict | None = None,
) -> str:
    parts: list[str] = [f"Task (original):\n{prompt.strip()}"]
    if context is not None:
        parts.append("Context:\n" + json.dumps(context, ensure_ascii=False, indent=2))
    blocks: list[str] = []
    for i, step in enumerate(refinement_history):
        chk = ", ".join(f"{c.stage}:{c.passed}" for c in step.checks) if step.checks else "(no checks recorded)"
        blocks.append(
            f"Step {i + 1}\n"
            f"Assistant code:\n```lua\n{step.assistant_code.strip()}\n```\n"
            f"User feedback:\n{step.user_feedback.strip()}\n"
            f"Checks snapshot (reference): {chk}\n"
        )
    parts.append("Refinement history (chronological):\n\n" + "\n".join(blocks))
    parts.append(
        "Produce ONLY the updated Lua that addresses the **last** user feedback in the history. "
        "Output executable Lua only in your next assistant message (plain Lua for this endpoint — "
        "the outer API wraps it); no markdown fences unless the task requires a lua{...}lua JSON pattern."
    )
    return "\n\n".join(parts)


_DEBUG_HIST_USER_CODE_MAX = 14_000
_DEBUG_HIST_PROBLEM_MAX = 10_000
_DEBUG_HIST_SUGGESTED_MAX = 14_000


def _truncate_debug_text(s: str, max_chars: int) -> str:
    t = s.strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 1] + "…"


def _format_debug_history_checks_block(checks: Any) -> str:
    """Only all_checks_passed plus failed checks (no full passed list)."""
    if not checks:
        return "all_checks_passed: true (empty snapshot — treat as no failures)."
    failed = [c for c in checks if not bool(getattr(c, "passed", False))]
    if not failed:
        return "all_checks_passed: true"
    lines: list[str] = ["all_checks_passed: false", "Failed checks:"]
    for c in failed:
        st = getattr(c, "stage", "?")
        msg = (getattr(c, "message", None) or "").strip()
        lines.append(f"- {st}: {msg}")
    return "\n".join(lines)


def build_debug_user_message(
    code: str,
    prompt: str | None,
    debug_history: list[Any],
    checks_text: str,
) -> str:
    from app.models_io import DebugHistoryTurn

    parts: list[str] = []
    parts.extend(
        [
            "=== Context: static checks + user's Lua (this round) ===\n"
            "Static checks (compact: all_checks_passed + failed only):\n" + checks_text,
            "User's Lua:\n```lua\n" + code.strip() + "\n```",
        ]
    )
    if debug_history:
        hist_lines: list[str] = []
        for i, turn in enumerate(debug_history):
            if not isinstance(turn, DebugHistoryTurn):
                continue
            uc = _truncate_debug_text(turn.user_code, _DEBUG_HIST_USER_CODE_MAX)
            chk_block = _format_debug_history_checks_block(turn.checks)
            up = (turn.user_prompt or "").strip()
            user_q = f"User question / note then:\n{up}\n" if up else "User question / note then:\n(none)\n"
            pd = _truncate_debug_text(turn.problem_description, _DEBUG_HIST_PROBLEM_MAX)
            sc = _truncate_debug_text(turn.suggested_code, _DEBUG_HIST_SUGGESTED_MAX)
            hist_lines.append(
                f"========== Earlier debug round {i + 1} (chronological) ==========\n"
                f"User's code then:\n```lua\n{uc}\n```\n"
                f"Static checks then (all_checks_passed + failures only):\n{chk_block}\n"
                f"{user_q}"
                f"Assistant problem_description then:\n{pd}\n"
                f"Assistant suggested_code then:\n```lua\n{sc}\n```\n"
            )
        parts.append(
            "=== Earlier /debug transcript (same order as HTTP requests) ===\n\n"
            + "\n".join(hist_lines)
        )
    if prompt and prompt.strip():
        parts.append(
            "=== PRIMARY TASK (read LAST — this is what you must answer first in problem_description) ===\n"
            + prompt.strip()
            + "\n\nIf the primary task is a direct question, answer it in the opening of "
            "problem_description before any repeated Lua-syntax boilerplate."
        )
    parts.append(
        "Respond with JSON only: problem_description and suggested_code as specified in the system prompt."
    )
    return "\n\n".join(parts)


def messages_for_generate_chat(
    user_content: str,
    *,
    clarification_mode: bool,
    include_few_shot: bool = True,
) -> list[dict[str, str]]:
    sys_content = (
        SYSTEM_PROMPT_GENERATE_JSON if clarification_mode else SYSTEM_PROMPT_GENERATE_JSON_CODE_ONLY
    )
    msgs: list[dict[str, str]] = [{"role": "system", "content": sys_content}]
    if include_few_shot:
        msgs.extend(
            [
                {"role": "user", "content": FEW_SHOT_USER_1},
                {"role": "assistant", "content": FEW_SHOT_ASSISTANT_1},
                {"role": "user", "content": FEW_SHOT_USER_2},
                {"role": "assistant", "content": FEW_SHOT_ASSISTANT_2},
                {"role": "user", "content": FEW_SHOT_USER_3},
                {"role": "assistant", "content": FEW_SHOT_ASSISTANT_3},
            ]
        )
    msgs.append({"role": "user", "content": user_content})
    return msgs


def messages_for_debug_chat(user_content: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT_DEBUG},
        {"role": "user", "content": user_content},
    ]
