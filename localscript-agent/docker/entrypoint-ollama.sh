#!/bin/sh
set -e
MODEL="${OLLAMA_MODEL:-qwen2.5-coder:7b}"
ollama serve &
sleep 8
echo "Pulling model ${MODEL}..."
set +e
ollama pull "${MODEL}"
pull_rc=$?
set -e
if [ "$pull_rc" -ne 0 ]; then
  echo "WARN: ollama pull failed (exit ${pull_rc}). Tags may stay empty; run manually:" >&2
  echo "  docker exec -it <ollama-container> ollama pull ${MODEL}" >&2
fi
wait
