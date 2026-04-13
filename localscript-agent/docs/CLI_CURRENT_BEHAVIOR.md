# Текущее поведение демо CLI и связанного API

Документ фиксирует **фактическую** логику на момент написания. Поведение **планируется уточнять** (история, лимиты, тексты ошибок, ключи в `context`).

Источник правды в коде: [`scripts/demo_cli.py`](../scripts/demo_cli.py), настройки: [`app/cli_settings.py`](../app/cli_settings.py), API: [`app/main.py`](../app/main.py), [`app/models_io.py`](../app/models_io.py), пайплайн: [`app/pipeline.py`](../app/pipeline.py).

---

## Сессия без серверной памяти

- Сервер **не хранит** историю чата между запросами.
- CLI держит **локальное** состояние: `last_code`, `last_prompt`, опционально загруженный `context`, буфер debug, флаги attach / refine-all, список `session_history`.

---

## Обычный ввод (не команда)

Строка без ведущего `/` → **`POST /generate`** с телом:

- `prompt` — эта строка;
- `context` — если задан через `/ctx` или `LOCALSCRIPT_CLI_DEFAULT_CONTEXT_FILE`;
- `previous_code` — **только если** включён режим **`/attach on`** и уже есть `last_code` (подставляется **только последний** напечатанный код, без склейки всех прошлых версий);
- `debug: true` — если не выключено через `/debug off` или `--no-server-debug` / настройку `request_server_debug`.

После **успешного** ответа: `last_code` и `last_prompt` обновляются; в **`session_history`** записывается **ровно один** шаг `type: generate` (предыдущая цепочка **сбрасывается**); флаг **`pending_refine_all_chain`** сбрасывается в `false`.

---

## `/refine`

- Требуются `last_code` и `last_prompt` (после хотя бы одного успешного generate).
- Запрашивается многострочный **feedback** (пустая первая строка — отмена).
- **`POST /refine`**: `prompt=last_prompt`, `previous_code=last_code`, `feedback`, `context` (см. ниже про `/refine all`).

После **успешного** ответа: `last_code` обновляется; **`last_prompt` не меняется**; в `session_history` добавляется шаг `type: refine` с тем же `prompt`, введённым `feedback` и новым `code`.

---

## `/refine all`

1. Если в `session_history` **нет ни одного** шага `type: refine` → в **stderr** сообщение об ошибке, команда **не** активирует режим.
2. Иначе выставляется **`pending_refine_all_chain = true`** (одноразовое ожидание следующего успешного `/refine`).

При **следующем** успешно отправленном `/refine`:

- В **`context`** мержится текущий пользовательский `context` (если был) и добавляется ключ **`refine_all_history`**: копия **`session_history` на момент отправки** (все шаги до этого refine, без нового ответа).
- В списке не более **40** последних шагов (`REFINE_ALL_HISTORY_MAX_STEPS` в коде).
- После **успешного** HTTP-ответа флаг `pending_refine_all_chain` сбрасывается. При **ошибке** запроса флаг **остаётся** — можно повторить `/refine`.

Если после `/refine all` пользователь **отменяет** ввод feedback (пустая первая строка), флаг **не** сбрасывается.

---

## `/attach on` / `off`

- При **`on`**: каждый последующий **generate** добавляет `previous_code=last_code`, пока код есть.
- **`last_code`** всегда один — последний ответ (generate или refine).

---

## Буфер `/debug`

- Пока **`request_server_debug`** истинно, после каждого успешного generate/refine в кольцевой буфер (до **32** записей) кладётся срез ответа API с полем `debug`.
- **`/debug`**, **`/debug N`**, **`/debug all`**, **`/debug clear`**, **`/debug on|off|status`** — только клиент, без запросов к API.

Поле **`debug`** в ответе API описано в [`README.md`](../README.md) (раздел про флаг `debug`): `first_validation_ok`, `final_validation_ok`, `llm_rounds`, `repair_rounds_used`, `max_repair_attempts`, `degraded`, `log`.

---

## Настройки CLI (`app/cli_settings.py`)

Префикс окружения: **`LOCALSCRIPT_CLI_`**, опциональный файл **`.env.cli`**.

| Поле (в коде) | Смысл |
|---------------|--------|
| `base_url` | Базовый URL API |
| `http_timeout_s` | Таймаут HTTP |
| `default_context_file` | JSON для стартового `context` |
| `request_server_debug` | Слать ли `debug: true` (по умолчанию `true`) |
| `attach_previous_code` | Стартовый режим attach (по умолчанию `false`) |

Флаги запуска: `--no-server-debug`, `--attach-previous-code`.

---

## Что сознательно не сделано / ограничения

- Нет полной «ленты чата» в API; цепочка **`refine_all_history`** — только клиентский срез в `context`.
- Системный промпт сервера **не** описывает ключ `refine_all_history`; модель должна понимать его из текста Context (при необходимости позже добавят явные инструкции).
- Лимиты 32 / 40 и тексты ошибок — **временные**, под настройку.
