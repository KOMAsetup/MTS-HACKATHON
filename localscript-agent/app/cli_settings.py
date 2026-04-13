"""Defaults for the demo CLI. Override via env `LOCALSCRIPT_CLI_*` or file `.env.cli` in cwd."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CliSettings(BaseSettings):
    """
    Environment prefix: LOCALSCRIPT_CLI_

    Examples:
        LOCALSCRIPT_CLI_BASE_URL=http://localhost:8080
        LOCALSCRIPT_CLI_HTTP_TIMEOUT_S=300
        LOCALSCRIPT_CLI_DEFAULT_CONTEXT_FILE=/path/to/context.json
    """

    model_config = SettingsConfigDict(
        env_prefix="LOCALSCRIPT_CLI_",
        env_file=".env.cli",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    base_url: str = Field(default="http://127.0.0.1:8080", description="LocalScript API root")
    http_timeout_s: float = Field(
        default=180.0,
        ge=1.0,
        description="HTTP timeout for /generate and /refine",
    )
    default_context_file: str | None = Field(
        default=None,
        description="Optional path to JSON file used as request `context` until cleared in CLI",
    )
    request_server_debug: bool = Field(
        default=True,
        description="If true, send debug:true on /generate and /refine; responses buffered for /debug",
    )
    attach_previous_code: bool = Field(
        default=False,
        description=(
            "If true, each /generate sends previous_code=last assistant code (debug/fix mode)"
        ),
    )


def load_json_context(path: str | Path) -> dict:
    p = Path(path).expanduser().resolve()
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Context JSON must be an object at the top level")
    return data
