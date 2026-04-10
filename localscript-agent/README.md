# LocalScript agent

Локальный сервис генерации Lua для LowCode: **FastAPI** + **Ollama** (без внешних LLM API). Соответствует контракту [`../localscript-openapi.yaml`](../localscript-openapi.yaml).

## Однострочный запуск (Docker + GPU)

```bash
cd localscript-agent && docker compose up --build
```

(команда из **корня** клона репозитория; если вы уже внутри `localscript-agent/`, достаточно `docker compose up --build`.)

- API: `http://localhost:8080`
- Ollama: `http://localhost:11434`
- Модель по умолчанию: `qwen2.5-coder:7b` (переопределение: `OLLAMA_MODEL=... docker compose up --build`)

### Параметры инференса (как в условии хакатона)

| Параметр      | Значение |
|---------------|----------|
| `num_ctx`     | 4096     |
| `num_predict` | 256      |
| batch         | 1 (см. README Ollama; при необходимости фиксируйте версией образа) |
| parallel      | 1        |

В README зафиксировано:

```bash
ollama pull qwen2.5-coder:7b
```

Переменные приложения: `NUM_CTX`, `NUM_PREDICT`, `OLLAMA_HOST`, `OLLAMA_MODEL`, `OLLAMA_NUM_GPU` (999 = все слои на GPU, без CPU offload весов на стороне llama.cpp/Ollama).

## Conda (разработка)

```bash
./scripts/bootstrap_dev.sh
conda activate localscript-agent
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

Нужны `lua` и `luac` на PATH (conda-forge ставит их вместе с пакетом `lua`).

## API

- `POST /generate` — тело: `{"prompt": "..."}`. Опционально: `context` (JSON), `previous_code`, `feedback` (итерация / уточнение).
- `POST /refine` — явная вторая итерация: `prompt`, `previous_code`, `feedback`, опционально `context`.
- `GET /health` — готовность приложения и доступность Ollama.

Пример:

```bash
curl -s http://localhost:8080/generate \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Функция factorial(n) для n >= 0"}'
```

Итерация с обратной связью (агентность):

```bash
curl -s http://localhost:8080/refine \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"То же задание","previous_code":"return n","feedback":"Исправь: учти n=0 и используй локальные переменные"}'
```

Либо один вызов `POST /generate` с полями `previous_code` и `feedback`.

## Оценка на публичной выборке

С поднятым Ollama:

```bash
python3 scripts/eval_public.py --http --base-url http://127.0.0.1:8080
```

Без HTTP (in-process, нужен отвечающий Ollama по `OLLAMA_HOST`):

```bash
python3 scripts/eval_public.py
```

## Синтетический датасет (детерминированный)

```bash
python3 scripts/generate_synthetic_dataset.py --out data/synthetic/generated.jsonl
```

## Качество кода

```bash
./scripts/quality.sh
```

## Документы

- [`../docs/INSTALL_LINUX.md`](../docs/INSTALL_LINUX.md), [`../docs/INSTALL_WINDOWS.md`](../docs/INSTALL_WINDOWS.md) — установка Docker / GPU с нуля с корня репозитория.
- [`docs/SETUP_GUIDE.md`](docs/SETUP_GUIDE.md) — что качалось (Ollama vs веса модели), Docker или нативный Ollama, conda, проверки после установки.
- [`docs/AGENT_WORKFLOW.md`](docs/AGENT_WORKFLOW.md) — как держать стек для итераций с ассистентом (eval, метрики, что писать в чат).
- [`docs/hardware.md`](docs/hardware.md) — железо.
- [`docs/vram_smoke.md`](docs/vram_smoke.md) — проверка пиковой VRAM.
- [`docs/experiments/BEST_CONFIG.md`](docs/experiments/BEST_CONFIG.md) — эталон конфигурации для сдачи.
- [`docs/SUBMISSION.md`](docs/SUBMISSION.md) — чеклист артефактов хакатона.
- [`models/Modelfile.example`](models/Modelfile.example) — пример кастомной модели Ollama.

## Структура

- `app/` — сервис, Ollama-клиент, промпты, валидация (`luac` + статические запреты), sandbox.
- `benchmarks/public_tasks.json` — публичные задачи из PDF.
- `data/synthetic/` — эталоны для обучения (агент + шаблоны).
