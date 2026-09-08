#!/usr/bin/env bash
set -euo pipefail

source /home/ubuntu/miniconda3/etc/profile.d/conda.sh
conda activate gmr

GMR_ROOT="/mnt/d/GMR_WORK/GMR"
MOTION_ROOT="/mnt/d/GMR_WORK/final use mode"
DIRECT_OUT="${GMR_ROOT}/outputs/direct_mapping_scripts_final/pkl"
BASIC_OUT="${GMR_ROOT}/outputs/basic_ik_scripts_final/pkl"

mkdir -p "${DIRECT_OUT}" "${BASIC_OUT}"
cd "${GMR_ROOT}"

for motion in "${MOTION_ROOT}"/*_poses.npz; do
  stem="$(basename "${motion}" _poses.npz)"
  echo "[direct] ${stem}"
  python scripts/direct_motion_to_robot.py \
    --motion_file "${motion}" \
    --motion_format auto \
    --robot unitree_g1 \
    --no_visualize \
    --save_path "${DIRECT_OUT}/${stem}_unitree_g1_direct_mapping.pkl" \
    --quiet

  echo "[basic_ik] ${stem}"
  python scripts/basic_ik_motion_to_robot.py \
    --motion_file "${motion}" \
    --motion_format auto \
    --robot unitree_g1 \
    --no_visualize \
    --save_path "${BASIC_OUT}/${stem}_unitree_g1_basic_ik.pkl" \
    --quiet
done

cd /mnt/d/GMR_WORK/retarget_eval_toolkit
python eval_retargeting.py \
  --config configs/eval_config.yaml \
  --original_root "${MOTION_ROOT}" \
  --direct_pkl_root "${DIRECT_OUT}" \
  --ik_pkl_root "${BASIC_OUT}" \
  --gmr_pkl_root "${GMR_ROOT}/outputs/final product/pkl" \
  --robot_xml "${GMR_ROOT}/assets/unitree_g1/g1_mocap_29dof.xml" \
  --smplx_body_model_path "${GMR_ROOT}/assets/body_models" \
  --output_dir "/mnt/d/GMR_WORK/retarget_eval_toolkit/outputs/ubuntu_scripts_full_eval"

