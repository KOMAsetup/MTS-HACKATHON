from __future__ import annotations

import json

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


def repair_user_message(broken_code: str, errors: str) -> str:
    return (
        "The following Lua failed validation. Fix syntax and policy violations. "
        "Output ONLY the corrected Lua.\n\n"
        f"Errors:\n{errors}\n\nBroken code:\n```lua\n{broken_code.strip()}\n```"
    )
