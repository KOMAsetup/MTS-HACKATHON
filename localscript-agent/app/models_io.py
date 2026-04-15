from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ResponseKind(str, Enum):
    clarification = "clarification"
    code = "code"


class StopReason(str, Enum):
    validation_ok = "validation_ok"
    max_repairs_exhausted = "max_repairs_exhausted"
    error = "error"


class CheckItem(BaseModel):
    id: str
    stage: str
    passed: bool
    message: str = ""


class AttemptRecord(BaseModel):
    index: int = Field(ge=0)
    kind: str  # "initial" | "repair"
    code: str
    checks: list[CheckItem] = Field(default_factory=list)


class ClarificationTurn(BaseModel):
    model_question: str
    user_answer: str


class RefinementStep(BaseModel):
    assistant_code: str = Field(..., min_length=1)
    user_feedback: str = Field(..., min_length=1)
    checks: list[CheckItem] = Field(..., min_length=0)


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    max_repair_attempts: int | None = Field(
        default=None,
        ge=0,
        description="Override max repair rounds; capped server-side",
    )
    clarification_history: list[ClarificationTurn] = Field(default_factory=list)


class RefineRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    refinement_history: list[RefinementStep] = Field(..., min_length=1)
    max_repair_attempts: int | None = Field(default=None, ge=0)


class GenerateResponse(BaseModel):
    response_kind: ResponseKind
    clarification_question: str | None = None
    code: str | None = None
    attempts: list[AttemptRecord] = Field(default_factory=list)
    all_checks_passed: bool | None = None
    degraded: bool | None = None
    stop_reason: StopReason | None = None
    llm_rounds: int | None = None
    repair_rounds_used: int | None = None
    parse_warning: str | None = None


class DebugHistoryTurn(BaseModel):
    user_code: str
    user_prompt: str | None = None
    checks: list[CheckItem]
    problem_description: str
    suggested_code: str


class DebugRequest(BaseModel):
    code: str = Field(..., min_length=1)
    prompt: str | None = None
    debug_history: list[DebugHistoryTurn] = Field(default_factory=list)


class DebugResponse(BaseModel):
    checks: list[CheckItem]
    all_checks_passed: bool
    problem_description: str
    suggested_code: str


class HealthResponse(BaseModel):
    status: str
    ollama_reachable: bool
    model: str
