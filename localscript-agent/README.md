# LocalScript Agent (merge)

Локальный агент для генерации и доработки Lua-кода под LowCode-сценарии.  
Стек: `FastAPI` + `Ollama` + внутренний `repair loop` + статические проверки + sandbox.

Cервер не хранит сессию, историю диалога
клиент передает в теле запроса (`clarification_history`, `refinement_history`, `debug_history`).

Полный API-контракт: [`../localscript-openapi.yaml`](../localscript-openapi.yaml)

## Что есть в текущей версии

- эндпоинты: `POST /generate`, `POST /refine`, `POST /debug`, `GET /health`
- расширенный `health` (готовность Ollama + модель + инференс-параметры)
- repair loop с отчетом по попыткам (`attempts`, `checks`, `degraded`, `stop_reason`)
- семантическая валидация (опционально, через `Context` в prompt)
- demo CLI для полного сценария работы с API
- Streamlit GUI с chat history (save/load/clear + загрузка выбранного шага)
- скрипты оценки на публичной выборке и синтетические утилиты

## Архитектура (кратко)

- `app/main.py` - FastAPI-приложение и HTTP-эндпоинты
- `app/pipeline.py` - orchestration generate/refine/debug, repair loop
- `app/prompts.py` - system/user prompts и сборка сообщений для LLM
- `app/code_checks.py` - run_all_checks (syntax/static/sandbox/semantic)
- `app/semantic.py` - правила семантической валидации
- `app/sandbox.py` - безопасный запуск Lua в sandbox
- `app/ollama_client.py` - вызовы Ollama, warmup, health-ready проверки
- `scripts/demo_cli.py` - интерактивный CLI-клиент к API
- `scripts/demo_streamlit.py` - GUI-клиент к API


Инструкции по установке и запуске ищите в `docs/` в корне репозитория