#!/usr/bin/env bash
set -uo pipefail

source /home/ubuntu/miniconda3/etc/profile.d/conda.sh
conda activate gmr

GMR_ROOT="/mnt/d/GMR_WORK/GMR"
MOTION_ROOT="/mnt/d/GMR_WORK/final use mode"
DIRECT_OUT="${GMR_ROOT}/outputs/direct_mapping_scripts_rerun_latest/pkl"
BASIC_OUT="${GMR_ROOT}/outputs/basic_ik_scripts_rerun_latest/pkl"
EVAL_OUT="/mnt/d/GMR_WORK/retarget_eval_toolkit/outputs/ubuntu_scripts_rerun_latest"
LOG_DIR="${EVAL_OUT}/run_logs"
FAILED_LOG="${LOG_DIR}/generation_failures.txt"

mkdir -p "${DIRECT_OUT}" "${BASIC_OUT}" "${LOG_DIR}"
: > "${FAILED_LOG}"

cd "${GMR_ROOT}" || exit 1

for motion in "${MOTION_ROOT}"/*_poses.npz; do
  stem="$(basename "${motion}" _poses.npz)"

  echo "[direct] ${stem}"
  if ! python scripts/direct_motion_to_robot.py \
    --motion_file "${motion}" \
    --motion_format auto \
    --robot unitree_g1 \
    --no_visualize \
    --save_path "${DIRECT_OUT}/${stem}_unitree_g1_direct_mapping.pkl" \
    --quiet; then
    echo "direct_mapping,${stem},failed" | tee -a "${FAILED_LOG}"
  fi

  echo "[basic_ik] ${stem}"
  if ! python scripts/basic_ik_motion_to_robot.py \
    --motion_file "${motion}" \
    --motion_format auto \
    --robot unitree_g1 \
    --no_visualize \
    --save_path "${BASIC_OUT}/${stem}_unitree_g1_basic_ik.pkl" \
    --quiet; then
    echo "basic_ik,${stem},failed" | tee -a "${FAILED_LOG}"
  fi
done

cd /mnt/d/GMR_WORK/retarget_eval_toolkit || exit 1
python eval_retargeting.py \
  --config configs/eval_config.yaml \
  --original_root "${MOTION_ROOT}" \
  --direct_pkl_root "${DIRECT_OUT}" \
  --ik_pkl_root "${BASIC_OUT}" \
  --gmr_pkl_root "${GMR_ROOT}/outputs/final product/pkl" \
  --robot_xml "${GMR_ROOT}/assets/unitree_g1/g1_mocap_29dof.xml" \
  --smplx_body_model_path "${GMR_ROOT}/assets/body_models" \
  --output_dir "${EVAL_OUT}"
