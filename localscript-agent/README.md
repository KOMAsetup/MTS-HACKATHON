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

- `POST /generate` — тело: `{"prompt": "..."}`. Опционально: `context` (JSON), **`previous_code`** (последний Lua для правки в том же запросе), `feedback`, **`debug`** (`bool`, по умолчанию `false`).
- `POST /refine` — явная вторая итерация: `prompt`, `previous_code`, `feedback`, опционально `context`, **`debug`**.
- `GET /health` — готовность приложения и доступность Ollama.

### Флаг `debug` в ответе

Если в запросе передать `"debug": true`, в JSON ответа появится поле **`debug`** (иначе поля нет). Там диагностика пайплайна валидации и repair:

| Поле | Смысл |
|------|--------|
| `first_validation_ok` | Прошла ли проверка сразу после первого ответа модели |
| `final_validation_ok` | Прошла ли проверка у кода, который возвращается клиенту |
| `llm_rounds` | Сколько раз вызывался Ollama (1 + число repair-вызовов) |
| `repair_rounds_used` | Сколько раз зашли в цикл repair (0, если с первого раза ок) |
| `max_repair_attempts` | Лимит repair из настроек сервера |
| `degraded` | `true`, если финальный код **всё ещё** не проходит статические проверки после всех попыток |
| `log` | Строки внутреннего лога (`validate: …`) |

Пример:

```bash
curl -s http://localhost:8080/generate \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"return 1+1","debug":true}'
```

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

## Демо CLI (`scripts/demo_cli.py`)

**Текущая логика (attach, /refine all, буфер debug, сброс истории)** — в [`docs/CLI_CURRENT_BEHAVIOR.md`](docs/CLI_CURRENT_BEHAVIOR.md); документ будем уточнять по мере доработок.

Интерактивная сессия в терминале к поднятому API (удобно вместе с Docker на `http://127.0.0.1:8080`):

```bash
cd localscript-agent
python3 scripts/demo_cli.py
```

Опции: `--base-url`, `--timeout`, `--context-file`, **`--no-server-debug`**, **`--attach-previous-code`**.

**Настройки по умолчанию** — модуль [`app/cli_settings.py`](app/cli_settings.py): префикс переменных окружения `LOCALSCRIPT_CLI_` (например `LOCALSCRIPT_CLI_BASE_URL`), опциональный файл **`.env.cli`** в текущем каталоге. Поля **`request_server_debug`** (по умолчанию `true`) и **`attach_previous_code`** (по умолчанию `false`) — см. ниже.

### Режим «дописать / починить» (`previous_code`)

В `POST /generate` уже есть поле **`previous_code`**: сервер подмешивает его в промпт как блок *«Previous Lua (fix or improve)»* (см. [`app/prompts.py`](app/prompts.py)). В CLI новая строка — это **`prompt`**; при **`/attach on`** к запросу добавляется **`previous_code`** = последний напечатанный `code`. В stderr кратко видно, ушёл ли `previous_code`. Для сценария с отдельным полем **`feedback`** используй **`/refine`** или сырой JSON к API.

Команды внутри REPL (строка с `>`):

| Команда | Действие |
|---------|----------|
| `/help` | Справка |
| `/health` | `GET /health` |
| `/settings` | Текущие настройки CLI и размер буфера |
| `/url <url>` | Сменить базовый URL сессии |
| `/ctx …` | Загрузить / показать / очистить JSON-контекст |
| `/refine` | Уточнение последнего кода (многострочный feedback) |
| **`/refine all`** | Одноразово для **следующего** `/refine`: в `context` добавить `refine_all_history` (см. док выше). Без предшествующего успешного `/refine` — ошибка в stderr. |
| **`/debug`** | Последняя запись из буфера диагностики |
| **`/debug N`** | Последние **N** записей буфера (новые в конце списка) |
| **`/debug all`** | Весь буфер |
| **`/debug clear`** | Очистить буфер |
| **`/debug on` / `/debug off`** | Запрашивать ли у API поле `debug` (без `/debug off` буфер не пополняется новыми метаданными) |
| **`/debug status`** | Вкл/выкл запрос debug и число записей в буфере |
| **`/attach on` / `/attach off`** | Автоматически приклеивать последний код к следующим `generate` |
| **`/attach status`** | Состояние attach и наличие `last_code` |

Буфер ограничен (последние 32 ответа с метаданными). Так можно **не засорять вывод** при обычной генерации, а по команде **`/debug`** или **`/debug 5`** посмотреть, прошла ли валидация с первого раза или исчерпались repair.

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
- [`docs/CLI_CURRENT_BEHAVIOR.md`](docs/CLI_CURRENT_BEHAVIOR.md) — **текущее** поведение демо CLI и связанных флагов API (черновик, под доработку).
- [`docs/hardware.md`](docs/hardware.md) — железо.
- [`docs/vram_smoke.md`](docs/vram_smoke.md) — проверка пиковой VRAM.
- [`docs/experiments/BEST_CONFIG.md`](docs/experiments/BEST_CONFIG.md) — эталон конфигурации для сдачи.
- [`docs/SUBMISSION.md`](docs/SUBMISSION.md) — чеклист артефактов хакатона.
- [`models/Modelfile.example`](models/Modelfile.example) — пример кастомной модели Ollama.

## Структура

- `app/` — сервис, Ollama-клиент, промпты, валидация (`luac` + статические запреты), `code_checks`, опциональный линтер, sandbox; **`cli_settings.py`** — дефолты для демо CLI.
- `scripts/demo_cli.py` — REPL к API с буфером `/debug`.
- `benchmarks/public_tasks.json` — публичные задачи из PDF.
- `data/synthetic/` — эталоны для обучения (агент + шаблоны).
