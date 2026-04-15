from __future__ import annotations

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5-coder:7b"
    ollama_timeout_s: float = 120.0
    ollama_max_retries: int = 3
    ollama_retry_backoff_s: float = 1.5
    ollama_health_timeout_s: float = Field(
        default=5.0,
        validation_alias=AliasChoices("OLLAMA_HEALTH_TIMEOUT_SECONDS", "ollama_health_timeout_s"),
    )
    ollama_warmup_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("OLLAMA_WARMUP_ENABLED", "ollama_warmup_enabled"),
    )
    ollama_warmup_timeout_s: float = Field(
        default=240.0,
        validation_alias=AliasChoices("OLLAMA_WARMUP_TIMEOUT_SECONDS", "ollama_warmup_timeout_s"),
    )

    num_ctx: int = 4096
    num_predict: int = 256
    num_batch: int = 1
    num_parallel: int = 1
    temperature: float = 0.2
    top_p: float = 0.95

    max_repair_attempts: int = 2
    max_repair_server_cap: int = 5

    # If false, generate uses code-only JSON (no clarification branch); for deterministic eval.
    clarification_mode: bool = True
    luac_path: str = "luac"
    lua_path: str = "lua"

    validation_linter: bool = False
    linter_path: str = "selene"
    linter_timeout_s: float = 30.0
    enable_semantic_validation: bool = Field(
        default=False,
        validation_alias=AliasChoices("ENABLE_SEMANTIC_VALIDATION", "enable_semantic_validation"),
    )
    semantic_context_key: str = "__semantic_validation"

    # Ollama sets GPU layers; 999 typically means all layers on GPU (no CPU offload of weights)
    ollama_num_gpu: int = 999


settings = Settings()
