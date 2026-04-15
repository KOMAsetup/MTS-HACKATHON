# LocalScript — локальный AI-агент для Lua

Репозиторий содержит решение для трека **LocalScript**: локальный API-сервис на Python, который генерирует и дорабатывает Lua-код через локальный **Ollama** без внешних LLM API в runtime.

- Условие хакатона: [`instruction.txt`](instruction.txt)
- Контракт API: [`localscript-openapi.yaml`](localscript-openapi.yaml)
- Публичная выборка: [`Публичная выборка LocalScript.pdf`](Публичная%20выборка%20LocalScript.pdf)

## Быстрый старт после клонирования

```bash
cd localscript-agent
docker compose up --build
```

- API: `http://127.0.0.1:8080`
- Ollama: `http://127.0.0.1:11434`

Подробный запуск с нуля и полный список зависимостей:

- [Полная установка на Linux](docs/INSTALL_LINUX.md)
- [Полная установка на Windows + WSL](docs/INSTALL_WINDOWS.md)

## Что внутри репозитория

| Путь | Назначение |
|------|------------|
| [`localscript-agent/`](localscript-agent/) | FastAPI-приложение, pipeline, проверки, CLI и Streamlit GUI |
| [`localscript-openapi.yaml`](localscript-openapi.yaml) | OpenAPI-контракт эндпоинтов |
| [`docs/`](docs/) | Гайды установки, API-логика, архитектура, C4 |
| [`docs/c4/`](docs/c4/) | C4-диаграммы и материалы для сдачи |

## API: контракты и логика работы

Сервис **stateless**: сервер не хранит сессию, клиент передаёт историю шагов в теле запроса.

- `GET /health` — состояние API, доступность Ollama и готовность модели.
- `POST /generate` — старт новой задачи; может вернуть либо `clarification`, либо `code`.
- `POST /refine` — доработка кода по обязательному `refinement_history`.
- `POST /debug` — статические проверки текущего кода + один раунд review от LLM.

Ключевая логика:

1. Модель генерирует начальный Lua.
2. Код валидируется (`static guard` + `luac` + optional linter + optional semantic).
3. Если есть ошибки, запускается repair loop до лимита попыток.
4. Клиент получает список попыток, признаки деградации и причину остановки.

Подробные описания контрактов запросов/ответов и поведения каждого эндпоинта:

- [API-контракты и логика эндпоинтов](docs/API_CONTRACTS.md)
- [README подпроекта с примерами `curl`](localscript-agent/README.md)

## Стек и архитектура проекта

Технологический стек:

- **Backend:** Python 3.11, FastAPI, Pydantic, httpx, Uvicorn
- **LLM runtime:** Ollama (`qwen2.5-coder:7b`)
- **Валидация Lua:** `luac`, статические правила, optional semantic/sandbox
- **Интерфейсы:** CLI и Streamlit GUI (оба как клиенты HTTP API)
- **Развёртывание:** Docker Compose (`app` + `ollama`)

Архитектурный поток:

`Client (CLI/GUI/curl)` -> `FastAPI endpoints` -> `Pipeline` -> `Ollama + checks` -> `response with attempts/checks`.

Документы по архитектуре:

- [Архитектура и стек (детально)](docs/PROJECT_ARCHITECTURE.md)
- [Архитектура подпроекта](localscript-agent/docs/architecture.md)
- [C4 для сдачи](docs/c4/C4_SUBMISSION.md)

## Дополнительно

- [Инструкция по развёртыванию и режимам запуска](localscript-agent/docs/SETUP_GUIDE.md)
- [Эксперименты и лучшая конфигурация](localscript-agent/docs/experiments/BEST_CONFIG.md)
- [Критерии и артефакты сдачи](localscript-agent/docs/SUBMISSION.md)
