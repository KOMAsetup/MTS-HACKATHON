# API-контракты и логика эндпоинтов

Источник контракта: [`../localscript-openapi.yaml`](../localscript-openapi.yaml).

## Общие принципы API

- API stateless: состояние диалога хранит клиент, а не сервер.
- Формат обмена: JSON поверх HTTP.
- Базовый URL при локальном запуске: `http://127.0.0.1:8080`.
- Основные коды ошибок:
  - `422` — некорректное тело запроса.
  - `502` — сбой upstream/parsing/pipeline.

## `GET /health`

Назначение: быстрый health-check приложения и доступности Ollama.

Что возвращает:

- `status` (`ok` / `degraded`)
- `ollama_reachable`
- `model_ready`
- активную модель и параметры инференса (`num_ctx`, `num_predict`, `batch`, `parallel`, `gpu_only`)

Логика:

1. API ходит в Ollama `/api/tags`.
2. Проверяет, отвечает ли HTTP.
3. Проверяет наличие нужной модели в списке tags.
4. Формирует итоговый status.

## `POST /generate`

Назначение: первичная генерация Lua-кода по задаче.

Вход (ключевые поля):

- `prompt: string` (обязательно)
- `clarification_history: ClarificationTurn[]` (опционально)
- `max_repair_attempts: int | null` (опционально, с серверным cap)

Выход:

- `response_kind: clarification | code`
- если `clarification` -> `clarification_question`
- если `code` -> `code`, `attempts`, `all_checks_passed`, `degraded`, `stop_reason`, `llm_rounds`, `repair_rounds_used`, `parse_warning`

Логика:

1. Собирается prompt для режима generate (включая `clarification_history`).
2. Делается один вызов LLM.
3. Ответ парсится как JSON (`clarification` либо `code`).
4. Для ветки `code` запускаются проверки и repair loop.
5. Клиент получает финальный код и журнал попыток.

## `POST /refine`

Назначение: доработка уже сгенерированного кода.

Вход:

- `prompt: string` (исходная задача)
- `refinement_history: RefinementStep[]` (обязательно и не пусто)
- `max_repair_attempts` (опционально)

Выход: та же структура, что у ветки `code` в `/generate`.

Логика:

1. История refinement сворачивается в единый user-message.
2. LLM генерирует обновлённый Lua.
3. Запускаются проверки + repair loop.
4. Возвращается финальный вариант и все check-артефакты.

## `POST /debug`

Назначение: ревью пользовательского Lua-кода (проверки + анализ + предложенный фикс).

Вход:

- `code: string` (обязательно)
- `prompt: string | null` (опциональный вопрос пользователя)
- `debug_history: DebugHistoryTurn[]` (опционально, для многошагового debug-диалога)

Выход:

- `checks: CheckItem[]`
- `all_checks_passed: bool`
- `problem_description: string`
- `suggested_code: string`

Логика:

1. На переданный `code` запускается `run_all_checks`.
2. Для LLM строится компактное описание failed-checks и history.
3. Выполняется один debug-вызов модели.
4. Ответ парсится в `problem_description` и `suggested_code`.
5. Клиент сам решает, использовать ли `suggested_code` в следующем шаге.

## Проверки и repair loop

Проверки в pipeline:

- static guard (запрещённые паттерны Lua)
- syntax check через `luac -p`
- optional linter (`selene`, если включён)
- optional semantic validation (если включена настройкой или есть спец-контекст)

Repair loop:

1. Начальный код валидируется.
2. Если fail — строится compact repair prompt с ошибками.
3. Модель предлагает исправление.
4. Код снова валидируется.
5. Цикл идёт до `max_repair_attempts` или `validation_ok`.

## Основные модели данных

- `GenerateRequest`, `GenerateResponse`
- `RefineRequest`, `RefinementStep`
- `DebugRequest`, `DebugResponse`, `DebugHistoryTurn`
- `AttemptRecord`, `CheckItem`

Полный machine-readable контракт — в `localscript-openapi.yaml`.
