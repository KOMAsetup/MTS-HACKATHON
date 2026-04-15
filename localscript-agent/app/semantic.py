from __future__ import annotations

import ast
import re
from typing import Any

from app.sandbox import run_lua_with_wf_capture_result


def semantic_validate(
    code: str,
    *,
    context: dict | None,
    lua_bin: str,
    context_key: str = "__semantic_validation",
) -> tuple[bool, list[str]]:
    """
    Run optional semantic validation using a spec from request context.

    Expected context shape:
      {
        "wf": {...},
        "__semantic_validation": {
          "expected_stdout": "42",
          "expected_stdout_regex": "^\\d+$",
          "forbid_stdout_contains": ["nil", "error"],
          "require_non_empty_stdout": true
        }
      }
    """
    spec = _extract_semantic_spec(context, context_key=context_key)
    if spec is None:
        return True, []

    wf_root = _extract_wf_root(context)
    ok, out, err, result_obj = run_lua_with_wf_capture_result(code, wf_root, lua_bin=lua_bin)
    if not ok:
        return False, [f"semantic:sandbox_exec:{err or out}"]

    sem_errors = evaluate_semantic_rules(out, result_obj, spec)
    if sem_errors:
        return False, [f"semantic:{e}" for e in sem_errors]
    return True, []


def _extract_semantic_spec(context: dict | None, *, context_key: str) -> dict[str, Any] | None:
    if not isinstance(context, dict):
        return None
    spec = context.get(context_key)
    return spec if isinstance(spec, dict) else None


def _extract_wf_root(context: dict | None) -> dict:
    if not isinstance(context, dict):
        return {}
    wf = context.get("wf")
    if isinstance(wf, dict):
        return wf
    return context


