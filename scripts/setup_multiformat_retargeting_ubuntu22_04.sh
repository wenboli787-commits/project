#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="${1:-gmr}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GMR_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "[setup] GMR root: $GMR_ROOT"
echo "[setup] Target conda env: $ENV_NAME"
echo
echo "[setup] If MuJoCo viewer fails to open later, install Ubuntu system packages:"
echo "sudo apt update"
echo "sudo apt install -y build-essential cmake git ffmpeg libgl1-mesa-dev libglfw3 libglfw3-dev libglew-dev libosmesa6-dev libx11-6 libxext6 libxrender1 libxi6 libxrandr2 libxinerama1 libxcursor1 patchelf"
echo

if ! command -v conda >/dev/null 2>&1; then
  echo "[setup] conda was not found. Install Miniconda or Anaconda first, then rerun this script."
  exit 1
fi

source "$(conda info --base)/etc/profile.d/conda.sh"

if ! conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  echo "[setup] Creating conda env: $ENV_NAME"
  conda create -n "$ENV_NAME" python=3.10 -y
fi

conda activate "$ENV_NAME"

echo "[setup] Installing Python dependencies..."
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e "$GMR_ROOT"
python -m pip install "qpsolvers[daqp,proxqp]" daqp
conda install -c conda-forge libstdcxx-ng -y

echo
echo "[setup] Import check:"
python - <<'PY'
import importlib.util

required = ["numpy", "scipy", "mujoco", "mink", "smplx", "qpsolvers", "daqp"]
for name in required:
    ok = importlib.util.find_spec(name) is not None
    print(f"  {name:10s}: {'OK' if ok else 'MISSING'}")
PY

echo
echo "[setup] Done."
echo "[setup] Next commands:"
echo "conda activate $ENV_NAME"
echo "cd \"$GMR_ROOT\""
echo "python scripts/motion_to_robot.py --check_paths_only"
