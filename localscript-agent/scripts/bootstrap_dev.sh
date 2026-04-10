#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v conda &>/dev/null; then
  echo "conda not found; install Miniconda/Mambaforge or use pip in a venv."
  exit 1
fi
conda env create -f environment.yml -y || conda env update -f environment.yml -y
echo "Run: conda activate localscript-agent"
