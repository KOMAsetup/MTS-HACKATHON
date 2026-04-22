# Краткая установка и запуск на Linux

Инструкция для Ubuntu 22.04/24.04 и совместимых систем.  

## 1) Установить зависимости

Нужны Docker Engine + Compose v2. Для запуска на GPU также нужны NVIDIA Driver и NVIDIA Container Toolkit.

Официальные инструкции:
- [Docker Engine (Ubuntu)](https://docs.docker.com/engine/install/ubuntu/)
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

Проверка после установки:

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

Перейдите в каталог проекта и затем в `localscript-agent`:

```bash
cd /путь/к/проекту/localscript-agent
docker compose up --build -d
docker compose logs -f
```

Что должно подняться:
- `ollama` на `11434`
- `app` на `8080`

Если модель не загрузилась автоматически:

```bash
docker compose exec ollama ollama pull qwen2.5-coder:7b
```

## 3) Запустить CLI и Web интерфейсы

В отдельном терминале:

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

Открыть в браузере: `http://127.0.0.1:8501`.

## 4) Прямое использование API

Быстрые проверки:

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
