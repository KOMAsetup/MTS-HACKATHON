from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import streamlit as st


def _load_json(text: str, field_name: str) -> tuple[Any | None, str | None]:
    text = text.strip()
    if not text:
        return None, None
    try:
        return json.loads(text), None
    except json.JSONDecodeError as e:
        return None, f"{field_name}: invalid JSON ({e})"


def _post_json(
    base_url: str,
    endpoint: str,
    payload: dict,
) -> tuple[dict[str, Any] | None, str | None]:
    url = base_url.rstrip("/") + endpoint
    try:
        with httpx.Client(timeout=180.0) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, dict):
                return None, "Response is not a JSON object."
            return data, None
    except Exception as e:  # noqa: BLE001
        return None, str(e)


def _get_json(base_url: str, endpoint: str) -> tuple[dict[str, Any] | None, str | None]:
    url = base_url.rstrip("/") + endpoint
    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.get(url)
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, dict):
                return None, "Response is not a JSON object."
            return data, None
    except Exception as e:  # noqa: BLE001
        return None, str(e)


def _history_file() -> Path:
    return Path(__file__).resolve().parents[1] / "artifacts" / "gui_chat_history.jsonl"


def _append_history(
    endpoint: str,
    payload: dict[str, Any] | None,
    response: dict[str, Any] | None,
    error: str | None,
) -> None:
    item = {
        "ts": datetime.now().isoformat(),
        "endpoint": endpoint,
        "payload": payload,
        "response": response,
        "error": error,
    }
    st.session_state["chat_history"] = [*st.session_state.get("chat_history", []), item]


def _merge_context_into_prompt(prompt: str, context: dict[str, Any] | None) -> str:
    if not isinstance(context, dict) or not context:
        return prompt.strip()
    return f"{prompt.strip()}\n\nContext:\n{json.dumps(context, ensure_ascii=False, indent=2)}"


def _init_state() -> None:
    st.session_state.setdefault("prompt", "")
    st.session_state.setdefault("context_json", "{}")
    st.session_state.setdefault("clarification_history_json", "[]")
    st.session_state.setdefault("refinement_history_json", "[]")
    st.session_state.setdefault("debug_history_json", "[]")
    st.session_state.setdefault("debug_code", "")
    st.session_state.setdefault("debug_prompt", "")
    st.session_state.setdefault("max_repair_attempts", 2)
    st.session_state.setdefault("enable_semantic_validation", False)
    st.session_state.setdefault(
        "semantic_rules_json",
        json.dumps(
            {
                "expected_type": "array",
                "expected_len": 2,
                "required_keys": ["name", "score"],
            },
            ensure_ascii=False,
            indent=2,
        ),
    )
    st.session_state.setdefault("last_response", None)
    st.session_state.setdefault("last_error", None)
    st.session_state.setdefault("last_request", None)
    st.session_state.setdefault("action_status", None)
    st.session_state.setdefault("chat_history", [])


