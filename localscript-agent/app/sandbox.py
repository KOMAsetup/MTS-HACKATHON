from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

RESULT_JSON_MARKER = "__RESULT_JSON__"


def _lua_literal(obj: object) -> str:
    if obj is None:
        return "nil"
    if isinstance(obj, bool):
        return "true" if obj else "false"
    if isinstance(obj, (int, float)):
        return str(obj)
    if isinstance(obj, str):
        esc = (
            obj.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
        )
        return f'"{esc}"'
    if isinstance(obj, list):
        parts = [_lua_literal(x) for x in obj]
        return "{" + ", ".join(parts) + "}"
    if isinstance(obj, dict):
        parts = []
        for k, v in obj.items():
            if not isinstance(k, str):
                k = str(k)
            key = k.replace("\\", "\\\\").replace('"', '\\"')
            parts.append(f'["{key}"] = {_lua_literal(v)}')
        return "{" + ", ".join(parts) + "}"
    return "nil"


def run_lua_with_wf(
    code: str,
    wf_table: dict,
    lua_bin: str = "lua",
    timeout_s: float = 5.0,
) -> tuple[bool, str, str]:
    wf_lua = _lua_literal(wf_table)
    utils_stub = """
local _utils = {
  array = {
    new = function() return {} end,
    markAsArray = function(t) return t end,
  },
}
"""
    wrapper = (
        utils_stub + f"local wf = {wf_lua}\n"
        "local _ok, _result = pcall(function()\n"
        f"{code}\n"
        "end)\n"
        "if not _ok then error(_result) end\n"
        "if _result ~= nil then print(tostring(_result)) end\n"
    )
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".lua",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(wrapper)
            path = f.name
        r = subprocess.run(
            [lua_bin, path],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        Path(path).unlink(missing_ok=True)
        ok = r.returncode == 0
        return ok, (r.stdout or "").strip(), (r.stderr or "").strip()
    except FileNotFoundError:
        return False, "", f"lua interpreter not found at {lua_bin!r}"
    except subprocess.TimeoutExpired:
        return False, "", "lua execution timeout"
    except Exception as e:
        return False, "", str(e)


def run_lua_with_wf_capture_result(
    code: str,
    wf_table: dict,
    lua_bin: str = "lua",
    timeout_s: float = 5.0,
) -> tuple[bool, str, str, object | None]:
    wf_lua = _lua_literal(wf_table)
    utils_stub = """
local _utils = {
  array = {
    new = function() return {} end,
    markAsArray = function(t) return t end,
  },
}
"""
    json_encoder = r'''
local function _json_escape(s)
  s = tostring(s)
  s = s:gsub("\\", "\\\\")
  s = s:gsub('"', '\\"')
  s = s:gsub("\n", "\\n")
  s = s:gsub("\r", "\\r")
  return s
end

local function _is_array(t)
  if type(t) ~= "table" then return false end
  local n = 0
  for k, _ in pairs(t) do
    if type(k) ~= "number" or k < 1 or math.floor(k) ~= k then
      return false
    end
    if k > n then n = k end
  end
  if n == 0 then return true end
  for i = 1, n do
    if t[i] == nil then return false end
  end
  return true
end

local function _to_json(v)
  local tv = type(v)
  if tv == "nil" then return "null" end
  if tv == "boolean" then return v and "true" or "false" end
  if tv == "number" then return tostring(v) end
  if tv == "string" then return '"' .. _json_escape(v) .. '"' end
  if tv == "table" then
    if _is_array(v) then
      local parts = {}
      for i = 1, #v do parts[#parts + 1] = _to_json(v[i]) end
      return "[" .. table.concat(parts, ",") .. "]"
    end
    local parts = {}
    for k, val in pairs(v) do
      parts[#parts + 1] = '"' .. _json_escape(k) .. '":' .. _to_json(val)
    end
    return "{" .. table.concat(parts, ",") .. "}"
  end
  return '"' .. _json_escape(tv) .. '"'
end
'''
    wrapper = (
        utils_stub + json_encoder + f"local wf = {wf_lua}\n"
        "local _ok, _result = pcall(function()\n"
        f"{code}\n"
        "end)\n"
        "if not _ok then error(_result) end\n"
        "if _result ~= nil then\n"
        "  print(tostring(_result))\n"
        f'  print("{RESULT_JSON_MARKER}" .. _to_json(_result))\n'
        "end\n"
    )
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".lua",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(wrapper)
            path = f.name
        r = subprocess.run(
            [lua_bin, path],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        Path(path).unlink(missing_ok=True)
        ok = r.returncode == 0
        stdout = (r.stdout or "").strip()
        stderr = (r.stderr or "").strip()
        if not ok:
            return False, stdout, stderr, None
        parsed = _extract_result_json(stdout)
        return True, stdout, stderr, parsed
    except FileNotFoundError:
        return False, "", f"lua interpreter not found at {lua_bin!r}", None
    except subprocess.TimeoutExpired:
        return False, "", "lua execution timeout", None
    except Exception as e:
        return False, "", str(e), None


def _extract_result_json(stdout: str) -> object | None:
    for line in reversed(stdout.splitlines()):
        if line.startswith(RESULT_JSON_MARKER):
            payload = line[len(RESULT_JSON_MARKER) :]
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                return None
    return None
