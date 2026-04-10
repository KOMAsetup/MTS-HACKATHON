from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    """OpenAPI requires `prompt`; optional fields extend PDF-style tasks and agent loop."""

    prompt: str = Field(..., min_length=1)
    context: dict[str, Any] | None = None
    previous_code: str | None = None
    feedback: str | None = None


class GenerateResponse(BaseModel):
    code: str


class RefineRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    context: dict[str, Any] | None = None
    previous_code: str = Field(..., min_length=1)
    feedback: str = Field(..., min_length=1)


class HealthResponse(BaseModel):
    status: str
    ollama_reachable: bool
    model: str
