# Архитектура LocalScript

Сервис **stateless**: клиент (в т.ч. [Streamlit GUI](../scripts/demo_streamlit.py) или `curl`) передаёт историю в теле каждого запроса. Backend — **FastAPI**; инференс только у локального **Ollama**; в runtime **нет** внешних LLM API.

## C4 (визуализация для сдачи)

1. **Текст для платформы + места под рисунки:** [`../../docs/c4/C4_SUBMISSION.md`](../../docs/c4/C4_SUBMISSION.md)  
2. Техническое описание и таблицы: [`../../docs/c4/C4_OVERVIEW.md`](../../docs/c4/C4_OVERVIEW.md)  
3. Исходники PlantUML и рендер: [`../../docs/c4/README.md`](../../docs/c4/README.md), скрипт [`../../scripts/render_c4.sh`](../../scripts/render_c4.sh) из корня репозитория `mts`

## Компоненты кода (сводка)

| Область | Модули |
|---------|--------|
| HTTP | `app/main.py` |
| Пайплайн | `app/pipeline.py` |
| Ollama | `app/ollama_client.py` |
| Промпты / разбор | `app/prompts.py`, `app/generate_parse.py`, `app/extract.py` |
| Проверки | `app/validate.py`, `app/code_checks.py`, `app/semantic.py`, при необходимости `app/sandbox.py` |
| GUI (клиент API) | `scripts/demo_streamlit.py` |
| CLI (клиент API) | `scripts/demo_cli.py` |

Развёртывание по умолчанию: **`docker-compose.yml`** в этом каталоге (`app` + `ollama`). Streamlit обычно запускается **на хосте** отдельной командой (см. README подпроекта).
