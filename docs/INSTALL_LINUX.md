# Установка и запуск на Linux

Кратко: **Git**, **Docker Engine** + плагин **Compose v2**, при GPU — **драйвер NVIDIA** и **NVIDIA Container Toolkit**. Затем из корня репозитория: `cd localscript-agent && docker compose up --build`.

## 1. Git

```bash
sudo apt update
sudo apt install -y git
```

## 2. Docker Engine и Compose v2

На Ubuntu/Debian следуйте официальной документации Docker: [Install Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/).

Проверка:

```bash
docker version
docker compose version
```

Если команда `docker compose` не найдена, установите плагин Compose V2, например:

```bash
sudo apt install -y docker-compose-v2
```

(альтернатива — классический бинарь `docker-compose` из пакета `docker-compose`, тогда команда будет `docker-compose up --build`.)

Добавьте пользователя в группу `docker`, чтобы не использовать `sudo` для каждого запуска:

```bash
sudo usermod -aG docker "$USER"
```

Перелогиньтесь в сессию. Либо запускайте `docker` через `sudo`.

## 3. NVIDIA: драйвер и Container Toolkit

1. Установите проприетарный драйвер NVIDIA так, чтобы работал `nvidia-smi`.
2. Установите **NVIDIA Container Toolkit** по официальной инструкции: [Installing the NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).

При настройке репозитория пакетов для Debian/Ubuntu подставьте архитектуру вместо плейсхолдера, например `$(dpkg --print-architecture)` вместо жёстко прошитого `ARCH` в `sources.list` (см. также комментарии в [`../localscript-agent/docs/SETUP_GUIDE.md`](../localscript-agent/docs/SETUP_GUIDE.md)).

Проверка GPU в контейнере (образ подставьте по документации NVIDIA/Docker, важно увидеть вывод `nvidia-smi` из контейнера):

```bash
sudo docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi
```

## 4. Клонирование и запуск проекта

```bash
git clone <URL-вашего-репозитория>.git
cd <имя-каталога>
cd localscript-agent && docker compose up --build
```

Первый запуск: скачивание образов и **`ollama pull`** для модели из `OLLAMA_MODEL` (по умолчанию `qwen2.5-coder:7b`), см. `docker/entrypoint-ollama.sh`.

Явная подгрузка модели вручную (если контейнер уже поднят):

```bash
docker compose exec ollama ollama pull qwen2.5-coder:7b
```

## 5. Проверка здоровья

```bash
curl -s http://127.0.0.1:8080/health
curl -s http://127.0.0.1:11434/api/tags | head
```

## 6. Conda и разработка (опционально)

Из каталога `localscript-agent`:

```bash
./scripts/bootstrap_dev.sh
conda activate localscript-agent
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

Оценка публичного бенчмарка по HTTP:

```bash
python3 scripts/eval_public.py --http --base-url http://127.0.0.1:8080
```

## Типовые проблемы

| Симптом | Что сделать |
|---------|-------------|
| `unknown command: docker compose` | Установить `docker-compose-v2` или использовать `docker-compose`. |
| В контейнере нет GPU | Проверить установку `nvidia-container-toolkit`, перезапуск Docker, наличие `gpus: all` в `docker-compose.yml`. |
| `connection refused` на `:11434` | Дождаться старта сервиса `ollama`, смотреть логи `docker compose`. |
| Пустой список моделей / ошибки генерации | Выполнить `ollama pull qwen2.5-coder:7b` внутри контейнера или дождаться завершения entrypoint. |
| Ошибки `luac` | В conda-окружении должен быть пакет `lua` (`which luac`). |
