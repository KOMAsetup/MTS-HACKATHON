# Полная установка и запуск на Linux с нуля

Инструкция рассчитана на **Ubuntu 22.04 / 24.04** (и близкие Debian-подобные системы). На других дистрибутивах имена пакетов и пути к репозиториям могут отличаться — ориентируйтесь на официальные гайды Docker и NVIDIA, ссылки ниже.

**Что в итоге получится:** на машине установлены все зависимости (Git, Docker Compose, при необходимости NVIDIA stack), вы клонировали репозиторий, подняли сервисы, дождались загрузки модели, проверили `GET /health` и выполнили тестовый `POST /generate`.

---

## 0. Что установить (сводка)

| Шаг | Компонент | Зачем |
|-----|-----------|--------|
| 1 | **Git** | Клонировать репозиторий |
| 2 | **Docker Engine** + **Compose v2** | Однострочный запуск из `docker-compose.yml` |
| 3 | (Для GPU) **Драйвер NVIDIA** | `nvidia-smi`, ускорение Ollama |
| 4 | (Для GPU в Docker) **NVIDIA Container Toolkit** | Проброс GPU в контейнер (`--gpus all`) |
| 5 | Код проекта | `git clone` → каталог с `localscript-agent/` |

**Без GPU:** compose можно запустить и на CPU (медленно, для хакатона обычно нужна видеокарта). В `docker-compose.yml` указано `gpus: all` — если GPU нет, см. раздел [Запуск без NVIDIA GPU](#запуск-без-nvidia-gpu-опционально).

**Место на диске (ориентир):** образы Docker (Ollama + приложение) и модель `qwen2.5-coder:7b` — **несколько гигабайт**; свободно иметь **15–20 GB** под кэш Docker и модели.

---

## 1. Git: установка и проверка

### 1.1 Установить

```bash
sudo apt update
sudo apt install -y git
```

### 1.2 Проверить

```bash
git --version
```

Ожидается вывод вроде `git version 2.x.x`. Если команда не найдена — повторите установку или проверьте `PATH`.

---

## 2. Docker Engine и Compose v2

Официальный путь для Ubuntu: [Install Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/).

> Ниже команды Docker для Ubuntu даны с `sudo` (`sudo docker ...` / `sudo docker compose ...`).
> Если у вас уже настроена группа `docker`, можно запускать эти же команды без `sudo`.

### 2.1 Типовая последовательность (Ubuntu)

Удалите старые пакеты Docker (если были), затем по документации Docker:

1. Установите зависимости: `ca-certificates`, `curl` и т.д.
2. Добавьте **официальный** GPG-ключ и репозиторий Docker для вашей версии Ubuntu.
3. Установите пакеты: `docker-ce`, `docker-ce-cli`, `containerd.io`, `docker-buildx-plugin`, **`docker-compose-plugin`**.

Пример после настройки репозитория (точные команды возьмите со страницы Docker — они обновляются):

```bash
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### 2.2 Запустить демон Docker

```bash
sudo systemctl enable --now docker
sudo systemctl status docker
```

В статусе должно быть **active (running)**.

### 2.3 Проверить Docker и Compose

```bash
sudo docker version
sudo docker compose version
```

- **`docker version`** — должен показать и Client, и Server (если Server пустой — демон не запущен или нет прав).
- **`docker compose version`** — должна быть **v2** (например `v2.29.x`).  
  Если команды `docker compose` нет, но установлен старый пакет:

  ```bash
  sudo apt install -y docker-compose-v2
  ```

  Либо используйте классический бинарь: `sudo apt install docker-compose` и везде вместо `docker compose` пишите `docker-compose` (с дефисом).

### 2.4 Запуск Docker без `sudo` (опционально)

```bash
sudo usermod -aG docker "$USER"
```

**Выйдите из сессии** (logout) или перезагрузите компьютер, затем снова войдите. Проверка:

```bash
sudo docker run --rm hello-world
```

Должно напечататься сообщение об успешном запуске контейнера.

---

## 3. NVIDIA: драйвер (только для GPU)

### 3.1 Установить драйвер

На Ubuntu часто достаточно **Additional Drivers** в GUI или пакета из репозитория (например `nvidia-driver-XXX` для вашей карты). Официально: [NVIDIA drivers — Linux](https://www.nvidia.com/Download/index.aspx) и документация вашего дистрибутива.

### 3.2 Проверить

```bash
nvidia-smi
```

Ожидается таблица с **GPU**, драйвером и памятью. Если команда не найдена или «no devices» — драйвер не установлен или не подходит; GPU в Docker дальше не заработает.

---

## 4. NVIDIA Container Toolkit (GPU внутри Docker)

Официальная инструкция: [Installing the NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).

### 4.1 Что сделать по смыслу

1. Подключить репозиторий пакетов NVIDIA для вашего дистрибутива.
2. Установить пакет **`nvidia-container-toolkit`**.
3. Настроить рантайм Docker: **`nvidia-ctk runtime configure --runtime=docker`**
4. **Перезапустить** Docker: `sudo systemctl restart docker`

### 4.2 Про `ARCH` в `sources.list`

В инструкциях NVIDIA иногда встречается плейсхолдер архитектуры. Для **amd64** на обычном ПК подставьте архитектуру так:

```bash
dpkg --print-architecture
```

Должно быть `amd64`. В строках для `sources.list` не оставляйте буквальный текст `ARCH` — используйте вывод команды или готовые блоки с официальной страницы для **Ubuntu** / **Debian**.

### 4.3 Проверка: GPU виден в контейнере

После настройки toolkit выполните (образ можно взять актуальный с [Docker Hub NVIDIA CUDA](https://hub.docker.com/r/nvidia/cuda) или из документации; важен успешный вывод `nvidia-smi` **из контейнера**):

```bash
sudo docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi
```

- Если видите ту же GPU, что и на хосте — **готово**.
- Если ошибка про `--gpus` или драйвер — вернитесь к шагам 3–4 и логам `sudo journalctl -u docker`.

---

## 5. Получить код репозитория

### 5.1 Клонировать

```bash
cd ~
git clone <URL-вашего-репозитория>.git
cd <имя-каталога-клона>
```

### 5.2 Проверить структуру

В корне должны быть как минимум:

- `localscript-agent/` (внутри — `docker-compose.yml`, `Dockerfile`)
- `README.md`, `instruction.txt` (и т.д. по вашему репо)

```bash
ls
ls localscript-agent
```

---

## 6. Первый запуск: Docker Compose

Все команды ниже — из каталога **`localscript-agent`**.

```bash
cd ~/путь/к/клону/localscript-agent
sudo docker compose up --build
```

### 6.1 Что происходит при первом запуске

1. Скачиваются образы **`ollama/ollama`** и собирается образ **приложения** (`app`).
2. Поднимается сервис **ollama** (порт **11434**), затем **app** (порт **8080**).
3. Скрипт [`docker/entrypoint-ollama.sh`](../localscript-agent/docker/entrypoint-ollama.sh) запускает `ollama serve`, ждёт несколько секунд и выполняет **`ollama pull`** для модели из `OLLAMA_MODEL` (по умолчанию **`qwen2.5-coder:7b`**). Первая загрузка модели может занять **десятки минут** при медленном интернете.

Оставьте терминал открытым; логи должны показывать прогресс pull. Если pull завершился с ошибкой, в логах будет предупреждение — тогда см. раздел 8.

### 6.2 Запуск в фоне (по желанию)

```bash
sudo docker compose up --build -d
sudo docker compose logs -f
```

Отключиться от логов: `Ctrl+C` (контейнеры останутся при `-d`).

---

## 7. Проверки после старта (обязательный минимум)

Откройте **второй** терминал на хосте (пока `compose up` работает или при `up -d`).

### 7.1 Ollama и список моделей

```bash
curl -s http://127.0.0.1:11434/api/tags
```

Должен вернуться **JSON**; внутри `models` должна быть запись с именем вроде **`qwen2.5-coder:7b`**. Если `models` пустой — см. раздел 8.

### 7.2 Health приложения

```bash
curl -s http://127.0.0.1:8080/health
```

Ожидается JSON с признаками готовности сервиса и доступности Ollama (формат смотрите в ответе; ошибка подключения — приложение ещё не поднялось или порт занят).

### 7.3 Первый запрос генерации (проверка сквозняка)

```bash
curl -s http://127.0.0.1:8080/generate \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Функция factorial(n) для целого n >= 0, на Lua"}'
```

Должен прийти ответ с полем кода/текста (как в вашем API). Долгое ожидание на первом запросе нормально — прогрев модели.

### 7.4 Запуск CLI-интерфейса (опционально)

CLI находится в `localscript-agent/scripts/demo_cli.py` и работает как клиент к уже поднятому API.

В **третьем** терминале:

```bash
cd /путь/к/localscript-agent
./scripts/bootstrap_dev.sh
conda activate localscript-agent
python scripts/demo_cli.py --base-url http://127.0.0.1:8080
```

Полезные команды в CLI: `/health`, `/help`, `/refine`, `/debug`.

### 7.5 Запуск Web-интерфейса Streamlit (опционально)

Web UI находится в `localscript-agent/scripts/demo_streamlit.py` и также обращается к API на `:8080`.

```bash
cd /путь/к/localscript-agent
conda activate localscript-agent
python -m streamlit run scripts/demo_streamlit.py --server.address 0.0.0.0 --server.port 8501
```

Откройте в браузере: `http://127.0.0.1:8501`.

Если запускаете API через Docker, а GUI/CLI с хоста — это нормальный режим: оба интерфейса являются внешними клиентами одного и того же HTTP API.

---

## 8. Если модель не подтянулась автоматически

Узнайте имя контейнера Ollama:

```bash
sudo docker ps --format '{{.Names}}\t{{.Image}}'
```

Найдите контейнер с образом **`ollama/ollama`**. Либо из каталога `localscript-agent`:

```bash
sudo docker compose ps
```

Ручная подгрузка (имя сервиса в compose — **`ollama`**):

```bash
cd /путь/к/localscript-agent
sudo docker compose exec ollama ollama pull qwen2.5-coder:7b
```

Альтернатива через `docker exec` (подставьте **реальное** имя контейнера):

```bash
sudo docker exec -it localscript-agent-ollama-1 ollama pull qwen2.5-coder:7b
```

Снова проверьте: `curl -s http://127.0.0.1:11434/api/tags`.

---

## 9. Остановка контейнеров

Из каталога `localscript-agent`:

```bash
sudo docker compose down
```

Данные моделей Ollama по умолчанию в **именованном volume** compose — при следующем `up` модель может не качаться заново.

---

## 10. Conda и разработка без пересборки образа (опционально)

Нужно, если вы меняете Python-код локально и запускаете Uvicorn на хосте, а Ollama оставляете в Docker **или** нативно.

### 10.1 Установить Miniconda/Anaconda

С официального сайта: [Miniconda](https://docs.conda.io/en/latest/miniconda.html). Проверка:

```bash
conda --version
```

### 10.2 Окружение проекта

```bash
cd /путь/к/localscript-agent
./scripts/bootstrap_dev.sh
conda activate localscript-agent
```

Проверка **`luac`** (нужен для валидации Lua):

```bash
which luac
luac -v
```

### 10.3 Запуск API на хосте

Ollama должна быть доступна по `OLLAMA_HOST` (например `http://127.0.0.1:11434`, если контейнер ollama запущен и порт проброшен).

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

### 10.4 Бенчмарк по HTTP

```bash
python3 scripts/eval_public.py --http --base-url http://127.0.0.1:8080
```

---

## Запуск без NVIDIA GPU (опционально)

На машине без GPU или без toolkit команда `sudo docker compose up` может завершиться ошибкой из‑за директивы **`gpus: all`** в [`docker-compose.yml`](../localscript-agent/docker-compose.yml).

Варианты:

- Временно закомментировать/убрать блок `gpus: all` у сервиса `ollama` (только для локальной отладки; для условий хакатона обычно нужен GPU).
- Либо использовать **Вариант 2** из [`../localscript-agent/docs/SETUP_GUIDE.md`](../localscript-agent/docs/SETUP_GUIDE.md): нативный Ollama + приложение в conda.

---

## Типовые проблемы

| Симптом | Что сделать |
|---------|-------------|
| `unknown command: docker compose` | Установить плагин: `docker-compose-plugin` или пакет `docker-compose-v2`; либо `docker-compose` (v1). |
| `permission denied` при `docker run` | Либо запускать с `sudo`, либо добавить пользователя в группу `docker` и перелогиниться. |
| `could not select device driver` / нет GPU в контейнере | Установить и настроить **nvidia-container-toolkit**, перезапустить Docker; проверить `sudo docker run --rm --gpus all ... nvidia-smi`. |
| `connection refused` на **11434** | Дождаться старта контейнера `ollama`, смотреть `sudo docker compose logs ollama`. |
| Пустой `models` в `/api/tags` | Выполнить `sudo docker compose exec ollama ollama pull qwen2.5-coder:7b`. |
| Порт **8080** или **11434** занят | Остановить другой сервис или изменить `ports:` в `docker-compose.yml`. |
| Ошибки **`luac`** при conda-запуске | В активном env должен быть пакет `lua` из conda-forge (`which luac`). |

Дополнительно: [`../localscript-agent/docs/SETUP_GUIDE.md`](../localscript-agent/docs/SETUP_GUIDE.md), [`../README.md`](../README.md).
