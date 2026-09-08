#!/usr/bin/env bash
# Ubuntu/Bash convenience entry point. It uses the active virtual environment.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python "${SCRIPT_DIR}/run_dummy_evaluation.py"
