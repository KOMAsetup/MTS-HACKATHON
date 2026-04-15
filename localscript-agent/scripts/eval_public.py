#!/usr/bin/env python3
"""Evaluate /generate against benchmarks/public_tasks.json."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx

from app.config import Settings
from app.models_io import GenerateRequest, ResponseKind
from app.pipeline import run_generate_pipeline
from app.sandbox import run_lua_with_wf
from app.validate import luac_check, static_guard_violations


def load_tasks(path: Path | None = None) -> list[dict]:
    p = path or (ROOT / "benchmarks" / "public_tasks.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def merge_prompt_with_benchmark(task: dict) -> str:
    """Benchmark `context` is embedded in the prompt only (not a separate API field)."""
    prompt = task["prompt"]
    ctx = task.get("context")
    if ctx is None:
        return prompt
    return (
        f"{prompt}\n\nContext:\n"
        f"{json.dumps(ctx, ensure_ascii=False, indent=2)}"
    )


def heuristic_pass(code: str, expected_contains: list[str]) -> bool:
    return all(s in code for s in expected_contains)


async def run_one_direct(
    client: httpx.AsyncClient,
    settings: Settings,
    task: dict,
) -> dict:
    t0 = time.perf_counter()
    eval_settings = settings.model_copy(update={"clarification_mode": False})
    req = GenerateRequest(prompt=merge_prompt_with_benchmark(task))
    resp = await run_generate_pipeline(client, eval_settings, req)
    dt = time.perf_counter() - t0
    if resp.response_kind != ResponseKind.code:
        raise RuntimeError(f"expected code response, got {resp.response_kind!r}")
    code = resp.code or ""
    return {"code": code, "latency_s": dt}


def score_task(task: dict, code: str) -> dict:
    ev = task.get("eval") or {}
    et = ev.get("type", "heuristic")
    errs: list[str] = []

    ok_l, msg = luac_check(code, luac_path=Settings().luac_path)
    if not ok_l:
        errs.append(f"luac:{msg}")

    static_violations = static_guard_violations(code)
    static_ok = not static_violations
    for v in static_violations:
        errs.append(f"static:{v}")

    sandbox_ok = True
    if et == "sandbox" and ok_l and static_ok:
        ctx = task.get("context") or {}
        wf_root = ctx.get("wf", ctx)
        sb_ok, out, err = run_lua_with_wf(code, wf_root, lua_bin=Settings().lua_path)
        if not sb_ok:
            sandbox_ok = False
            errs.append(f"sandbox:{err or out}")

    subs = ev.get("expected_contains") or []
    heur_ok = heuristic_pass(code, subs) if subs else True
    if subs and not heur_ok:
        errs.append("heuristic:expected_substrings_missing")

    if et == "heuristic":
        final = ok_l and static_ok and heur_ok
    else:
        final = ok_l and static_ok and sandbox_ok and heur_ok

    return {
        "syntax_ok": ok_l,
        "sandbox_ok": sandbox_ok,
        "heuristic_ok": heur_ok,
        "errors": errs,
        "pass": final,
    }


def final_pass(
    *,
    eval_type: str,
    syntax_ok: bool,
    static_ok: bool,
    sandbox_ok: bool,
    heuristic_ok: bool,
    strict_heuristic: bool,
) -> bool:
    """
    New default semantics:
    - heuristic tasks: require heuristic substring check
    - sandbox tasks: by default rely on syntax/static/sandbox only
      (heuristics can be enabled with --strict-heuristic)
    """
    if eval_type == "heuristic":
        return syntax_ok and static_ok and heuristic_ok
    if strict_heuristic:
        return syntax_ok and static_ok and sandbox_ok and heuristic_ok
    return syntax_ok and static_ok and sandbox_ok


async def _post_generate_with_clarification_loop(
    hc: httpx.AsyncClient,
    *,
    prompt: str,
    max_clarification_rounds: int,
) -> tuple[dict, int]:
    """
    Handle /generate clarification branch in HTTP mode.
    Returns (final_response_json, clarification_rounds_used).
    """
    clarification_history: list[dict[str, str]] = []
    rounds = 0
    while True:
        payload = {
            "prompt": prompt,
            "clarification_history": clarification_history,
        }
        r = await hc.post("/generate", json=payload)
        r.raise_for_status()
        data = r.json()
        rk = data.get("response_kind")
        if rk == "code":
            return data, rounds
        if rk != "clarification":
            raise RuntimeError(f"unexpected response_kind: {rk!r}")
        if rounds >= max_clarification_rounds:
            raise RuntimeError(
                f"clarification rounds exceeded limit={max_clarification_rounds}"
            )
        q = (data.get("clarification_question") or "").strip()
        # Deterministic auto-answer for benchmark runs.
        a = (
            "Proceed with best reasonable defaults and context values. "
            "Do not ask more clarifications unless absolutely necessary."
        )
        clarification_history.append({"model_question": q, "user_answer": a})
        rounds += 1


async def main_async(args: argparse.Namespace) -> int:
    tasks = load_tasks(Path(args.tasks) if args.tasks else None)
    settings = Settings()
    results = []
    if args.http:
        async with httpx.AsyncClient(base_url=args.base_url, timeout=180.0) as hc:
            for t in tasks:
                try:
                    t0 = time.perf_counter()
                    data, clar_rounds = await _post_generate_with_clarification_loop(
                        hc,
                        prompt=merge_prompt_with_benchmark(t),
                        max_clarification_rounds=args.max_clarification_rounds,
                    )
                    code = data.get("code") or ""
                    dt = time.perf_counter() - t0
                    sc = score_task(t, code)
                    ev = t.get("eval") or {}
                    et = ev.get("type", "heuristic")
                    static_ok = not any(e.startswith("static:") for e in sc["errors"])
                    sc["pass"] = final_pass(
                        eval_type=et,
                        syntax_ok=bool(sc["syntax_ok"]),
                        static_ok=static_ok,
                        sandbox_ok=bool(sc["sandbox_ok"]),
                        heuristic_ok=bool(sc["heuristic_ok"]),
                        strict_heuristic=args.strict_heuristic,
                    )
                    results.append(
                        {
                            "id": t["id"],
                            **sc,
                            "clarification_rounds": clar_rounds,
                            "latency_s": dt,
                            "code_preview": code[:200],
                        }
                    )
                except Exception as e:
                    results.append({"id": t["id"], "pass": False, "errors": [str(e)]})
    else:
        client = httpx.AsyncClient()
        try:
            for t in tasks:
                try:
                    r = await run_one_direct(client, settings, t)
                    sc = score_task(t, r["code"])
                    ev = t.get("eval") or {}
                    et = ev.get("type", "heuristic")
                    static_ok = not any(e.startswith("static:") for e in sc["errors"])
                    sc["pass"] = final_pass(
                        eval_type=et,
                        syntax_ok=bool(sc["syntax_ok"]),
                        static_ok=static_ok,
                        sandbox_ok=bool(sc["sandbox_ok"]),
                        heuristic_ok=bool(sc["heuristic_ok"]),
                        strict_heuristic=args.strict_heuristic,
                    )
                    results.append(
                        {
                            "id": t["id"],
                            **sc,
                            "latency_s": r["latency_s"],
                            "code_preview": r["code"][:200],
                        }
                    )
                except Exception as e:
                    results.append({"id": t["id"], "pass": False, "errors": [str(e)]})
        finally:
            await client.aclose()

    passed = sum(1 for x in results if x.get("pass"))
    out = {
        "passed": passed,
        "total": len(tasks),
        "results": results,
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if passed == len(tasks) else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--http",
        action="store_true",
        help="Call running server instead of in-process pipeline",
    )
    ap.add_argument(
        "--base-url",
        default="http://127.0.0.1:8080",
        help="Server base URL for --http",
    )
    ap.add_argument(
        "--tasks",
        default=None,
        help="Path to tasks JSON (default: benchmarks/public_tasks.json)",
    )
    ap.add_argument(
        "--strict-heuristic",
        action="store_true",
        help=(
            "For sandbox tasks also require expected_contains heuristics. "
            "Default is relaxed (sandbox correctness based on syntax/static/sandbox)."
        ),
    )
    ap.add_argument(
        "--max-clarification-rounds",
        type=int,
        default=2,
        help="Max clarification rounds to auto-handle in HTTP mode before failing.",
    )
    args = ap.parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
