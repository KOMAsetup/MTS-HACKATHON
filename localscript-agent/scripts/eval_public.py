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
from app.pipeline import generate_lua
from app.sandbox import run_lua_with_wf
from app.validate import luac_check, static_guard_violations


def load_tasks(path: Path | None = None) -> list[dict]:
    p = path or (ROOT / "benchmarks" / "public_tasks.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def heuristic_pass(code: str, expected_contains: list[str]) -> bool:
    return all(s in code for s in expected_contains)


async def run_one_direct(
    client: httpx.AsyncClient,
    settings: Settings,
    task: dict,
) -> dict:
    t0 = time.perf_counter()
    code, log, _dbg = await generate_lua(
        client,
        settings,
        task["prompt"],
        context=task.get("context"),
        return_debug=False,
    )
    dt = time.perf_counter() - t0
    return {"code": code, "log": log, "latency_s": dt}


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


async def main_async(args: argparse.Namespace) -> int:
    tasks = load_tasks(Path(args.tasks) if args.tasks else None)
    settings = Settings()
    results = []
    if args.http:
        async with httpx.AsyncClient(base_url=args.base_url, timeout=180.0) as hc:
            for t in tasks:
                try:
                    t0 = time.perf_counter()
                    payload = {"prompt": t["prompt"]}
                    if t.get("context") is not None:
                        payload["context"] = t["context"]
                    r = await hc.post("/generate", json=payload)
                    r.raise_for_status()
                    data = r.json()
                    code = data.get("code", "")
                    dt = time.perf_counter() - t0
                    sc = score_task(t, code)
                    results.append(
                        {
                            "id": t["id"],
                            **sc,
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


def main() -> None:
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
    args = ap.parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
