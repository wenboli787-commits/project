#!/usr/bin/env bash
set -euo pipefail

VENV_PATH="${VENV_PATH:-tracking/.venv_tracking}"
PYTHON_BIN="${VENV_PATH}/bin/python"
ROBOT="${ROBOT:-unitree_g1}"
MOTION_PATH="${MOTION_PATH:-outputs/dance1_subject2_unitree_g1.pkl}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "[smoke] Missing venv Python: ${PYTHON_BIN}" >&2
  echo "[smoke] Run: WITH_RL=1 bash tracking/scripts/setup_tracking_ubuntu22_04.sh" >&2
  exit 2
fi

echo "[smoke] Checking environment"
"${PYTHON_BIN}" tracking/scripts/check_tracking_env.py \
  --robot "${ROBOT}" \
  --motion_path "${MOTION_PATH}"

echo "[smoke] Diagnosing PD tracking"
"${PYTHON_BIN}" tracking/scripts/diagnose_tracking.py \
  --robot "${ROBOT}" \
  --robot_motion_path "${MOTION_PATH}" \
  --max_frames 20

echo "[smoke] Running PD tracking"
"${PYTHON_BIN}" tracking/scripts/run_pd_tracking.py \
  --robot "${ROBOT}" \
  --robot_motion_path "${MOTION_PATH}" \
  --max_frames 5 \
  --root_mode kinematic \
  --print_every 1

echo "[smoke] Running RL zero-action evaluation"
"${PYTHON_BIN}" tracking/scripts/eval_rl_tracking.py \
  --robot "${ROBOT}" \
  --robot_motion_path "${MOTION_PATH}" \
  --max_frames 5 \
  --root_mode kinematic

echo "[smoke] Running tiny PPO training"
"${PYTHON_BIN}" tracking/scripts/train_rl_tracking.py \
  --robot "${ROBOT}" \
  --robot_motion_path "${MOTION_PATH}" \
  --root_mode kinematic \
  --max_frames 10 \
  --total_timesteps 32 \
  --n_envs 1 \
  --n_steps 8 \
  --batch_size 8 \
  --save_path outputs/rl_tracking/smoke_test_ppo.zip

echo "[smoke] All smoke tests passed."
