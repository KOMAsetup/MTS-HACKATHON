from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    """OpenAPI requires `prompt`; optional fields extend PDF-style tasks and agent loop."""

    prompt: str = Field(..., min_length=1)
    context: dict[str, Any] | None = None
    previous_code: str | None = None
    feedback: str | None = None
    debug: bool = Field(
        default=False,
        description="If true, response includes validation/repair diagnostics",
    )


class GenerateDebugMeta(BaseModel):
    """Populated when request.debug is true."""

    first_validation_ok: bool
    final_validation_ok: bool
    llm_rounds: int = Field(ge=1, description="Ollama chat calls: initial + each repair")
    repair_rounds_used: int = Field(
        ge=0,
        description="Repair loop iterations that ran (0 if validation passed on first code)",
    )
    max_repair_attempts: int = Field(ge=0)
    degraded: bool = Field(
        description="True if final code still fails static validation after all repairs",
    )
    log: list[str]


class GenerateResponse(BaseModel):
    code: str
    debug: GenerateDebugMeta | None = None


class RefineRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    context: dict[str, Any] | None = None
    previous_code: str = Field(..., min_length=1)
    feedback: str = Field(..., min_length=1)
    debug: bool = Field(
        default=False,
        description="If true, response includes validation/repair diagnostics",
    )


class HealthResponse(BaseModel):
    status: str
    ollama_reachable: bool
    model: str
