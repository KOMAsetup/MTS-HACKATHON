from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen


def main() -> None:
    requests = [
        {
            "name": "HEALTH",
            "method": "GET",
            "url": "http://127.0.0.1:8080/health",
            "body": None,
        },
        {
            "name": "STEP1",
            "method": "POST",
            "url": "http://127.0.0.1:8080/generate-from-clarify",
            "body": {
                "prompt": "Отфильтруй parsedCsv и оставь только строки, где Discount не пустой",
                "context": None,
                "answers": [],
            },
        },
        {
            "name": "STEP2",
            "method": "POST",
            "url": "http://127.0.0.1:8080/generate-from-clarify",
            "body": {
                "prompt": "Отфильтруй parsedCsv и оставь только строки, где Discount не пустой",
                "context": None,
                "answers": [
                    {
                        "id": "q_context_json",
                        "text": (
                            '{"wf":{"vars":{"parsedCsv":['
                            '{"SKU":"A001","Discount":"10%","Markdown":""},'
                            '{"SKU":"A002","Discount":"","Markdown":""},'
                            '{"SKU":"A003","Discount":"5%","Markdown":""}'
                            "]}}}"
                        ),
                    }
                ],
            },
        },
        {
            "name": "STEP3",
            "method": "POST",
            "url": "http://127.0.0.1:8080/refine",
            "body": {
                "prompt": "То же задание",
                "previous_code": "return wf.vars.parsedCsv",
                "feedback": (
                    'Используй _utils.array.new(), table.insert и фильтрацию Discount != ""'
                ),
            },
        },
    ]

    out: list[str] = []
    for item in requests:
        name = item["name"]
        method = item["method"]
        url = item["url"]
        body = item["body"]

        out.append(f"=== {name} INPUT ===")
        out.append(f"METHOD: {method}")
        out.append(f"URL: {url}")
        if body is None:
            out.append("BODY: <none>")
            raw = urlopen(url, timeout=20).read().decode("utf-8")
        else:
            body_json = json.dumps(body, ensure_ascii=False)
            out.append(f"BODY: {body_json}")
            req = Request(
                url,
                data=body_json.encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            raw = urlopen(req, timeout=120).read().decode("utf-8")

        out.append(f"=== {name} OUTPUT ===")
        out.append(raw)
        out.append("")

    target = Path("artifacts/demo_input_output.txt")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(out), encoding="utf-8")
    print(str(target))


if __name__ == "__main__":
    main()
