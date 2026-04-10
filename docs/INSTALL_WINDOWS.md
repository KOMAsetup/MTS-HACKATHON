# Установка и запуск на Windows

Рекомендуемый путь: **Docker Desktop** с бэкендом **WSL2** и включённой поддержкой GPU, либо работа **целиком внутри WSL2 (Ubuntu)** — тогда шаги совпадают с [INSTALL_LINUX.md](INSTALL_LINUX.md) относительно каталога проекта в Linux-файловой системе WSL.

## 1. Docker Desktop и WSL2

- Официальная документация Docker: [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/).
- Включите WSL2 по инструкции Microsoft, если ещё не включено: [Install WSL](https://learn.microsoft.com/en-us/windows/wsl/install).

В настройках Docker Desktop включите интеграцию с нужным дистрибутивом WSL и используйте **Linux-контейнеры**.

## 2. GPU в WSL / Docker

Требования к версиям драйвера и Docker Desktop меняются; ориентируйтесь на актуальные страницы:

- NVIDIA: [CUDA on WSL User Guide](https://docs.nvidia.com/cuda/wsl-user-guide/index.html)
- Docker: раздел GPU в документации Docker Desktop for Windows

После настройки в терминале WSL должны работать `nvidia-smi` (если установлен драйвер NVIDIA для Windows с поддержкой WSL) и тест GPU в Docker (см. Linux-гайд).

## 3. Клонирование и запуск

В **WSL** (предпочтительно, репозиторий в Linux FS, например `~/projects/mts`):

```bash
git clone <URL-вашего-репозитория>.git
cd <имя-каталога>
cd localscript-agent && docker compose up --build
```

Если клон лежит на диске `C:` и монтируется в WSL (`/mnt/c/...`), I/O Docker может быть медленнее — для разработки лучше каталог в домашнем каталоге WSL.

## 4. Порты и конфликты

По умолчанию: приложение **8080**, Ollama **11434**. Если порты заняты, измените секцию `ports` в [`../localscript-agent/docker-compose.yml`](../localscript-agent/docker-compose.yml) или остановите конфликтующие сервисы.

## 5. Проверка

```bash
curl -s http://127.0.0.1:8080/health
```

Подгрузка модели при необходимости:

```bash
docker compose exec ollama ollama pull qwen2.5-coder:7b
```

## Ограничения без GPU

Если Docker или Ollama видят только CPU, инференс будет существенно медленнее; для условий хакатона ожидается **GPU ≤ 8 GB VRAM**. Для локальной отладки логики API CPU может быть достаточен, для проверки VRAM и скорости — нужна карта NVIDIA и корректная передача GPU в контейнер.

## Дополнительно

Детали стека Ollama и переменных: [`../localscript-agent/docs/SETUP_GUIDE.md`](../localscript-agent/docs/SETUP_GUIDE.md).
