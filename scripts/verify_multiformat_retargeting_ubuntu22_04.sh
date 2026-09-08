#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GMR_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$GMR_ROOT"

echo "[verify] GMR root: $GMR_ROOT"
echo "[verify] If dependencies are missing, run:"
echo "bash scripts/setup_multiformat_retargeting_ubuntu22_04.sh gmr"
echo

python scripts/verify_multiformat_retargeting.py "$@"
