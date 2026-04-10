# Synthetic / training data

- **`seed_agent_examples.jsonl`**: hand-authored ground-truth rows (Cursor agent), safe for QLoRA targets.
- **`generated.jsonl`**: produced by `scripts/generate_synthetic_dataset.py` — only deterministic variations of verified templates (no LLM labels).

Do **not** use local Ollama outputs as training labels.
