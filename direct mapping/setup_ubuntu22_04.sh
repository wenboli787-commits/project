#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="${1:-gmr}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GMR_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if ! command -v conda >/dev/null 2>&1; then
  echo "conda was not found. Please install Miniconda or Anaconda first."
  exit 1
fi

source "$(conda info --base)/etc/profile.d/conda.sh"

if ! conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  conda create -n "$ENV_NAME" python=3.10 -y
fi

conda activate "$ENV_NAME"
python -m pip install --upgrade pip
python -m pip install -e "$GMR_ROOT"
python -m pip install "qpsolvers[daqp,proxqp]" daqp
conda install -c conda-forge libstdcxx-ng -y

echo "Environment is ready for direct mapping."
echo "Use: conda activate $ENV_NAME"