def evaluate_semantic_rules(
    stdout: str, result_obj: object | None, spec: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    actual = (stdout or "").strip()

    expected_stdout = spec.get("expected_stdout")
    if expected_stdout is not None and actual != str(expected_stdout):
        errors.append(f"expected_stdout_mismatch: expected={expected_stdout!r}, got={actual!r}")

    expected_regex = spec.get("expected_stdout_regex")
    if isinstance(expected_regex, str):
        if re.search(expected_regex, actual) is None:
            errors.append(
                f"expected_stdout_regex_mismatch: pattern={expected_regex!r}, got={actual!r}"
            )

    forbid_contains = spec.get("forbid_stdout_contains")
    if isinstance(forbid_contains, list):
        for token in forbid_contains:
            if isinstance(token, str) and token in actual:
                errors.append(f"forbid_stdout_contains_match: token={token!r}")

    if bool(spec.get("require_non_empty_stdout")) and actual == "":
        errors.append("stdout_empty_but_required")

    allowed_values = spec.get("allowed_stdout_values")
    if isinstance(allowed_values, list):
        allowed_str = [str(x) for x in allowed_values]
        if actual not in allowed_str:
            errors.append(
                f"allowed_stdout_values_mismatch: allowed={allowed_str!r}, got={actual!r}"
            )

    expected_type = spec.get("expected_type")
    if isinstance(expected_type, str):
        _check_expected_type(expected_type, result_obj, errors)

    expected_len = spec.get("expected_len")
    if expected_len is not None:
        _check_expected_len(expected_len, result_obj, errors)

    required_keys = spec.get("required_keys")
    if isinstance(required_keys, list):
        _check_required_keys(required_keys, result_obj, errors)

    all_items_predicate = spec.get("all_items_predicate")
    if isinstance(all_items_predicate, str):
        _check_all_items_predicate(all_items_predicate, result_obj, errors)

    numeric_range = spec.get("numeric_range")
    if numeric_range is not None:
        _check_numeric_range(numeric_range, result_obj, errors)

    return errors


def _check_expected_type(expected: str, value: object | None, errors: list[str]) -> None:
    actual_map = {
        list: "array",
        dict: "object",
        str: "string",
        int: "number",
        float: "number",
        bool: "boolean",
    }
    actual_type = "null" if value is None else actual_map.get(type(value), "other")
    if actual_type != expected:
        errors.append(f"expected_type_mismatch: expected={expected!r}, got={actual_type!r}")


def _check_expected_len(rule: object, value: object | None, errors: list[str]) -> None:
    if not isinstance(value, (list, dict, str)):
        errors.append("expected_len_type_error: result is not sized (need array/object/string)")
        return
    actual_len = len(value)
    if isinstance(rule, int):
        if actual_len != rule:
            errors.append(f"expected_len_mismatch: expected={rule}, got={actual_len}")
        return
    if isinstance(rule, dict):
        eq = rule.get("eq")
        gte = rule.get("gte")
        lte = rule.get("lte")
        if isinstance(eq, int) and actual_len != eq:
            errors.append(f"expected_len_eq_mismatch: expected={eq}, got={actual_len}")
        if isinstance(gte, int) and actual_len < gte:
            errors.append(f"expected_len_gte_mismatch: expected>={gte}, got={actual_len}")
        if isinstance(lte, int) and actual_len > lte:
            errors.append(f"expected_len_lte_mismatch: expected<={lte}, got={actual_len}")
        return
    errors.append("expected_len_invalid_rule")


def _check_required_keys(required_keys: list, value: object | None, errors: list[str]) -> None:
    keys = [k for k in required_keys if isinstance(k, str)]
    if not keys:
        return
    if isinstance(value, dict):
        missing = [k for k in keys if k not in value]
        if missing:
            errors.append(f"required_keys_missing: {missing!r}")
        return
    if isinstance(value, list):
        for idx, item in enumerate(value):
            if not isinstance(item, dict):
                errors.append(f"required_keys_item_type_error: index={idx}")
                continue
            missing = [k for k in keys if k not in item]
            if missing:
                errors.append(f"required_keys_missing: index={idx}, missing={missing!r}")
        return
    errors.append("required_keys_type_error: result is not object/array-of-objects")


def _check_all_items_predicate(predicate: str, value: object | None, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append("all_items_predicate_type_error: result is not array")
        return
    parsed = _parse_predicate(predicate)
    if parsed is None:
        errors.append(f"all_items_predicate_invalid: {predicate!r}")
        return
    field, op, rhs = parsed
    for idx, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"all_items_predicate_item_type_error: index={idx}")
            continue
        lhs = item.get(field)
        if not _compare(lhs, op, rhs):
            errors.append(
                "all_items_predicate_mismatch: "
                f"index={idx}, field={field!r}, op={op!r}, rhs={rhs!r}, got={lhs!r}"
            )


def _check_numeric_range(rule: object, value: object | None, errors: list[str]) -> None:
    if isinstance(rule, (int, float)):
        # shorthand: exact numeric value
        if not isinstance(value, (int, float)):
            errors.append("numeric_range_type_error: result is not numeric")
            return
        if float(value) != float(rule):
            errors.append(f"numeric_range_exact_mismatch: expected={rule}, got={value}")
        return
    if not isinstance(rule, dict):
        errors.append("numeric_range_invalid_rule")
        return

    target = value
    path = rule.get("path")
    if isinstance(path, str) and path.strip():
        target = _get_by_dot_path(value, path)
    if not isinstance(target, (int, float)):
        errors.append(f"numeric_range_type_error: target at path {path!r} is not numeric")
        return
    num = float(target)
    minimum = rule.get("min")
    maximum = rule.get("max")
    if isinstance(minimum, (int, float)) and num < float(minimum):
        errors.append(f"numeric_range_min_mismatch: min={minimum}, got={num}")
    if isinstance(maximum, (int, float)) and num > float(maximum):
        errors.append(f"numeric_range_max_mismatch: max={maximum}, got={num}")


def _parse_predicate(predicate: str) -> tuple[str, str, object] | None:
    m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(==|!=|>=|<=|>|<)\s*(.+?)\s*$", predicate)
    if not m:
        return None
    field, op, rhs_raw = m.group(1), m.group(2), m.group(3)
    rhs = _parse_literal(rhs_raw)
    return field, op, rhs


def _parse_literal(raw: str) -> object:
    lower = raw.lower()
    if lower == "nil" or lower == "null":
        return None
    if lower == "true":
        return True
    if lower == "false":
        return False
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        pass
    try:
        return ast.literal_eval(raw)
    except Exception:
        return raw.strip("\"'")


def _compare(lhs: object, op: str, rhs: object) -> bool:
    if op == "==":
        return lhs == rhs
    if op == "!=":
        return lhs != rhs
    if op in {">", "<", ">=", "<="}:
        if not isinstance(lhs, (int, float)) or not isinstance(rhs, (int, float)):
            return False
        if op == ">":
            return lhs > rhs
        if op == "<":
            return lhs < rhs
        if op == ">=":
            return lhs >= rhs
        return lhs <= rhs
    return False


def _get_by_dot_path(value: object, path: str) -> object | None:
    cur: object = value
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
            continue
        if isinstance(cur, list) and part.isdigit():
            idx = int(part)
            if 0 <= idx < len(cur):
                cur = cur[idx]
                continue
            return None
        return None
    return cur
