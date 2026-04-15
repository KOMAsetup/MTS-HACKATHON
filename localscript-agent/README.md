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

## API (stateless)

Сервер **не хранит** сессии. Клиент передаёт полную цепочку там, где она нужна (`clarification_history`, `refinement_history`, `debug_history`). Полный контракт: [`../localscript-openapi.yaml`](../localscript-openapi.yaml).

| Метод | Назначение |
|-------|------------|
| `POST /generate` | Новая задача. Опционально `clarification_history` для раундов «вопрос → ответ» до первого кода. Ответ: `response_kind`: `clarification` или `code`. |
| `POST /refine` | Продолжение одной ветки правок: обязательны `prompt` (исходная задача) и **непустой** `refinement_history` (минимум один шаг). Отдельного поля `context` в HTTP-теле нет. |
| `POST /debug` | Обзор Lua: проверки + один раунд LLM — подробно в § **POST /debug (HTTP)** ниже. Не смешивать с `/refine`. |
| `GET /health` | Готовность приложения и доступность Ollama. |

**Уточнения до кода (`/generate` только):** модель может вернуть `response_kind: clarification` и `clarification_question`; тогда `code` пустой, `attempts: []`. Следующий запрос — снова `POST /generate` с тем же `prompt` и дополненным `clarification_history`.

**Ветка `code`:** поле `code` — итог после внутреннего repair; всегда есть **`attempts`** (шаги `initial` / `repair` с полем **`checks`** на каждом шаге), плюс сводка `all_checks_passed`, `degraded`, `stop_reason`, `llm_rounds`, `repair_rounds_used`. Флага `debug` в запросе **нет** — диагностика всегда в теле ответа для ветки кода.

**Важно про checks в LLM-контексте (все эндпоинты):** в текст, который отправляется модели, не прокидывается «полный список checks с passed=true/false». В контекст попадает только компактный вид: `all_checks_passed: true` либо `all_checks_passed: false` + список только проваленных проверок с описаниями.

**Ошибки:** неверное тело (например пустой `refinement_history`) → **422** от FastAPI; сбой парсинга/OLLama при обработке → **502** с `detail`.

### `POST /debug` (HTTP)

- **Запрос:** обязательный **`code`** (строка Lua — клиент **всегда** передаёт её явно в JSON; «подстановка без кода» возможна только в **демо CLI**, см. ниже). Опционально **`prompt`** (вопрос/контекст), **`debug_history`** — полная цепочка прошлых раундов (см. схему `DebugHistoryTurn` в OpenAPI).
- **Сервер:** один раз **`run_all_checks`** по переданному **`code`** → в ответе **`checks`**, **`all_checks_passed`**; затем один вызов LLM (отдельный system prompt, не как у `/generate`). В ответе **`problem_description`**, **`suggested_code`** (черновик от модели; может не проходить проверки). Цель `/debug` для модели двойная: **ответить на вопрос пользователя** и **дать корректный Lua**.
- **Длинный диалог:** сервер stateless; клиент на каждом шаге присылает новый **`code`** (и при необходимости **`prompt`**) и накопленный **`debug_history`**, чтобы модель видела предыдущие раунды.

#### Что из `debug_history` попадает в контекст LLM

Сборка в `app/prompts.py` → `build_debug_user_message`. В **user**-сообщение блоки идут **в таком порядке** (вопрос в конце — чтобы модель видела его последним перед ответом):

1. **Контекст текущего раунда:** заголовок `=== Context: static checks + user's Lua ===`, затем **компактные** проверки по корневому **`code`** (`all_checks_passed` + только провалы), затем **`User's Lua:`** + тело в markdown-ограждении `lua`.

2. Если **`debug_history`** не пустой — блок **транскрипта** ранних раундов; **для каждого** `DebugHistoryTurn` **по порядку** подставляется полный смысл раунда:
   - **`user_code`** — в markdown-блок кода с тегом `lua` (при сверхбольшой длине — усечение, см. `_DEBUG_HIST_USER_CODE_MAX` в коде);
   - **`checks`** — в промпт идёт только **`all_checks_passed`** (по снимку) и при **`false`** — **только провалы** (`stage` + `message`); успешные проверки не перечисляются;
   - **`user_prompt`** — блок «User question / note then:» + текст или `(none)`;
   - **`problem_description`** — полный текст (усечение только при превышении `_DEBUG_HIST_PROBLEM_MAX`);
   - **`suggested_code`** — в markdown-блок кода с тегом `lua` (лимит `_DEBUG_HIST_SUGGESTED_MAX`).

