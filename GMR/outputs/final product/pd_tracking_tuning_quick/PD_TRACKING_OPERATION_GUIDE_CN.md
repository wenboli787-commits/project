# GMR + PD Tracking 操作指南

## 单个动作调试

```bash
cd /mnt/d/GMR_WORK/GMR
python scripts/run_pd_tracking_from_gmr.py \
  --motion_pkl "outputs/final product/pkl/13_01_unitree_g1_gmr.pkl" \
  --xml_path "assets/unitree_g1/g1_mocap_29dof.xml" \
  --save_dir "outputs/final product/pkl PD tracking debug" \
  --mode pd \
  --root_mode free \
  --kp 100.0 \
  --kd 3.0 \
  --torque_clip 200.0 \
  --time_scale 1.5 \
  --smooth_ref \
  --smooth_window 5 \
  --target_blend 0.8 \
  --root_height_offset 0.08 \
  --extra_joint_damping 0.5 \
  --stop_on_fall
```

## 重新自动调参

```bash
cd /mnt/d/GMR_WORK/GMR
python scripts/tune_pd_tracking_from_gmr.py \
  --motion_dir "outputs/final product/pkl" \
  --xml_path "assets/unitree_g1/g1_mocap_29dof.xml" \
  --output_dir "outputs/final product/pd_tracking_tuning" \
  --save_best_video
```

## 注意事项

- `root_mode=kinematic` 通过不代表自由根动力学可执行，只说明关节映射和 PD 大致正常。
- `root_mode=free` 更真实，但简单 PD 没有上层平衡控制，G1 很容易摔倒。
- 本工作区的 `g1_mocap_29dof.xml` torque motor 默认 `ctrlrange="-1 1"`；调试 normalized actuator limit 时可以使用 `--ignore_actuator_ctrlrange`，但论文对比时应说明是否保留 XML 原始限制。
- 后续与 mjlab RL tracking 对比时，优先使用 `tracking_comparison_ready_summary.csv` 的标准字段。
