# Краткая установка и запуск на Windows (WSL2)

Рекомендуемый путь: Windows 10/11 + WSL2 (Ubuntu) + Docker Desktop с интеграцией в WSL.  
Команды проекта выполняются внутри терминала Ubuntu (WSL).

Инструкция предполагает, что код проекта уже есть в WSL (зависимость от `git` не требуется).

## 1) Установить зависимости

Минимум:
- WSL2 + Ubuntu
- Docker Desktop (WSL integration для вашей Ubuntu)

Для GPU (опционально):
- NVIDIA драйвер на Windows с поддержкой WSL2

Официальные инструкции:
- [Install WSL](https://learn.microsoft.com/en-us/windows/wsl/install)
- [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
- [CUDA on WSL](https://docs.nvidia.com/cuda/wsl-user-guide/index.html)

Проверка из Ubuntu (WSL):

```bash
docker version
docker compose version
```

Проверка GPU (опционально):

```bash
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi
```

## 2) Поднять контейнеры

```bash
cd /путь/к/проекту/localscript-agent
docker compose up --build -d
docker compose logs -f
```

После старта должны быть доступны:
- API: `http://127.0.0.1:8080`
- Ollama: `http://127.0.0.1:11434`

Если модель не подтянулась автоматически:

```bash
docker compose exec ollama ollama pull qwen2.5-coder:7b
```

## 3) Запустить CLI и Web интерфейсы

В отдельном терминале Ubuntu (WSL):

```bash
cd /путь/к/проекту/localscript-agent
./scripts/bootstrap_dev.sh
conda activate localscript-agent
```

CLI:

```bash
python scripts/demo_cli.py --base-url http://127.0.0.1:8080
```

Web (Streamlit):

```bash
python -m streamlit run scripts/demo_streamlit.py --server.address 0.0.0.0 --server.port 8501
```

Открыть в браузере Windows: `http://localhost:8501`.

## 4) Прямое использование API

Проверка API и Ollama:

```bash
curl -s http://127.0.0.1:8080/health
curl -s http://127.0.0.1:11434/api/tags
```

Пример генерации:

```bash
curl -s http://127.0.0.1:8080/generate \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Напиши Lua-функцию factorial(n) для n >= 0"}'
```

## Остановка

```bash
cd /путь/к/проекту/localscript-agent
docker compose down
```
