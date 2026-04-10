# Опциональное дообучение (QLoRA)

Ground truth только из **агентских** / PDF эталонов и **детерминированных** шаблонов (`data/synthetic/`). Не использовать ответы локальной Ollama как учителя.

## Рекомендуемый поток

1. Объединить `data/synthetic/seed_agent_examples.jsonl` и `generated.jsonl` в единый JSONL инструкций.
2. В отдельном conda env добавить `transformers`, `peft`, `trl` (или `unsloth` при совместимости с GPU).
3. Обучить QLoRA на базе той же архитектуры, что и модель в Ollama.
4. Merge адаптера → экспорт **GGUF** инструментами сообщества → `ollama create` / локальный тег.
5. Прогнать `scripts/eval_public.py`; если метрики ниже prompt-only baseline — откатиться к официальному `ollama pull`.

На **8 GB VRAM** не запускайте одновременно тяжёлый train и полный Ollama без планирования памяти.
