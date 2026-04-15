# LocalScript Agent (merge)

Локальный агент для генерации и доработки Lua-кода под LowCode-сценарии.  
Стек: `FastAPI` + `Ollama` + внутренний `repair loop` + статические проверки + sandbox.

Проект работает в **tim-style API** (stateless): сервер не хранит сессию, историю диалога
клиент передает в теле запроса (`clarification_history`, `refinement_history`, `debug_history`).

Полный API-контракт: [`../localscript-openapi.yaml`](../localscript-openapi.yaml)

## Что есть в текущей версии

- tim-style эндпоинты: `POST /generate`, `POST /refine`, `POST /debug`, `GET /health`
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

## Установка и запуск

### Вариант 1 (рекомендуется): Docker + GPU

Из директории `localscript-agent`:

```bash
sudo docker compose up --build
```

После старта:

- API: `http://127.0.0.1:8080`
- Ollama: `http://127.0.0.1:11434`
- модель по умолчанию: `qwen2.5-coder:7b`

Основные переменные окружения:

- `OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_NUM_GPU`
- `NUM_CTX`, `NUM_PREDICT`, `NUM_BATCH`, `NUM_PARALLEL`
- `OLLAMA_WARMUP_ENABLED`, `OLLAMA_WARMUP_TIMEOUT_SECONDS`
- `OLLAMA_HEALTH_TIMEOUT_SECONDS`

### Вариант 2: локальная разработка (conda + uvicorn)

```bash
./scripts/bootstrap_dev.sh
conda activate localscript-agent
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

Требуется `lua` и `luac` в `PATH`.

### Подробные инструкции по установке

- [`../docs/INSTALL_WINDOWS.md`](../docs/INSTALL_WINDOWS.md)
- [`../docs/INSTALL_LINUX.md`](../docs/INSTALL_LINUX.md)
- [`docs/SETUP_GUIDE.md`](docs/SETUP_GUIDE.md)

## Эксплуатация API

Сервис stateless: для многошаговой логики клиент сам передает историю в каждом запросе.

### Эндпоинты

- `GET /health` - проверка статуса приложения, доступности Ollama и готовности модели
- `POST /generate` - старт новой задачи (может вернуть `clarification` до кода)
- `POST /refine` - доработка кода по `refinement_history` (обязательное непустое поле)
- `POST /debug` - анализ переданного Lua-кода + 1 раунд LLM-ревью

### Пример `GET /health`

```bash
curl -s http://127.0.0.1:8080/health
```

### Пример `POST /generate`

```bash
curl -s http://127.0.0.1:8080/generate \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "Напиши Lua, который возвращает последний email из wf.vars.emails",
    "clarification_history": [],
    "max_repair_attempts": 2
  }'
```

### Пример `POST /refine`

```bash
curl -s http://127.0.0.1:8080/refine \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "То же задание",
    "refinement_history": [
      {
        "assistant_code": "return wf.vars.emails[#wf.vars.emails]",
        "user_feedback": "Добавь проверку на пустой массив",
        "checks": []
      }
    ],
    "max_repair_attempts": 2
  }'
```

### Пример `POST /debug`

```bash
curl -s http://127.0.0.1:8080/debug \
  -H 'Content-Type: application/json' \
  -d '{
    "code": "return wf.initVariables(\"x\")",
    "prompt": "Почему этот код падает в sandbox?",
    "debug_history": []
  }'
```

### Коды ответов

- `200` - успешный ответ
- `422` - ошибка валидации входного тела
- `502` - ошибка upstream/parsing/runtime в пайплайне

## Эксплуатация CLI

CLI-файл: `scripts/demo_cli.py`  
Назначение: интерактивная работа с `generate/refine/debug`, контекстом и логом ответов.

Запуск:

```bash
python scripts/demo_cli.py
```

Полезные флаги:

- `--base-url` - адрес API
- `--timeout` - таймаут HTTP в секундах
- `--context-file` - JSON-контекст, который будет встроен в prompt
- `--verbose` - печать полного JSON-ответа

Базовые команды внутри CLI:

- `/help`, `/quit`
- `/health`, `/settings`, `/url <url>`
- `/ctx <file.json>`, `/ctx show`, `/ctx clear`
- `/log`, `/log N`, `/log all`, `/log clear`
- `/refine`
- `/debug`, `/debug <text>`, `/debug new`

Важно: удобная подстановка кода в `/debug` (из предыдущих шагов) реализована на стороне
CLI и не является частью HTTP-контракта.

## Эксплуатация GUI

GUI-файл: `scripts/demo_streamlit.py`  
Назначение: визуальная работа с `health/generate/refine/debug`, историями и семантикой.

Запуск:

```bash
python -m streamlit run scripts/demo_streamlit.py
```

Ключевые возможности GUI:

- поля для `prompt`, `clarification_history`, `refinement_history`, `debug_history`
- настройка `max_repair_attempts`
- переключатель `Enable semantic validation for this request`
- поле `Semantic rules JSON`
- блок `Action readiness` перед отправкой запроса
- chat history:
  - `Save chat history`
  - `Load chat history`
  - `Clear chat history`
  - `Load selected turn into response panel`

Файл истории GUI: `artifacts/gui_chat_history.jsonl`

## Проверка качества и метрик

### Тесты

```bash
pytest -q
```

### Линтер

```bash
ruff check .
```

### Публичная выборка

HTTP-режим:

```bash
python scripts/eval_public.py --http --base-url http://127.0.0.1:8080
```

Direct/in-process режим:

```bash
python scripts/eval_public.py
```

## Дополнительная документация

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/AGENT_WORKFLOW.md`](docs/AGENT_WORKFLOW.md)
- [`docs/CLI_CURRENT_BEHAVIOR.md`](docs/CLI_CURRENT_BEHAVIOR.md)
- [`docs/hardware.md`](docs/hardware.md)
- [`docs/vram_smoke.md`](docs/vram_smoke.md)
- [`docs/experiments/BEST_CONFIG.md`](docs/experiments/BEST_CONFIG.md)
- [`docs/SUBMISSION.md`](docs/SUBMISSION.md)
- [`models/Modelfile.example`](models/Modelfile.example)
