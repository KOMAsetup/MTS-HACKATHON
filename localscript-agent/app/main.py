from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException

from app.config import settings
from app.models_io import GenerateRequest, GenerateResponse, HealthResponse, RefineRequest
from app.ollama_client import ollama_http_ok_and_model_ready, ollama_warmup
from app.pipeline import generate_lua

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    client: httpx.AsyncClient = app.state.http
    http_ok, model_ready = await ollama_http_ok_and_model_ready(client, settings)
    status = "ok" if http_ok and model_ready else "degraded"
    gpu_only = bool(settings.ollama_num_gpu)
    return HealthResponse(
        status=status,
        ollama_reachable=http_ok,
        model_ready=model_ready,
        model=settings.ollama_model,
        num_ctx=settings.num_ctx,
        num_predict=settings.num_predict,
        batch=settings.num_batch,
        parallel=settings.num_parallel,
        gpu_only=gpu_only,
    )


@app.post("/generate", response_model=GenerateResponse)
async def generate(body: GenerateRequest):
    client: httpx.AsyncClient = app.state.http
    try:
        code, _log = await generate_lua(
            client,
            settings,
            body.prompt,
            context=body.context,
            previous_code=body.previous_code,
            feedback=body.feedback,
        )
        return GenerateResponse(code=code)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@app.post("/refine", response_model=GenerateResponse)
async def refine(body: RefineRequest):
    """Second-turn refinement with explicit feedback (agentness / demo)."""
    client: httpx.AsyncClient = app.state.http
    try:
        code, _log = await generate_lua(
            client,
            settings,
            body.prompt,
            context=body.context,
            previous_code=body.previous_code,
            feedback=body.feedback,
        )
        return GenerateResponse(code=code)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
