# Эталон конфигурации для сдачи

Обновляйте этот файл при выборе финальной модели и промпта.

| Параметр | Значение |
|----------|----------|
| Ollama pull | `ollama pull qwen2.5-coder:7b` |
| OLLAMA_MODEL | `qwen2.5-coder:7b` |
| num_ctx | 4096 |
| num_predict | 256 |
| num_batch | 1 (env `NUM_BATCH`; снижает пик VRAM на батчевых проходах) |
| temperature | 0.2 (env `TEMPERATURE`) |
| top_p | 0.95 |
| max_repair_attempts | 2 |
| System / few-shot | `app/prompts.py` |
| Лучший прогон (runs.csv) | _указать строку после замеров_ |

## VRAM

- Целевой пик ≤ **8 GB** при проверке жюри — см. [`docs/vram_smoke.md`](../vram_smoke.md).

## Примечание

Если используете кастомный GGUF: `ollama create -f models/Modelfile` и замените строку `ollama pull` на свою.
