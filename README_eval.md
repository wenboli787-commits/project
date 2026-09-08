# Unitree G1 重定向质量评估工具

这套工具用于比较三种人类动作到 Unitree G1 机器人动作重定向方法：

- Direct Mapping
- Basic IK
- GMR

它会读取原始动作 `.npz/.npy/.bvh` 和三种方法生成的 `.pkl`，自动匹配动作名，计算成功率、全局关键点误差、root-relative 误差、骨骼方向角误差、脚滑、穿地、自碰撞、关节速度/加速度/jerk 突变和综合评分，并输出 CSV、JSON、PNG 图和 Markdown/HTML 报告。

## 依赖安装

建议在 Ubuntu/WSL 的项目根目录中安装：

```bash
pip install numpy pandas matplotlib pyyaml tqdm mujoco plotly
```

最低运行依赖是 `numpy`。如果没有 `mujoco`，程序仍会运行，但无法从 `qpos` 做机器人 FK，因此 body/keypoint、contact、自碰撞等指标会显示为 `NaN` 或 unavailable。如果没有 `matplotlib`，会生成简化 PNG，安装后会生成正式图表。

## 一条命令运行

```bash
cd /mnt/d/GMR_WORK
python tools/evaluate_retargeting_quality.py \
  --original_dir "/mnt/d/GMR_WORK/final use mode" \
  --direct_dir "/mnt/d/GMR_WORK/GMR/outputs/final product/pkl direct" \
  --ik_dir "/mnt/d/GMR_WORK/GMR/outputs/final product/pkl Basic IK" \
  --gmr_dir "/mnt/d/GMR_WORK/GMR/outputs/final product/pkl" \
  --robot_xml "/mnt/d/GMR_WORK/GMR/assets/unitree_g1/g1_mocap_29dof.xml" \
  --config "configs/eval_mapping_unitree_g1.yaml" \
  --output_dir "/mnt/d/GMR_WORK/GMR/outputs/evaluation_results"
```

如果你的 Basic IK 文件夹叫 `pkl ik`，把 `--ik_dir` 改成对应路径即可。也可以只传其中一种或两种方法；不存在的方法目录会被跳过并写入 `missing_files.csv`。

## 输出结构

```text
evaluation_results/
├── summary_metrics.csv
├── per_motion_metrics.csv
├── per_keypoint_error.csv
├── per_joint_jump_stats.csv
├── self_collision_pairs.csv
├── missing_files.csv
├── user_study_template.csv
├── quality_raw_summary.json
├── report.md
├── report.html
└── figures/
    ├── success_rate_bar.png
    ├── global_error_bar.png
    ├── root_relative_error_bar.png
    ├── foot_sliding_bar.png
    ├── ground_penetration_bar.png
    ├── self_collision_bar.png
    ├── sudden_jumps_bar.png
    ├── per_motion_metrics_line.png
    ├── overall_score_heatmap.png
    ├── overall_radar.png
    └── keypoint_error_heatmap.png
```

## 主要表格怎么看

- `summary_metrics.csv`: 每种方法的平均结果。论文里比较三种方法时优先看这个表。
- `per_motion_metrics.csv`: 每个动作、每种方法一行，包含所有原始指标和 `overall_score`。
- `per_keypoint_error.csv`: pelvis、torso、head、hands、knees、feet 等关键点误差，适合分析“手部差还是脚部差”。
- `per_joint_jump_stats.csv`: 每段动作最容易突变的 Top 10 关节。
- `self_collision_pairs.csv`: MuJoCo contact 可用时统计最常自碰撞的 body pair。
- `user_study_template.csv`: 后续看视频人工打分用。
- `report.md/html`: 自动总结整体最好方法、每个动作最好/最差方法、缺失文件、不可计算指标和展示建议。

## 指标说明

- `success_rate`: 成功动作数量 / 总动作数量。默认失败条件包括提前中断、root 高度过低、roll/pitch 过大、严重穿地、严重自碰撞或 PKL 中已有 fall/terminate/done 状态。
- `raw_global_error_mm`: 不做 root/heading 对齐的全局关键点误差。
- `aligned_global_error_mm`: 初始 root 和 heading 对齐后的全局关键点误差。
- `root_relative_error_mm`: 去掉 root 平移后的身体结构误差。
- `bone_orientation_error_deg`: 没有一一对应机器人参考关节角时的骨骼方向角误差，不能当成真实 joint angle error。
- `total_foot_sliding_m`: 接触地面期间双脚水平滑动距离。
- `max_ground_penetration_m`: 脚或 body 低于地面的最大深度。
- `self_collision_count`: MuJoCo contact 可用时的非相邻 body 自碰撞帧数。
- `sudden_jump_count`: 关节速度超过自适应阈值或绝对阈值的帧数。
- `overall_score`: 只用于辅助排序，不替代原始指标；权重在 `configs/eval_mapping_unitree_g1.yaml` 中修改。

## 注意事项

- 当前 AMASS/SMPL NPZ 如果只有 `trans/poses` 而没有显式 3D joints，本工具会用配置里的 canonical human offsets 生成近似关键点，并在报告里标注 warning。若要得到更严格的 MPBPE，请先导出 SMPL/SMPL-X joints 或 keypoints 到 NPZ。
- 如果机器人 PKL 只有 `root_pos/root_rot/dof_pos`，需要安装 `mujoco` 并提供正确 XML，工具才能做 FK 得到机器人 body/keypoint 轨迹。
- 默认动作匹配正则是 `^([0-9]+_[0-9]+)`，例如 `08_01_poses.npz` 会匹配 `08_01_unitree_g1_gmr.pkl`、`08_01_...direct...pkl`、`08_01_...basic_ik...pkl`。可用 `--name_regex` 修改。
