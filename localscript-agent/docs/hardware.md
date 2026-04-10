# Hardware baseline (development machine)

Зафиксировано от участника для воспроизводимости и планирования нагрузки (train / inference).

## CPU

- **Model:** Intel Core Ultra 7 255HX
- **Architecture:** x86_64
- **Cores / threads:** 20 CPUs (по выводу `lscpu`: 20 cores per socket, 1 thread per core)
- **Max clock:** до ~5300 MHz (из `lscpu`)

## RAM

- **32 GB** (по данным пользователя)

## GPU

- **Model:** NVIDIA GeForce RTX 5070 Laptop
- **VRAM:** **8 GB**

## Disk

- **Free space:** ~100 GB+ (по данным пользователя)

## Сопоставление с условиями хакатона

- Жюри проверяет при **пиковом VRAM ≤ 8 GB** и **полностью на GPU** (без CPU offload).
- Эта машина имеет **ровно 8 GB VRAM**: запаса почти нет; выбор модели и квантизации должен укладываться в этот потолок при `num_ctx=4096`, `num_predict=256`, `batch=1`, `parallel=1`.
- CPU/RAM и диск достаточны для разработки, синтетического датасета и умеренного дообучения; при QLoRA следить за одновременным потреблением VRAM с Ollama (не держать тяжёлый train и inference на одной карте без планирования).

## Команды для повторной проверки

```bash
lscpu
free -h
nvidia-smi
df -h
```

При изменении железа обновите этот файл и при необходимости `experiments/runs.csv` (комментарий к прогону).