Так модель видит **цепочку** прошлых раундов, затем (если задан) корневой **`prompt`**: блок **`=== PRIMARY TASK … ===`** в **самом конце** перед финальной строкой про JSON — в нём текущий вопрос/заметка пользователя; system prompt требует отвечать на него **в начале** `problem_description`.

После PRIMARY TASK — напоминание ответить одним JSON с `problem_description` и `suggested_code`.

Пример генерации:

```bash
curl -s http://localhost:8080/generate \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Функция factorial(n) для n >= 0"}'
```

Пример refine (один шаг истории после generate):

```bash
curl -s http://localhost:8080/refine \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"То же задание","refinement_history":[{"assistant_code":"return n","user_feedback":"Учти n=0","checks":[]}]}'
```

**Три разные вещи в CLI:** флаг **`verbose`** (печать полного JSON после вызова), команда **`/log`** (локальный буфер последних **25** полных ответов API), и HTTP-эндпоинт **`POST /debug`** (отдельный сценарий разбора кода).

## Демо CLI (`scripts/demo_cli.py`)

Интерактивная сессия к поднятому API:

```bash
cd localscript-agent
python3 scripts/demo_cli.py
```

Опции: `--base-url`, `--timeout`, `--context-file`, **`--verbose`**.

**Настройки** — [`app/cli_settings.py`](app/cli_settings.py), префикс `LOCALSCRIPT_CLI_`, опционально **`.env.cli`**. Поле **`verbose`** (по умолчанию `false`) задаёт, печатать ли полный JSON ответа после `generate` / `refine` / `debug`.

JSON из бенчмарка с полем `context` в HTTP **не передаётся**: при необходимости CLI вшивает загруженный `/ctx` в текст `prompt` как блок `Context:`.

#### Демо CLI: команда `/debug`

Поведение **не часть HTTP-контракта** — это удобства REPL при сборке тела `POST /debug`.

- **`last_code`** — последний **`code`** из успешного ответа **`/generate`** (ветка `code`) или **`/refine`**. Нужен для **`/refine`** и как запасной источник Lua для `/debug`.
- **`last_debug_suggested_code`** — последний **`suggested_code`** из успешного ответа **`POST /debug`** в этой сессии. Обновляется после каждого успешного `/debug`; сбрасывается при **`/debug new`**, успешном **`/generate`** (новая задача) и успешном **`/refine`**.
- **Интерактивный `/debug`:** после приглашения `Lua >` можно вставить Lua и завершить ввод **пустой строкой**. Если **первая** строка ввода пустая, в API уходит **`code`** = `last_debug_suggested_code`, если он есть, иначе **`last_code`**; если обоих нет — команда отменяется. Затем опционально вводится вопрос (**`prompt`**).
- **`/debug <текст>`:** в **`prompt`** попадает весь хвост команды; **`code`** выбирается с тем же приоритетом: сначала **`last_debug_suggested_code`**, иначе **`last_code`** (если нечего подставить — ошибка в stderr).
- **`/debug new`:** очищает **`debug_history`** и **`last_debug_suggested_code`**.

Команды (строка с `>`):

| Команда | Действие |
|---------|----------|
| `/help` | Справка |
| `/health` | `GET /health` |
| `/settings` | Только настройки CLI (конфиг) |
| `/info` | Состояние текущей сессии (например `active_context`, размер `/log`) |
| `/url <url>` | Сменить базовый URL |
| `/ctx …` | Загрузить / показать / очистить JSON (включается в `prompt`) |
| `/verbose on` / `off` / `status` | Подробный вывод ответов |
| `/log` , `/log N`, `/log all`, `/log clear` | Локальный буфер полных JSON (до 25 записей) |
| `/refine` | Уточнение последнего кода (однострочный feedback, отправка одним Enter; `refinement_history` собирается автоматически) |
| `/debug` | Интерактивный `POST /debug` — правила в подразделе **Демо CLI: команда /debug** |
| `/debug` `<текст>` | Шорткат: **`prompt`** = текст, выбор **`code`** — там же |
| `/debug new` | Сброс **`debug_history`** и **`last_debug_suggested_code`** |
| `/quit` | Выход |

Устаревшие режимы **`attach`**, **`/refine all`**, запрос **`debug: true`** к API удалены.

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
- `scripts/demo_cli.py` — REPL к API с буфером `/log` и опциональным `POST /debug`.
- `benchmarks/public_tasks.json` — публичные задачи из PDF.
- `data/synthetic/` — эталоны для обучения (агент + шаблоны).
