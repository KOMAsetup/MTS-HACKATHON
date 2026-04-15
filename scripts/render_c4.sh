#!/usr/bin/env bash
# Рендер всех C4-диаграмм LocalScript (PlantUML в Docker).
# Запуск из корня репозитория mts: ./scripts/render_c4.sh [png|svg|pdf]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
C4="${ROOT}/docs/c4"

if [[ ! -d "${C4}/vendor/C4-PlantUML" ]]; then
  echo "Нет ${C4}/vendor/C4-PlantUML. Выполните:" >&2
  echo "  mkdir -p ${C4}/vendor && git clone --depth 1 https://github.com/plantuml-stdlib/C4-PlantUML.git ${C4}/vendor/C4-PlantUML" >&2
  exit 1
fi

mkdir -p "${C4}/out"

fmt="${1:-png}"
case "${fmt}" in
  png|svg|pdf) ;;
  *)
    echo "Использование: $0 [png|svg|pdf]" >&2
    exit 2
    ;;
esac

flag="-t${fmt}"

shopt -s nullglob
cd "${C4}"
paths=(diagrams/*.puml)
if [[ -f smoke_c4.puml ]]; then
  paths+=(smoke_c4.puml)
fi
if [[ ${#paths[@]} -eq 0 ]]; then
  echo "Не найдено ни одного .puml в ${C4}/diagrams" >&2
  exit 1
fi

echo "Рендер в ${C4}/out (${fmt})..."
docker run --rm \
  -v "${C4}:/work" \
  -w /work \
  plantuml/plantuml:latest \
  -charset UTF-8 \
  -DRELATIVE_INCLUDE=1 \
  -o out \
  "${flag}" \
  "${paths[@]}"

echo "Готово: ${C4}/out/"
