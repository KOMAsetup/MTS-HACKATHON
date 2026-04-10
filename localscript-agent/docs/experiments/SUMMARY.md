# Журнал экспериментов

Добавляйте строку после каждого осмысленного изменения (промпт, few-shot, temperature, repair, датасет).

| Дата       | Гипотеза | Изменение | M1/M2/M3 (eval_public) | Вывод        |
|------------|----------|-----------|-------------------------|--------------|
| 2026-04-10 | меньше VRAM / стабильнее ответ | `num_batch` в запросе Ollama; уточнён system prompt (без markdown); `--tasks` + `benchmarks/synthetic_smoke.json`; `scripts/check_ollama.sh` | не измерено (Ollama недоступен на хосте) | после `ollama serve` + pull — прогнать полный `eval_public.py` и записать строку в `runs.csv` |
| 2026-04-10 | меньше ложных static + ясные ошибки eval | Статгард: не банить `package` как имя поля; разрешить `os.time`/`os.date`; промпт: REST-массив, ISO8601, `lua{…}lua`; `eval_public` добавляет `heuristic:*` и для `type=heuristic`; ruff format | было 3/8 у пользователя — **пересобрать app-образ** и перепрогнать | см. `app/validate.py`, `app/prompts.py`, `scripts/eval_public.py` |
| 2026-04-10 | pub_05 эвристика + few-shot lua/ISO/parsedCsv | `public_tasks` pub_05: `ensureArray` → `_utils.array`; few-shot №3 (lua{…}lua+tonumber); system: ISO `%04d-%02d…`, фильтры через `_utils.array.new` | пользователь **4/8** после первого патча; дальше — rebuild app + eval | агент не может дернуть твой `:8080` из среды Cursor |
| 2026-04-10 | pub_04 / pub_07 | pub_04: эвристика `%02d`+`sub` вместо литерала даты в коде; pub_07: запрет JS-фрагментов, few-shot на русском | пользователь **6/8** | rebuild app + eval |
| 2026-04-10 | pub_07 plain JSON | system: не `format('{\"num\"...}')` без `lua{`/`}lua`; `build_user_message`: hard constraint если в задаче есть `lua{`…`}lua` | пользователь **7/8** | rebuild app + eval → цель 8/8 |
| YYYY-MM-DD | baseline | —         | заполнить               | оставить     |

Метрики:

- **M1**: доля задач с успешным `luac`.
- **M2**: sandbox (где включён в `public_tasks.json`).
- **M3**: эвристики `expected_contains`.

Полный машинный лог — `experiments/runs.csv`.

## Цикл улучшения (tune)

1. Запустить `python3 scripts/eval_public.py` (с `--http` при работе через контейнер).
2. Разобрать провалы по `results[].errors`.
3. Править `app/prompts.py` или параметры в `.env` / `docker-compose.yml`.
4. Повторить минимум 3–5 итераций; лучший конфиг отразить в `BEST_CONFIG.md`.