def main() -> None:
    st.set_page_config(page_title="LocalScript Demo UI (tim API)", layout="wide")
    _init_state()

    st.title("LocalScript Demo UI (tim API style)")
    st.caption("Works with /health, /generate, /refine, /debug")

    with st.sidebar:
        base_url = st.text_input("API base URL", value="http://127.0.0.1:8080")
        if st.button("Check /health"):
            resp, err = _get_json(base_url, "/health")
            st.session_state["last_response"] = resp
            st.session_state["last_error"] = err
            st.session_state["last_request"] = {
                "method": "GET",
                "endpoint": "/health",
                "payload": None,
            }
            _append_history("/health", None, resp, err)
        st.markdown("---")
        if st.button("Save chat history", use_container_width=True):
            path = _history_file()
            path.parent.mkdir(parents=True, exist_ok=True)
            lines = [
                json.dumps(x, ensure_ascii=False)
                for x in st.session_state.get("chat_history", [])
            ]
            path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
            st.success(f"Saved: {path}")
        if st.button("Load chat history", use_container_width=True):
            path = _history_file()
            if path.exists():
                rows = []
                for line in path.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
                st.session_state["chat_history"] = rows
                st.success(f"Loaded {len(rows)} entries")
            else:
                st.warning("History file not found.")
        if st.button("Clear chat history", use_container_width=True):
            st.session_state["chat_history"] = []
            st.success("History cleared.")

    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("Input")
        with st.expander("Field guide", expanded=False):
            st.markdown(
                "- `Prompt`: task for generation.\n"
                "- `Context JSON`: optional context merged into prompt text as `Context:` block.\n"
                "- `Enable semantic validation`: inject semantic checks into context block.\n"
                "- `Semantic rules JSON`: semantic checks for result object/stdout.\n"
                "- `Clarification history JSON`: tim-style list for `/generate`.\n"
                "- `Refinement history JSON`: tim-style list for `/refine`.\n"
                "- `Debug code/prompt/history`: inputs for `/debug`.\n"
                "- `Max repair attempts`: optional server override."
            )
        st.session_state["prompt"] = st.text_area(
            "Prompt",
            value=st.session_state["prompt"],
            height=110,
        )
        st.session_state["context_json"] = st.text_area(
            "Context JSON (merged into prompt text)",
            value=st.session_state["context_json"],
            height=140,
        )
        st.session_state["enable_semantic_validation"] = st.checkbox(
            "Enable semantic validation for this request",
            value=st.session_state["enable_semantic_validation"],
            help=(
                "When enabled, GUI injects '__semantic_validation' into Context JSON. "
                "Backend extracts Context from prompt and runs semantic checks."
            ),
        )
        st.session_state["semantic_rules_json"] = st.text_area(
            "Semantic rules JSON",
            value=st.session_state["semantic_rules_json"],
            height=130,
            help='Example: {"expected_type":"array","expected_len":2}',
        )
        st.session_state["clarification_history_json"] = st.text_area(
            "Clarification history JSON",
            value=st.session_state["clarification_history_json"],
            height=120,
            help='Example: [{"model_question":"...","user_answer":"..."}]',
        )
        st.session_state["refinement_history_json"] = st.text_area(
            "Refinement history JSON",
            value=st.session_state["refinement_history_json"],
            height=140,
            help='Example: [{"assistant_code":"...","user_feedback":"...","checks":[]}]',
        )
        st.session_state["max_repair_attempts"] = st.number_input(
            "Max repair attempts",
            min_value=0,
            max_value=10,
            value=int(st.session_state["max_repair_attempts"]),
            step=1,
        )
        st.markdown("### Debug input")
        st.session_state["debug_code"] = st.text_area(
            "Debug code",
            value=st.session_state["debug_code"],
            height=110,
        )
        st.session_state["debug_prompt"] = st.text_area(
            "Debug prompt (optional)",
            value=st.session_state["debug_prompt"],
            height=70,
        )
        st.session_state["debug_history_json"] = st.text_area(
            "Debug history JSON",
            value=st.session_state["debug_history_json"],
            height=110,
        )

        c1, c2 = st.columns(2)
        with c1:
            do_generate = st.button("POST /generate", use_container_width=True)
            do_refine = st.button("POST /refine", use_container_width=True)
        with c2:
            do_debug = st.button("POST /debug", use_container_width=True)

    context, context_err = _load_json(st.session_state["context_json"], "context")
    clarification_history, clar_err = _load_json(
        st.session_state["clarification_history_json"], "clarification_history"
    )
    refinement_history, refine_err = _load_json(
        st.session_state["refinement_history_json"], "refinement_history"
    )
    debug_history, debug_hist_err = _load_json(
        st.session_state["debug_history_json"],
        "debug_history",
    )
    semantic_rules, sem_err = _load_json(
        st.session_state["semantic_rules_json"],
        "semantic_rules",
    )

    errors = [e for e in [context_err, clar_err, refine_err, debug_hist_err, sem_err] if e]
    for e in errors:
        st.warning(e)

    if context is not None and not isinstance(context, dict):
        st.warning("context: JSON must be object or null.")
        context = None
    if clarification_history is None:
        clarification_history = []
    if refinement_history is None:
        refinement_history = []
    if debug_history is None:
        debug_history = []
    if not isinstance(clarification_history, list):
        st.warning("clarification_history: must be JSON array.")
        clarification_history = []
    if not isinstance(refinement_history, list):
        st.warning("refinement_history: must be JSON array.")
        refinement_history = []
    if not isinstance(debug_history, list):
        st.warning("debug_history: must be JSON array.")
        debug_history = []
    if semantic_rules is not None and not isinstance(semantic_rules, dict):
        st.warning("semantic_rules: JSON must be object.")
        semantic_rules = None

    context_for_prompt = context
    if st.session_state["enable_semantic_validation"]:
        if context_for_prompt is None:
            context_for_prompt = {}
        if isinstance(context_for_prompt, dict):
            context_for_prompt = dict(context_for_prompt)
            if isinstance(semantic_rules, dict):
                context_for_prompt["__semantic_validation"] = semantic_rules

    prompt_ok = bool(st.session_state["prompt"].strip())
    debug_code_ok = bool(st.session_state["debug_code"].strip())
    refine_steps = list(refinement_history)
    semantic_ok = (
        not st.session_state["enable_semantic_validation"] or isinstance(semantic_rules, dict)
    )

    readiness = {
        "/generate": (
            []
            if prompt_ok and semantic_ok
            else ["prompt is empty" if not prompt_ok else "semantic_rules invalid"]
        ),
        "/refine": (
            []
            if (
                prompt_ok
                and isinstance(refine_steps, list)
                and len(refine_steps) > 0
                and semantic_ok
            )
            else ["prompt/refinement_history/semantic_rules invalid"]
        ),
        "/debug": [] if debug_code_ok else ["debug_code is empty"],
    }

    st.markdown("### Action readiness")
    for endpoint, blockers in readiness.items():
        icon = "✅" if not blockers else "⛔"
        st.markdown(f"**{icon} {endpoint}**")
        if blockers:
            st.caption("Blocked by: " + "; ".join(blockers))
        else:
            st.caption("Ready to send.")

    def run_post(endpoint: str, payload: dict[str, Any]) -> None:
        st.session_state["last_request"] = {
            "method": "POST",
            "endpoint": endpoint,
            "payload": payload,
        }
        resp, err = _post_json(base_url, endpoint, payload)
        st.session_state["last_response"] = resp
        st.session_state["last_error"] = err
        _append_history(endpoint, payload, resp, err)
        st.session_state["action_status"] = {
            "kind": "error" if err else "success",
            "endpoint": endpoint,
            "message": err or "Request sent and response received.",
        }

    if do_generate:
        blockers = readiness["/generate"]
        if blockers:
            st.session_state["action_status"] = {
                "kind": "blocked",
                "endpoint": "/generate",
                "message": "; ".join(blockers),
            }
        else:
            prompt = _merge_context_into_prompt(st.session_state["prompt"], context_for_prompt)
            payload = {
                "prompt": prompt,
                "clarification_history": clarification_history,
                "max_repair_attempts": int(st.session_state["max_repair_attempts"]),
            }
            run_post("/generate", payload)

    if do_refine:
        blockers = readiness["/refine"]
        if blockers:
            st.session_state["action_status"] = {
                "kind": "blocked",
                "endpoint": "/refine",
                "message": "; ".join(blockers),
            }
        else:
            prompt = _merge_context_into_prompt(st.session_state["prompt"], context_for_prompt)
            payload = {
                "prompt": prompt,
                "refinement_history": refine_steps,
                "max_repair_attempts": int(st.session_state["max_repair_attempts"]),
            }
            run_post("/refine", payload)

    if do_debug:
        blockers = readiness["/debug"]
        if blockers:
            st.session_state["action_status"] = {
                "kind": "blocked",
                "endpoint": "/debug",
                "message": "; ".join(blockers),
            }
        else:
            payload = {"code": st.session_state["debug_code"], "debug_history": debug_history}
            if st.session_state["debug_prompt"].strip():
                payload["prompt"] = st.session_state["debug_prompt"].strip()
            run_post("/debug", payload)

    with col_right:
        st.subheader("Last request / response")
        action_status = st.session_state.get("action_status")
        if isinstance(action_status, dict):
            kind = action_status.get("kind")
            endpoint = action_status.get("endpoint")
            message = action_status.get("message")
            text = f"{endpoint}: {message}" if endpoint else str(message)
            if kind == "success":
                st.success(text)
            elif kind == "blocked":
                st.warning(text)
            elif kind == "error":
                st.error(text)
        if st.session_state["last_request"] is not None:
            st.markdown("**Request**")
            st.json(st.session_state["last_request"], expanded=False)
        if st.session_state["last_error"]:
            st.error(st.session_state["last_error"])
        if st.session_state["last_response"] is not None:
            st.markdown("**Response**")
            st.json(st.session_state["last_response"], expanded=True)
            code = st.session_state["last_response"].get("code")
            if isinstance(code, str):
                st.markdown("**Code**")
                st.code(code, language="lua")
        hist = st.session_state.get("chat_history", [])
        with st.expander(f"Chat history ({len(hist)})", expanded=False):
            if not hist:
                st.caption("No history yet.")
            else:
                idx = st.selectbox(
                    "Select turn",
                    options=list(range(len(hist))),
                    index=len(hist) - 1,
                    format_func=lambda i: (
                        f"#{i + 1} {hist[i].get('ts', '')} "
                        f"{hist[i].get('endpoint', '')}"
                    ),
                )
                selected = hist[idx]
                st.json(selected, expanded=False)
                if st.button("Load selected turn into response panel", use_container_width=True):
                    st.session_state["last_request"] = {
                        "method": "POST",
                        "endpoint": selected.get("endpoint"),
                        "payload": selected.get("payload"),
                    }
                    st.session_state["last_response"] = selected.get("response")
                    st.session_state["last_error"] = selected.get("error")
                    st.rerun()

    st.divider()
    st.caption("tim-style flow: /generate -> if needed /refine -> optional /debug.")


if __name__ == "__main__":
    main()
