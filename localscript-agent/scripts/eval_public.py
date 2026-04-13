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


def _infra_failure_from_errors(errors: list[str]) -> bool:
    for msg in errors:
        if "not found" in msg and ("lua" in msg or "luac" in msg):
            return True
    return False


def _is_infra_exception(exc: BaseException) -> bool:
    return isinstance(exc, (httpx.HTTPError, TimeoutError, OSError))


async def run_one_direct(
    client: httpx.AsyncClient,
    settings: Settings,
    task: dict,
) -> dict:
    t0 = time.perf_counter()
    code, log = await generate_lua(
        client,
        settings,
        task["prompt"],
        context=task.get("context"),
    )
    dt = time.perf_counter() - t0
    return {"code": code, "log": log, "latency_s": dt}


def score_task(task: dict, code: str, *, settings: Settings) -> dict:
    ev = task.get("eval") or {}
    et = ev.get("type", "heuristic")
    errs: list[str] = []

    ok_l, msg = luac_check(code, luac_path=settings.luac_path)
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
        sb_ok, out, err = run_lua_with_wf(code, wf_root, lua_bin=settings.lua_path)
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
        "static_ok": static_ok,
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
                infra_fail = False
                generation_error = False
                latency_s: float | None = None
                code = ""
                try:
                    t0 = time.perf_counter()
                    payload = {"prompt": t["prompt"]}
                    if t.get("context") is not None:
                        payload["context"] = t["context"]
                    r = await hc.post("/generate", json=payload)
                    r.raise_for_status()
                    data = r.json()
                    code = data.get("code", "") or ""
                    dt = time.perf_counter() - t0
                    sc = score_task(t, code, settings=settings)
                    if _infra_failure_from_errors(sc["errors"]):
                        infra_fail = True
                    if not code.strip():
                        generation_error = True
                    latency_s = float(dt)
                except Exception as e:
                    latency_s = None
                    code = ""
                    if _is_infra_exception(e):
                        infra_fail = True
                    else:
                        generation_error = True
                    sc = {
                        "syntax_ok": False,
                        "static_ok": False,
                        "sandbox_ok": False,
                        "heuristic_ok": False,
                        "errors": [str(e)],
                        "pass": False,
                    }

                row = {
                    "id": t["id"],
                    **sc,
                    "latency_s": latency_s,
                    "infra_fail": infra_fail,
                    "generation_error": generation_error,
                    "model_error": False,
                    "code_preview": code[:200],
                }

                if not row["pass"] and not row["infra_fail"] and not row["generation_error"]:
                    row["model_error"] = True
                results.append(row)
    else:
        client = httpx.AsyncClient()
        try:
            for t in tasks:
                infra_fail = False
                generation_error = False
                latency_s: float | None = None
                try:
                    r = await run_one_direct(client, settings, t)
                    code = r["code"]
                    sc = score_task(t, code, settings=settings)
                    if _infra_failure_from_errors(sc["errors"]):
                        infra_fail = True
                    if not (code or "").strip():
                        generation_error = True
                    latency_s = float(r["latency_s"])
                except Exception as e:
                    latency_s = None
                    if _is_infra_exception(e):
                        infra_fail = True
                    else:
                        generation_error = True
                    sc = {
                        "syntax_ok": False,
                        "static_ok": False,
                        "sandbox_ok": False,
                        "heuristic_ok": False,
                        "errors": [str(e)],
                        "pass": False,
                    }
                    code = ""

                row = {
                    "id": t["id"],
                    **sc,
                    "latency_s": latency_s,
                    "infra_fail": infra_fail,
                    "generation_error": generation_error,
                    "model_error": False,
                    "code_preview": (code or "")[:200],
                }
                if not row["pass"] and not row["infra_fail"] and not row["generation_error"]:
                    row["model_error"] = True
                results.append(row)
        finally:
            await client.aclose()

    passed = sum(1 for x in results if x.get("pass"))
    lat_samples = [x["latency_s"] for x in results if x.get("latency_s") is not None]
    lat_samples_f = [float(x) for x in lat_samples]
    lat_samples_f.sort()
    p95_idx = int(0.95 * (len(lat_samples_f) - 1)) if lat_samples_f else 0
    metrics = {
        "total": len(tasks),
        "passed": passed,
        "syntax_ok": sum(1 for x in results if x.get("syntax_ok")),
        "static_ok": sum(1 for x in results if x.get("static_ok")),
        "sandbox_ok": sum(1 for x in results if x.get("sandbox_ok")),
        "heuristic_ok": sum(1 for x in results if x.get("heuristic_ok")),
        "infra_fail": sum(1 for x in results if x.get("infra_fail")),
        "generation_error": sum(1 for x in results if x.get("generation_error")),
        "model_error": sum(1 for x in results if x.get("model_error")),
        "latency_avg": (sum(lat_samples_f) / len(lat_samples_f)) if lat_samples_f else None,
        "latency_p95": lat_samples_f[p95_idx] if lat_samples_f else None,
        "latency_samples": len(lat_samples_f),
    }
    out = {
        "metrics": metrics,
        "results": results,
        "settings": settings.model_dump(),
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
