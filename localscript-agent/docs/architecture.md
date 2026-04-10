# Архитектура (черновик для C4)

## Контекст (C4 Level 1)

Пользователь или интеграционный контур обращается к HTTP API **LocalScript** в закрытой сети. Сервис вызывает локальный **Ollama** на GPU; внешние LLM API не используются.

## Контейнеры (C4 Level 2)

- **App** (Python, FastAPI): приём `POST /generate`, сборка промпта, вызов Ollama, извлечение Lua, валидация (`luac`, статические правила), цикл repair.
- **Ollama**: инференс GGUF-модели на GPU, параметры `num_ctx=4096`, `num_predict=256`.

## Компоненты App

- `pipeline.generate_lua` — оркестрация.
- `ollama_client` — HTTP `/api/chat`.
- `validate` — `luac -p` + запрет `require`/`io`/`os`.
- `sandbox` — опциональный прогон с mock `wf` (eval).

Перенесите блоки в официальный C4-шаблон организаторов (диаграмма + краткие подписи).
