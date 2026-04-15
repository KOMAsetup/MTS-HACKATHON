# Архитектура LocalScript

Кратко: пользователь или интеграция обращается к **HTTP API** (FastAPI); сервис собирает промпт, вызывает локальный **Ollama**, извлекает Lua, прогоняет **статические проверки** и **`luac`**, при необходимости выполняет **цикл repair**. Внешние LLM API в runtime не используются.

## C4 (полная модель и рендер)

- **Текст, таблицы, соответствие модулям:** [`../../docs/c4/C4_OVERVIEW.md`](../../docs/c4/C4_OVERVIEW.md)
- **Диаграммы PlantUML:** [`../../docs/c4/diagrams/`](../../docs/c4/diagrams/)
- **Как собрать PNG/SVG/PDF:** [`../../docs/c4/README.md`](../../docs/c4/README.md) или `./scripts/render_c4.sh` из корня репозитория `mts`

## Компоненты (сводка, без дублирования C4)

| Область | Модули |
|---------|--------|
| HTTP | `app/main.py` |
| Пайплайн | `app/pipeline.py` |
| Ollama | `app/ollama_client.py` |
| Промпты / разбор | `app/prompts.py`, `app/generate_parse.py`, `app/extract.py` |
| Проверки | `app/validate.py`, `app/code_checks.py` |
| Песочница (eval, не hot path API) | `app/sandbox.py`, `scripts/eval_public.py` |

Развёртывание по умолчанию: **`docker-compose.yml`** в каталоге `localscript-agent/` (сервисы `app` и `ollama`).
