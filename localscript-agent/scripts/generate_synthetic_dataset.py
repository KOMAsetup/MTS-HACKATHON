#!/usr/bin/env python3
"""
Deterministic expansion of verified LowCode templates (agent-authored patterns only).
Does NOT call any LLM. Output JSONL for optional QLoRA / smoke eval.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.validate import validate_code


def gen_last_of_list(rng: random.Random, n: int) -> tuple[dict, str, str]:
    names = [f"user{i}@example.com" for i in range(n)]
    ctx = {"wf": {"vars": {"emails": names}}}
    prompt = "Из полученного списка email получи последний."
    code = "return wf.vars.emails[#wf.vars.emails]"
    return ctx, prompt, code


def gen_counter(rng: random.Random, start: int) -> tuple[dict, str, str]:
    ctx = {"wf": {"vars": {"try_count_n": start}}}
    prompt = "Увеличивай значение переменной try_count_n на каждой итерации"
    code = "return wf.vars.try_count_n + 1"
    return ctx, prompt, code


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "data/synthetic/generated.jsonl")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--count", type=int, default=20)
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    rows = []
    for i in range(args.count):
        if i % 2 == 0:
            ctx, prompt, code = gen_last_of_list(rng, rng.randint(2, 8))
        else:
            ctx, prompt, code = gen_counter(rng, rng.randint(0, 100))
        ok, errs = validate_code(code)
        if not ok:
            raise SystemExit(f"template invalid: {errs}")
        rows.append(
            {
                "id": f"synth_{args.seed}_{i}",
                "prompt": prompt,
                "context": ctx,
                "reference_code": code,
                "tags": ["template-expanded", "lowcode"],
            }
        )
    with open(args.out, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Wrote {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
