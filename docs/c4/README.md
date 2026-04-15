# C4-диаграммы LocalScript (PlantUML + C4-PlantUML)

## Содержимое папки

| Путь | Назначение |
|------|------------|
| [`C4_OVERVIEW.md`](C4_OVERVIEW.md) | Текстовая модель C4: таблицы элементов, API, соответствие файлам в `localscript-agent/app/` |
| [`diagrams/*.puml`](diagrams/) | Исходники диаграмм (L1, L2, L3, deployment, dynamic) |
| [`smoke_c4.puml`](smoke_c4.puml) | Минимальная проверка, что PlantUML и `vendor/` настроены |
| `vendor/C4-PlantUML/` | Клон [C4-PlantUML](https://github.com/plantuml-stdlib/C4-PlantUML) (**в `.gitignore`**, не коммитится) |
| `out/` | Сюда пишутся PNG/SVG/PDF (**в `.gitignore`**) |

## Подготовка (один раз)

Из **корня репозитория** `mts`:

```bash
mkdir -p docs/c4/vendor
git clone --depth 1 https://github.com/plantuml-stdlib/C4-PlantUML.git docs/c4/vendor/C4-PlantUML
docker pull plantuml/plantuml:latest
```

## Рендер одной командой

Из **корня** `mts`:

```bash
./scripts/render_c4.sh png
```

Или SVG / PDF:

```bash
./scripts/render_c4.sh svg
./scripts/render_c4.sh pdf
```

Артефакты: **`docs/c4/out/`** (имена по `@startuml` / имени файла).

Флаг **`-DRELATIVE_INCLUDE=1`** внутри скрипта нужен, чтобы C4-PlantUML подтягивал зависимости **из локального `vendor/`**, а не по HTTPS из контейнера.

## Рендер вручную (без скрипта)

```bash
cd /path/to/mts
mkdir -p docs/c4/out
docker run --rm \
  -v "$(pwd)/docs/c4:/work" \
  -w /work \
  plantuml/plantuml:latest \
  -charset UTF-8 \
  -DRELATIVE_INCLUDE=1 \
  -o out \
  -tpng \
  diagrams/*.puml smoke_c4.puml
```

## Типичные проблемы

| Проблема | Решение |
|-----------|---------|
| `Cannot find C4_*.puml` | Выполните `git clone` в `docs/c4/vendor/C4-PlantUML` |
| Пустой/битый вывод для `04_*` / `05_*` | Убедитесь, что в команде есть **`-DRELATIVE_INCLUDE=1`** (скрипт уже добавляет) |
| Кракозябры | `-charset UTF-8` и сохранение `.puml` в UTF-8 |
| `permission denied` Docker | Группа `docker` или `sudo` (временно) |

## Связанные документы в репозитории

- Краткий черновик архитектуры: [`../localscript-agent/docs/architecture.md`](../localscript-agent/docs/architecture.md)
- Чеклист сдачи: [`../localscript-agent/docs/SUBMISSION.md`](../localscript-agent/docs/SUBMISSION.md)
