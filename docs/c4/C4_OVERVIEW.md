# LocalScript — модель C4 (текст, таблицы, связь с кодом)

Документ дополняет диаграммы в [`diagrams/`](diagrams/). Исходники для рендера: **PlantUML + C4-PlantUML**; инструкция по сборке PNG/SVG/PDF: [`README.md`](README.md).

Контракт API: [`../../localscript-openapi.yaml`](../../localscript-openapi.yaml). Сборка под жюри: [`../../localscript-agent/docker-compose.yml`](../../localscript-agent/docker-compose.yml).

---

## 1. Соответствие уровней C4 и файлов диаграмм

| Уровень C4 | Файл PlantUML | Кратко |
|------------|---------------|--------|
| Level 1 — System context | [`diagrams/01_L1_context.puml`](diagrams/01_L1_context.puml) | Кто пользуется системой и зачем |
| Level 2 — Containers | [`diagrams/02_L2_containers.puml`](diagrams/02_L2_containers.puml) | App и Ollama как отдельные развёртываемые части |
| Level 3 — Components | [`diagrams/03_L3_components.puml`](diagrams/03_L3_components.puml) | Крупные части **внутри** контейнера App |
| Deployment | [`diagrams/04_L2_deployment.puml`](diagrams/04_L2_deployment.puml) | Docker Compose на хосте |
| Dynamic (сценарий) | [`diagrams/05_dynamic_generate.puml`](diagrams/05_dynamic_generate.puml) | Упрощённый порядок вызовов для `POST /generate` |

---

## 2. Level 1 — контекст системы

**Назначение:** показать LocalScript как **одну** программную систему и внешнего актора (человек или автоматизация), без деталей Docker и модулей Python.

### Элементы диаграммы

| Элемент | Тип C4 | Описание |
|---------|--------|----------|
| Пользователь или интеграция | Person | Вызывает HTTP API: ручные запросы, скрипты, CI. |
| LocalScript | Software system | Локальная генерация и доработка Lua; в runtime **нет** обращений к внешним облачным LLM API — только к развёрнутому рядом Ollama (детализируется на L2). |

### Ключевые свойства (для подписей на слайде)

- Вход: естественный язык и история уточнений / шагов refinement (см. OpenAPI).
- Выход: Lua-код, метаданные проверок, режим уточняющего вопроса (`clarification`).
- Ограничение по условию хакатона: локальная OSS-модель через Ollama.

---

## 3. Level 2 — контейнеры

**Назначение:** разделить ответственность между процессом **приложения** и процессом **инференса**.

### Контейнеры

| Контейнер | Технология | Роль | Порты / связь |
|-----------|------------|------|----------------|
| App | Python 3.11, FastAPI, Uvicorn | HTTP API, промпты, пайплайны, `luac`, статические запреты, опциональный линтер, цикл repair | Публикуется **8080** (см. compose) |
| Ollama | образ `ollama/ollama`, GGUF на GPU | `POST /api/chat`, хранение/подгрузка весов | **11434** в compose; из App — `OLLAMA_HOST` (по умолчанию `http://ollama:11434`) |

### Переменные окружения (сводка, не исчерпывающе)

| Переменная | Где используется | Смысл |
|------------|------------------|--------|
| `OLLAMA_HOST` | App | Базовый URL Ollama для HTTP-клиента |
| `OLLAMA_MODEL` | App, entrypoint Ollama | Имя модели (по умолчанию `qwen2.5-coder:7b`) |
| `NUM_CTX`, `NUM_PREDICT` | App → опции запроса | Контекст и лимит токенов генерации |
| `OLLAMA_NUM_GPU` | compose | Политика GPU для Ollama |

Подробнее: [`../../localscript-agent/README.md`](../../localscript-agent/README.md), [`../../localscript-agent/docs/experiments/BEST_CONFIG.md`](../../localscript-agent/docs/experiments/BEST_CONFIG.md).

---

## 4. Level 3 — компоненты внутри контейнера App

