#!/usr/bin/env bash
# Quick environment check: Ollama tags, optional model presence, nvidia-smi.
set -euo pipefail
HOST="${OLLAMA_HOST:-http://127.0.0.1:11434}"
MODEL="${OLLAMA_MODEL:-qwen2.5-coder:7b}"

echo "Ollama host: $HOST"
if command -v curl >/dev/null 2>&1; then
  if curl -sfS "${HOST%/}/api/tags" >/dev/null; then
    echo "OK: GET /api/tags"
    if curl -sfS "${HOST%/}/api/tags" | grep -qF "$MODEL" 2>/dev/null; then
      echo "OK: model tag present: $MODEL"
    else
      echo "WARN: model not found in tags list (pull with: ollama pull $MODEL)"
    fi
  else
    echo "FAIL: cannot reach Ollama at $HOST"
    exit 1
  fi
else
  echo "SKIP: curl not installed"
fi

if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
else
  echo "SKIP: nvidia-smi not in PATH"
fi
