# Гайд: что качалось и как поднять всё с нуля

Когда напишешь «готово», можно переходить к проверкам (`scripts/check_ollama.sh`, `eval_public.py`, метрики).

Корневые пошаговые инструкции по ОС: [INSTALL_LINUX.md](../../docs/INSTALL_LINUX.md), [INSTALL_WINDOWS.md](../../docs/INSTALL_WINDOWS.md).

---

## Что именно скачивал ассистент

Пытались взять **архив движка Ollama для Linux x86_64** с GitHub:

- Файл вроде `ollama-linux-amd64.tar.zst` из релизов [ollama/ollama](https://github.com/ollama/ollama/releases) (в сессии фигурировал тег **v0.20.5**).
- Размер порядка **~2 ГБ** — это **сам Ollama** (бинарник и библиотеки), **не** веса языковой модели.

Веса модели для генерации кода — **отдельно**, командой:

```bash
ollama pull qwen2.5-coder:7b
```

(ещё несколько гигабайт, в зависимости от квантизации и кэша.)

Итого на диске обычно нужно: **Ollama + модель +** (опционально) образы Docker.

---

## Что должно быть на машине

1. **Драйвер NVIDIA** и рабочий `nvidia-smi` (для GPU-инференса).
2. Либо **Docker + GPU** для compose, либо **нативный Ollama** без Docker.
3. **Conda** (или venv) для Python-приложения; в окружении должны быть **lua** и **luac** (в проекте это через conda-forge).

Корень репозитория — каталог, где лежат `localscript-agent/`, `instruction.txt`, `README.md`. Код сервиса — в `localscript-agent/`.

---

## Вариант 1 — Docker + GPU (как в README)

Подходит, если установлены Docker Engine и поддержка GPU (часто пакет вроде `nvidia-container-toolkit`; точное имя зависит от дистрибутива).

```bash
cd /path/to/<корень-репозитория>/localscript-agent
docker compose up --build
```

- API приложения: `http://127.0.0.1:8080`
- Ollama: `http://127.0.0.1:11434`
- Образ при старте тянет модель из `OLLAMA_MODEL` (по умолчанию `qwen2.5-coder:7b`), см. `docker/entrypoint-ollama.sh`.

Первый запуск может занять много времени из‑за `docker pull` и `ollama pull`.

---

## Вариант 2 — Ollama нативно, приложение через conda

### 2.1 Установить Ollama (системно, с sudo)

Официально:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Скрипт ставит бинарник и сервис; для моделей используется каталог вроде `~/.ollama`.

Запуск демона (зависит от дистрибутива — часто уже через systemd):

```bash
ollama serve
```

В отдельном терминале:

```bash
ollama pull qwen2.5-coder:7b
```

Проверка:

```bash
curl -s http://127.0.0.1:11434/api/tags | head
```

### 2.2 Python-окружение и приложение

```bash
cd /path/to/<корень-репозитория>/localscript-agent
./scripts/bootstrap_dev.sh
conda activate localscript-agent
```

При необходимости подтянуть зависимости из `requirements.txt` (если менялись относительно `environment.yml`):

```bash
pip install -r requirements.txt
```

Переменные по умолчанию смотри в `app/config.py` / `.env`. Для локального Ollama обычно достаточно:

- `OLLAMA_HOST=http://127.0.0.1:11434`
- `OLLAMA_MODEL=qwen2.5-coder:7b`

Запуск API:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

---

## Проверки после «готово»

1. Ollama отвечает:

   ```bash
   ./scripts/check_ollama.sh
   ```

2. Здоровье приложения:

   ```bash
   curl -s http://127.0.0.1:8080/health
   ```

3. Линты и тесты:

   ```bash
   ./scripts/quality.sh
   ```

4. Бенчмарк (с поднятым API):

   ```bash
   python3 scripts/eval_public.py --http --base-url http://127.0.0.1:8080
   ```

   Быстрый смоук на двух задачах:

   ```bash
   python3 scripts/eval_public.py --tasks benchmarks/synthetic_smoke.json
   ```

Результаты экспериментов фиксируй в `experiments/runs.csv` и `docs/experiments/SUMMARY.md` (см. `docs/experiments/BEST_CONFIG.md`).

---

## Если что-то не взлетело

| Симптом | Что проверить |
|--------|----------------|
| `unknown flag: --build` или `unknown command: docker compose` | На Ubuntu часто не установлен плагин Compose V2: `sudo apt install docker-compose-v2`, затем снова `docker compose up --build`. Либо классический пакет: `sudo apt install docker-compose` и команда `docker-compose up --build`. |
| `connection refused` на 11434 | Запущен ли `ollama serve` или контейнер `ollama` из compose. |
| Нет GPU в контейнере | Установлен ли `nvidia-container-toolkit`, в compose ли `gpus: all`. |
| Ошибки `luac` / sandbox | В активном conda-окружении есть ли `lua`/`luac` (`which luac`). |
| Долгий первый старт Docker | Нормально: скачивание образа и модели. |

---

## Краткий чеклист перед словом «готово»

- [ ] `nvidia-smi` показывает GPU (если целишься в GPU).
- [ ] Либо `docker compose up` работает, либо `ollama serve` + `ollama pull qwen2.5-coder:7b`.
- [ ] `curl http://127.0.0.1:11434/api/tags` возвращает JSON.
- [ ] `conda activate localscript-agent`, `uvicorn` поднимает `:8080`.
- [ ] `./scripts/quality.sh` проходит.

После этого можно писать **«готово»** — дальше имеет смысл гонять полный `eval_public.py` и итерации по промпту/метрикам.
