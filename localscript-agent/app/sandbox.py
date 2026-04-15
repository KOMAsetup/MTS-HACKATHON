from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


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
    # Emulate common LowCode runtime behavior:
    # - wf.initVariables may be used as a callable helper (wf.initVariables("k", v))
    # - and/or as a table with incoming values (wf.initVariables.recallTime)
    initvars_stub = """
if wf.initVariables == nil then
  wf.initVariables = {}
end
if type(wf.initVariables) == "table" then
  setmetatable(wf.initVariables, {
    __call = function(self, key, value)
      if type(key) == "string" and value ~= nil then
        wf.vars = wf.vars or {}
        wf.vars[key] = value
      end
      return value
    end
  })
elseif type(wf.initVariables) == "function" then
  -- leave function as-is
else
  -- unexpected type: wrap into a callable table preserving the original value under _value
  local original = wf.initVariables
  wf.initVariables = setmetatable({ _value = original }, {
    __call = function(self, key, value)
      if type(key) == "string" and value ~= nil then
        wf.vars = wf.vars or {}
        wf.vars[key] = value
      end
      return value
    end
  })
end
"""
    wrapper = (
        utils_stub
        + f"local wf = {wf_lua}\n"
        + initvars_stub
        + "local _ok, _result = pcall(function()\n"
        + f"{code}\n"
        + "end)\n"
        + "if not _ok then error(_result) end\n"
        + "if _result ~= nil then print(tostring(_result)) end\n"
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
