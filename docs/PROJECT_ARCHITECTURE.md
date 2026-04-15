# Стек и архитектура проекта

## Технологический стек

### Backend и API

- Python 3.11
- FastAPI + Uvicorn
- Pydantic / pydantic-settings
- httpx (вызовы к Ollama)

### LLM-слой

- Ollama как локальный inference runtime
- Базовая модель: `qwen2.5-coder:7b`
- Параметры по умолчанию: `num_ctx=4096`, `num_predict=256`, `batch=1`, `parallel=1`

### Проверка качества Lua

- syntax: `luac -p`
- static guard: regex-ограничения по опасным API
- optional linter: `selene`
- optional semantic validation через sandbox-прогон Lua

### Клиенты

- CLI-клиент (`scripts/demo_cli.py`)
- Streamlit GUI (`scripts/demo_streamlit.py`)
- Любой HTTP-клиент (`curl`, Postman, frontend)

### Развёртывание

- Docker Compose (`localscript-agent/docker-compose.yml`)
- Два основных сервиса: `app` и `ollama`
- Для GPU-режима используется `gpus: all`

## Архитектурные модули

- `app/main.py` — FastAPI endpoints и lifespan.
- `app/pipeline.py` — orchestration generate/refine/debug и repair loop.
- `app/prompts.py` — system/user prompts для разных режимов.
- `app/ollama_client.py` — transport к Ollama (`/api/chat`, `/api/tags`).
- `app/validate.py`, `app/code_checks.py` — статические/синтаксические/дополнительные проверки.
- `app/semantic.py`, `app/sandbox.py` — semantic-валидация по контекстным правилам.
- `app/models_io.py` — Pydantic-схемы HTTP-контрактов.

## Логическая схема выполнения

1. Клиент отправляет запрос на `/generate`, `/refine` или `/debug`.
2. API строит prompt/messages в зависимости от endpoint и истории.
3. `ollama_client` делает запрос к локальному Ollama.
4. Pipeline парсит ответ и запускает проверки Lua.
5. При ошибках для `/generate` и `/refine` включается repair loop.
6. Клиент получает финальный JSON со статусом, кодом и деталями проверок.

## Stateless-подход

- Сервер не хранит пользовательские сессии.
- История шагов передаётся клиентом каждый раз:
  - `clarification_history`
  - `refinement_history`
  - `debug_history`
- Такой подход упрощает горизонтальное масштабирование API и воспроизводимость запросов.

## Runtime и зависимости

- Системный минимум: Docker + Compose; для GPU — NVIDIA stack.
- В контейнере приложения ставятся Python-зависимости из `requirements.txt` и Lua (`lua`, `luac`).
- В conda-режиме зависимости задаются `environment.yml`.

## Связанные документы

- [API-контракты и логика](API_CONTRACTS.md)
- [Полная установка на Linux](INSTALL_LINUX.md)
- [Полная установка на Windows + WSL](INSTALL_WINDOWS.md)
- [Linux install guide](INSTALL_LINUX.md)
- [Windows + WSL install guide](INSTALL_WINDOWS.md)
- [C4 материалы](c4/C4_OVERVIEW.md)
- [Архитектура подпроекта](../localscript-agent/docs/architecture.md)
