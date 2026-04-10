# Установка и запуск на Windows (до первого запуска API)

Рекомендуемый путь: **Windows 10/11** + **WSL2** + **Docker Desktop** с интеграцией WSL. Команды запуска проекта выполняются **в терминале Linux внутри WSL** (например Ubuntu), как на обычном Linux — см. также подробный [INSTALL_LINUX.md](INSTALL_LINUX.md).

**Что в итоге получится:** установлены WSL2 и Docker Desktop, при наличии видеокарты NVIDIA настроен GPU в WSL; репозиторий лежит в файловой системе WSL; выполнены `docker compose up --build`, проверены `curl` на порты **8080** и **11434**, сделан тестовый запрос к `/generate`.

---

## 0. Что установить (сводка)

| Шаг | Компонент | Зачем |
|-----|-----------|--------|
| 1 | **WSL2** + дистрибутив (**Ubuntu**) | Среда, близкая к Linux; Docker и пути как в инструкции жюри |
| 2 | **Docker Desktop for Windows** | Docker Engine и `docker compose` из WSL |
| 3 | (Опционально) **Git for Windows** или **git в WSL** | Клонирование репозитория |
| 4 | (Для GPU) Драйвер **NVIDIA** на Windows + настройка **WSL GPU** | Ускорение Ollama в контейнере |

**Важно:** клонируйте проект в каталог внутри **Linux-файловой системы WSL** (например `~/projects/...`), а не только в `C:\...` смонтированный как `/mnt/c/...` — так быстрее сборка и I/O Docker.

**Место на диске:** ориентир **15–20 GB** под Docker-образы и модель `qwen2.5-coder:7b`.

---

## 1. Включить WSL2 и поставить Ubuntu

