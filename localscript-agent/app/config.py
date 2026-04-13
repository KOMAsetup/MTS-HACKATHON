from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", env_file=".env", extra="ignore")

    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5-coder:7b"
    ollama_timeout_s: float = 120.0
    ollama_max_retries: int = 3
    ollama_retry_backoff_s: float = 1.5

    num_ctx: int = 4096
    num_predict: int = 256
    num_batch: int = 1
    num_parallel: int = 1
    temperature: float = 0.2
    top_p: float = 0.95

    max_repair_attempts: int = 2
    luac_path: str = "luac"
    lua_path: str = "lua"

    validation_linter: bool = False
    linter_path: str = "selene"
    linter_timeout_s: float = 30.0

    # Ollama sets GPU layers; 999 typically means all layers on GPU (no CPU offload of weights)
    ollama_num_gpu: int = 999


settings = Settings()