**Назначение:** разложить код в `localscript-agent/app/` на логические компоненты с понятными зависимостями.

### Компоненты и соответствие файлам

| Компонент (на диаграмме) | Файлы / пакет | Ответственность |
|--------------------------|---------------|-----------------|
| HTTP API | `main.py` | Маршруты `/generate`, `/refine`, `/debug`, `/health`; общий `httpx.AsyncClient` в lifespan |
| Пайплайн | `pipeline.py` | `run_generate_pipeline`, `run_refine_pipeline`, `run_debug_pipeline`, `run_repair_loop` |
| Клиент Ollama | `ollama_client.py` | `chat_completion`, `ollama_health`; ретраи и таймауты из настроек |
| Промпты и разбор ответа | `prompts.py`, `generate_parse.py`, `extract.py` | Сборка сообщений; разбор JSON (код / уточнение); извлечение Lua из «сырого» текста |
| Проверки Lua | `code_checks.py`, `validate.py` | Статические запреты (`require`, опасные `os.*`, и т.д.); `luac -p`; опциональный внешний линтер |
| Контракты и настройки | `models_io.py`, `config.py` | Pydantic-модели запросов/ответов; `Settings` из окружения |

### Модуль вне основного HTTP-потока

| Модуль | Файл | Заметка для C4 |
|--------|------|----------------|
| Песочница Lua (`wf`) | `sandbox.py` | Используется **скриптом** `scripts/eval_public.py` и тестами для задач с `eval.type == sandbox`; **не** вызывается из маршрутов `main.py` напрямую |

---

## 5. Deployment

**Смысл диаграммы:** один хост с Docker Compose; два контейнера и том для данных Ollama.

### Узлы развёртывания

| Узел | Содержимое |
|------|------------|
| Хост | Linux (или WSL2), Docker; при GPU — драйвер NVIDIA и настройка контейнера |
| Стек Compose | Сервисы `app` и `ollama`, сеть по умолчанию, volume `ollama` |

---

## 6. Динамика: упрощённый сценарий `POST /generate`

Нумерация стрелок задаётся стилем **C4 Dynamic** в PlantUML. Логика по коду:

1. Клиент вызывает **HTTP API** с телом `GenerateRequest`.
2. **Пайплайн** строит пользовательское сообщение через **промпты** и вызывает **клиент Ollama**.
3. **Ollama** возвращает текст; при необходимости **промпты/парсинг** извлекают Lua (в т.ч. fallback `extract_lua`).
4. **Пайплайн** запускает **проверки**; при ошибках — цикл **repair** (повторные вызовы LLM с текстом ошибок) в пределах лимита.

Детали полей ответа (`attempts`, `stop_reason`, `degraded`): см. `GenerateResponse` в `models_io.py`.

---

## 7. Публичные HTTP-операции (сводка)

| Метод | Путь | Назначение |
|-------|------|------------|
| GET | `/health` | Готовность сервиса и доступность Ollama |
| POST | `/generate` | Новая задача с нуля; возможен режим уточнения (`clarification`) |
| POST | `/refine` | Доработка кода по истории шагов refinement |
| POST | `/debug` | Анализ переданного Lua и предложение исправления (отдельный промпт) |

Полные схемы тел и кодов ошибок: OpenAPI в корне репозитория.

---

## 8. Глоссарий

| Термин | Значение в проекте |
|--------|---------------------|
| Repair | Повторная генерация фрагмента Lua после неуспешной валидации, с подсказкой по ошибкам |
| Clarification | Ответ модели в виде уточняющего вопроса вместо кода (см. `ResponseKind`) |
| Degraded | Флаг в ответе: итог выдан при исчерпании repair без полного прохождения проверок |

---

## 9. Что прикладывать к сдаче

- Отрендеренные из этой папки **PNG или PDF** (см. [`README.md`](README.md)).
- При необходимости платформы — перенос блоков в их шаблон; текст и таблицы из этого файла можно копировать в описание к диаграмме.
