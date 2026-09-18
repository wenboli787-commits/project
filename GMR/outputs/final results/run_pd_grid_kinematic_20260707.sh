cd /mnt/d/GMR_WORK/GMR
OUT="outputs/final results/pd tracking pd_grid_kinematic_20260707"
mkdir -p "$OUT"
KPS=(90 100 110)
KDS=(4 5 6)
for KP in "${KPS[@]}"; do
  for KD in "${KDS[@]}"; do
    RUN_DIR="$OUT/kp_${KP}_kd_${KD}"
    if [ -f "$RUN_DIR/tracking_comparison_ready_summary.csv" ]; then
      echo "[skip] kinematic kp=$KP kd=$KD"
      continue
    fi
    mkdir -p "$RUN_DIR"
    echo "[run] kinematic kp=$KP kd=$KD"
    MUJOCO_GL=egl /home/ubuntu/miniconda3/envs/gmr/bin/python scripts/run_pd_tracking_from_gmr.py \
      --motion_dir "outputs/final results/pkl gmr" \
      --xml_path "assets/unitree_g1/g1_mocap_29dof.xml" \
      --save_dir "$RUN_DIR" \
      --mode pd \
      --root_mode kinematic \
      --kp "$KP" \
      --kd "$KD" \
      --torque_clip 250 \
      --time_scale 1.6 \
      --smooth_ref \
      --smooth_window 3 \
      --target_blend 0.7 \
      --root_height_offset 0.08 \
      --extra_joint_damping 0.7 \
      --sim_dt 0.002 > "$RUN_DIR.log" 2>&1 || true
  done
done
