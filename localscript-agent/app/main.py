from __future__ import annotations

import logging
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
from app.ollama_client import ollama_http_ok_and_model_ready, ollama_warmup
from app.pipeline import run_debug_pipeline, run_generate_pipeline, run_refine_pipeline

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create shared HTTP client and optional Ollama warmup on startup."""
    app.state.http = httpx.AsyncClient()
    if settings.ollama_warmup_enabled:
        client: httpx.AsyncClient = app.state.http
        try:
            await ollama_warmup(client, settings)
        except Exception:
            logger.warning("ollama_warmup_failed", exc_info=True)
    yield
    await app.state.http.aclose()


app = FastAPI(title="LocalScript API", version="1.0.0", lifespan=lifespan)


@app.get("/health", response_model=HealthResponse)
async def health():
    """Report API, Ollama transport, and model readiness status."""
    client: httpx.AsyncClient = app.state.http
    http_ok, model_ready = await ollama_http_ok_and_model_ready(client, settings)
    return HealthResponse(
        status="ok" if http_ok and model_ready else "degraded",
        ollama_reachable=http_ok,
        model_ready=model_ready,
        model=settings.ollama_model,
        num_ctx=settings.num_ctx,
        num_predict=settings.num_predict,
        batch=settings.num_batch,
        parallel=settings.num_parallel,
        gpu_only=bool(settings.ollama_num_gpu),
    )


@app.post("/generate", response_model=GenerateResponse, response_model_exclude_none=True)
async def generate(body: GenerateRequest):
    """Generate Lua for a new task and run validation/repair pipeline."""
    client: httpx.AsyncClient = app.state.http
    try:
        return await run_generate_pipeline(client, settings, body)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.post("/refine", response_model=GenerateResponse, response_model_exclude_none=True)
async def refine(body: RefineRequest):
    """Refine previously generated Lua using full refinement history."""
    client: httpx.AsyncClient = app.state.http
    try:
        return await run_refine_pipeline(client, settings, body)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.post("/debug", response_model=DebugResponse, response_model_exclude_none=True)
async def debug(body: DebugRequest):
    """Run debug checks plus one review pass for user-supplied code."""
    client: httpx.AsyncClient = app.state.http
    try:
        return await run_debug_pipeline(client, settings, body)
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
