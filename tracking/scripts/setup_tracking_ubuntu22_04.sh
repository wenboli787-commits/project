#!/usr/bin/env bash
set -euo pipefail

# Ubuntu 22.04 setup script for GMR PD/RL tracking.
#
# Common usage:
#   bash tracking/scripts/setup_tracking_ubuntu22_04.sh
#   WITH_RL=1 TORCH_DEVICE=cpu bash tracking/scripts/setup_tracking_ubuntu22_04.sh
#   WITH_RL=1 TORCH_DEVICE=cu121 bash tracking/scripts/setup_tracking_ubuntu22_04.sh
#
# Optional environment variables:
#   PYTHON_BIN=python3.10
#   VENV_PATH=tracking/.venv_tracking
#   WITH_RL=0|1
#   INSTALL_TORCH=auto|0|1
#   TORCH_DEVICE=cpu|cu118|cu121|cu124
#   INSTALL_VIEWER_DEPS=1|0
#   INSTALL_APT_DEPS=0|1
#   UPGRADE_TOOLS=0|1

PYTHON_BIN="${PYTHON_BIN:-python3.10}"
VENV_PATH="${VENV_PATH:-tracking/.venv_tracking}"
WITH_RL="${WITH_RL:-0}"
INSTALL_TORCH="${INSTALL_TORCH:-auto}"
TORCH_DEVICE="${TORCH_DEVICE:-cpu}"
INSTALL_VIEWER_DEPS="${INSTALL_VIEWER_DEPS:-1}"
INSTALL_APT_DEPS="${INSTALL_APT_DEPS:-0}"
UPGRADE_TOOLS="${UPGRADE_TOOLS:-0}"

export PIP_DISABLE_PIP_VERSION_CHECK=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRACKING_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

APT_PACKAGES=(
  python3.10
  python3.10-venv
  python3-pip
  build-essential
  git
  ffmpeg
  libgl1-mesa-glx
  libglfw3
  libosmesa6
  libegl1
  mesa-utils
)

if [[ "${INSTALL_APT_DEPS}" == "1" ]]; then
  echo "[setup] Installing Ubuntu apt dependencies. sudo may ask for your password."
  sudo apt-get update
  sudo apt-get install -y "${APT_PACKAGES[@]}"
else
  echo "[setup] Apt dependencies are not installed automatically."
  echo "[setup] If this is a fresh Ubuntu 22.04 machine, run:"
  echo "  sudo apt-get update"
  echo "  sudo apt-get install -y ${APT_PACKAGES[*]}"
fi

echo "[setup] Python executable:"
"${PYTHON_BIN}" -c 'import sys; print(sys.executable); print(sys.version)'

echo "[setup] Creating virtual environment at ${VENV_PATH}"
"${PYTHON_BIN}" -m venv "${VENV_PATH}"

VENV_PYTHON="${VENV_PATH}/bin/python"
VENV_PIP="${VENV_PYTHON} -m pip"

if [[ "${UPGRADE_TOOLS}" == "1" ]]; then
  echo "[setup] Upgrading pip/setuptools/wheel"
  ${VENV_PIP} install --upgrade pip setuptools wheel
fi

echo "[setup] Installing PD tracking dependencies"
${VENV_PIP} install -r "${TRACKING_ROOT}/requirements-pd.txt"

if [[ "${INSTALL_VIEWER_DEPS}" == "1" ]]; then
  echo "[setup] Installing GMR motion-viewer dependencies"
  ${VENV_PIP} install -r "${TRACKING_ROOT}/requirements-viewer.txt"
fi

install_torch() {
  local index_url
  case "${TORCH_DEVICE}" in
    cpu)
      index_url="https://download.pytorch.org/whl/cpu"
      ;;
    cu118|cu121|cu124)
      index_url="https://download.pytorch.org/whl/${TORCH_DEVICE}"
      ;;
    *)
      echo "[setup] Unsupported TORCH_DEVICE='${TORCH_DEVICE}'. Use cpu, cu118, cu121, or cu124." >&2
      exit 2
      ;;
  esac
  echo "[setup] Installing PyTorch from ${index_url}"
  ${VENV_PIP} install torch --index-url "${index_url}"
}

if [[ "${WITH_RL}" == "1" ]]; then
  if [[ "${INSTALL_TORCH}" == "1" ]]; then
    install_torch
  elif [[ "${INSTALL_TORCH}" == "auto" ]]; then
    if ! "${VENV_PYTHON}" -c 'import torch' >/dev/null 2>&1; then
      install_torch
    else
      echo "[setup] PyTorch already importable in the venv; skipping torch install."
    fi
  fi

  echo "[setup] Installing RL tracking dependencies"
  ${VENV_PIP} install -r "${TRACKING_ROOT}/requirements-rl.txt"
fi

cat <<EOF
[setup] Done.

Activate:
  source ${VENV_PATH}/bin/activate

Check:
  ${VENV_PYTHON} tracking/scripts/check_tracking_env.py

MuJoCo rendering hints:
  Desktop viewer:
    export MUJOCO_GL=glfw

  Headless server:
    export MUJOCO_GL=egl
    # If EGL is unavailable, try:
    # export MUJOCO_GL=osmesa
EOF