Официально: [Install WSL](https://learn.microsoft.com/en-us/windows/wsl/install).

### 1.1 Типовые шаги (PowerShell **от администратора**)

```powershell
wsl --install
```

По умолчанию ставится Ubuntu и WSL2. Если WSL уже был, проверьте версию:

```powershell
wsl --status
wsl --list --verbose
```

Для существующего дистрибутива с версией 1 можно обновить до 2:

```powershell
wsl --set-version Ubuntu 2
```

### 1.2 Первый запуск Ubuntu

Из меню «Пуск» откройте **Ubuntu**, задайте пользователя и пароль Linux.

### 1.3 Проверка внутри WSL

```bash
uname -a
lsb_release -a
```

Должно быть ядро WSL и дистрибутив Ubuntu (или ваш выбор).

---

## 2. Docker Desktop for Windows

Официально: [Docker Desktop on Windows](https://docs.docker.com/desktop/setup/install/windows-install/).

### 2.1 Установить

1. Скачайте установщик **Docker Desktop** с сайта Docker.
2. Запустите установщик, при необходимости включите опцию использования **WSL 2** вместо Hyper-V (актуальные галочки смотрите в мастере установки).
3. Перезагрузите компьютер, если установщик попросит.

### 2.2 Настройки Docker Desktop

Откройте **Docker Desktop** → **Settings**:

- **General:** можно включить «Use the WSL 2 based engine» (если доступно).
- **Resources → WSL Integration:** включите интеграцию для вашего дистрибутива (**Ubuntu**).
- Убедитесь, что используются **Linux containers** (не Windows containers).

Нажмите **Apply & Restart**.

### 2.3 Проверка из WSL

Откройте терминал **Ubuntu (WSL)**:

```bash
docker version
docker compose version
docker run --rm hello-world
```

- Должны быть и клиент, и сервер Docker.
- `hello-world` должен завершиться успешно.

Если `docker: command not found` — в Docker Desktop включите WSL integration для этого дистрибутива и перезапустите WSL (`wsl --shutdown` в PowerShell, снова открыть Ubuntu).

---

## 3. GPU NVIDIA в WSL и Docker (опционально, но нужно для условий хакатона)

### 3.1 Драйвер на стороне Windows

Установите **актуальный драйвер NVIDIA для Windows**, который поддерживает **WSL** (на странице загрузки NVIDIA обычно указана поддержка WSL2). Перезагрузка может потребоваться.

### 3.2 Проверка в WSL

В терминале Ubuntu:

```bash
nvidia-smi
```

Если команда не найдена или устройств нет — см. документацию:

- [CUDA on WSL User Guide](https://docs.nvidia.com/cuda/wsl-user-guide/index.html)
- Раздел про GPU в [Docker Desktop WSL](https://docs.docker.com/desktop/features/wsl/)

После исправления снова `nvidia-smi` в WSL.

### 3.3 GPU внутри контейнера

Когда `nvidia-smi` работает в WSL, проверьте (как в Linux-гайде):

```bash
docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi
```

Успешный вывод таблицы GPU — контейнеры из `docker compose` смогут использовать `gpus: all` в [`docker-compose.yml`](../localscript-agent/docker-compose.yml).

---

## 4. Git в WSL

```bash
sudo apt update
sudo apt install -y git
git --version
```

(Альтернатива: **Git for Windows** и клон в доступном WSL-пути — но единый стиль — всё в WSL.)

---

## 5. Клонирование репозитория

В WSL, в домашнем каталоге или `~/projects`:

```bash
mkdir -p ~/projects
cd ~/projects
git clone <URL-вашего-репозитория>.git
cd <имя-каталога>
ls
```

Проверьте наличие **`localscript-agent/`** и **`docker-compose.yml`** внутри него:

```bash
ls localscript-agent
```

---

## 6. Первый запуск: Docker Compose

```bash
cd ~/projects/<имя-каталога>/localscript-agent
docker compose up --build
```

### 6.1 Что ожидать

1. Загрузка образов и сборка **app**.
2. Старт **ollama** (порт **11434**), затем **app** (порт **8080**).
3. В контейнере Ollama выполняется **`ollama pull`** для **`qwen2.5-coder:7b`** (см. [`entrypoint-ollama.sh`](../localscript-agent/docker/entrypoint-ollama.sh)) — первая загрузка может занять **долго**.

Фоновый режим:

```bash
docker compose up --build -d
docker compose logs -f
```

---

## 7. Проверки после старта

Во **втором** окне терминала WSL:

### 7.1 Список моделей Ollama

```bash
curl -s http://127.0.0.1:11434/api/tags
```

В JSON в `models` должна быть **`qwen2.5-coder:7b`**. Если пусто:

```bash
cd ~/projects/<имя>/localscript-agent
docker compose exec ollama ollama pull qwen2.5-coder:7b
```

### 7.2 Health API

```bash
curl -s http://127.0.0.1:8080/health
```

### 7.3 Первый запрос генерации

```bash
curl -s http://127.0.0.1:8080/generate \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Функция factorial(n) для целого n >= 0, на Lua"}'
```

---

## 8. Порты 8080 и 11434

По умолчанию конфликтов часто нет. Если порт занят:

- Остановите другой сервис **на Windows или в WSL**, который слушает тот же порт, **или**
- Отредактируйте проброс в [`../localscript-agent/docker-compose.yml`](../localscript-agent/docker-compose.yml) (секция `ports:`), например `"8081:8080"`, и обращайтесь к API на **8081**.

Проверка, кто слушает порт в WSL:

```bash
ss -tlnp | grep -E '8080|11434' || true
```

---

## 9. Остановка

```bash
cd ~/projects/<имя>/localscript-agent
docker compose down
```

---

## Ограничения без GPU

Если видеокарты нет или GPU не виден в Docker:

- Ollama может работать на **CPU** (очень медленно).
- Для отладки HTTP/API этого может хватить; для **требований жюри** (VRAM ≤ 8 GB, инференс на GPU) нужна корректная связка **NVIDIA + WSL + Docker**.

Вариант без Docker GPU: нативный Ollama в WSL + приложение в conda — см. [SETUP_GUIDE — вариант 2](../localscript-agent/docs/SETUP_GUIDE.md).

---

## Типовые проблемы (Windows / WSL)

| Симптом | Что сделать |
|---------|-------------|
| Docker не виден из WSL | Docker Desktop запущен; Settings → WSL Integration → включить Ubuntu; `wsl --shutdown`. |
| Медленная сборка при клоне на `/mnt/c/...` | Перенести репозиторий в `~/...` внутри WSL. |
| `nvidia-smi` не работает в WSL | Обновить драйвер NVIDIA на Windows, см. [CUDA WSL](https://docs.nvidia.com/cuda/wsl-user-guide/index.html). |
| Нет GPU в `docker run --gpus all` | Обновить Docker Desktop; проверить документацию GPU для WSL2. |
| Пустой список моделей | `docker compose exec ollama ollama pull qwen2.5-coder:7b`. |

---

## Дополнительно

- Подробные шаги для Linux (Docker Engine, NVIDIA Toolkit, troubleshooting): [INSTALL_LINUX.md](INSTALL_LINUX.md).
- Ollama, conda, нативный режим: [`../localscript-agent/docs/SETUP_GUIDE.md`](../localscript-agent/docs/SETUP_GUIDE.md).
- Корневой обзор репозитория: [`../README.md`](../README.md).
