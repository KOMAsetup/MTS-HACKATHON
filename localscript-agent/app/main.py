from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException

from app.config import settings
from app.models_io import (
    GenerateRequest,
    GenerateResponse,
    HealthResponse,
    RefineRequest,
)
from app.ollama_client import ollama_health
from app.pipeline import generate_lua


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient()
    yield
    await app.state.http.aclose()


app = FastAPI(title="LocalScript API", version="1.0.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health():
    client: httpx.AsyncClient = app.state.http
    ok = await ollama_health(client, settings)
    return HealthResponse(
        status="ok" if ok else "degraded",
        ollama_reachable=ok,
        model=settings.ollama_model,
    )


@app.post("/generate", response_model=GenerateResponse, response_model_exclude_none=True)
async def generate(body: GenerateRequest):
    client: httpx.AsyncClient = app.state.http
    try:
        code, _log, dbg = await generate_lua(
            client,
            settings,
            body.prompt,
            context=body.context,
            previous_code=body.previous_code,
            feedback=body.feedback,
            return_debug=body.debug,
        )
        return GenerateResponse(code=code, debug=dbg if body.debug else None)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.post("/refine", response_model=GenerateResponse, response_model_exclude_none=True)
async def refine(body: RefineRequest):
    """Second-turn refinement with explicit feedback (agentness / demo)."""
    client: httpx.AsyncClient = app.state.http
    try:
        code, _log, dbg = await generate_lua(
            client,
            settings,
            body.prompt,
            context=body.context,
            previous_code=body.previous_code,
            feedback=body.feedback,
            return_debug=body.debug,
        )
        return GenerateResponse(code=code, debug=dbg if body.debug else None)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
