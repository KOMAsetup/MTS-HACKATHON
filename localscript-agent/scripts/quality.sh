#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
ruff check app scripts tests
ruff format --check app scripts tests
pytest tests/ -q
