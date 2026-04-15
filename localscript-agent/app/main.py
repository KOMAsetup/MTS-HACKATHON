from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException

from app.config import settings
from app.models_io import (
    DebugRequest,
    DebugResponse,
    GenerateRequest,
    GenerateResponse,
    HealthResponse,
    RefineRequest,
)
from app.ollama_client import ollama_health
from app.pipeline import run_debug_pipeline, run_generate_pipeline, run_refine_pipeline


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
        return await run_generate_pipeline(client, settings, body)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.post("/refine", response_model=GenerateResponse, response_model_exclude_none=True)
async def refine(body: RefineRequest):
    client: httpx.AsyncClient = app.state.http
    try:
        return await run_refine_pipeline(client, settings, body)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.post("/debug", response_model=DebugResponse, response_model_exclude_none=True)
async def debug(body: DebugRequest):
    client: httpx.AsyncClient = app.state.http
    try:
        return await run_debug_pipeline(client, settings, body)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
