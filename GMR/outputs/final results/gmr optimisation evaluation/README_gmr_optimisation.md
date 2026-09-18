# Automatic Executability-Aware Optimisation for GMR Retargeted Motions

## 1. 研究目的

本模块用于在 RL tracking 之前，对 Raw GMR 生成的 humanoid robot motion pkl 进行自动可执行性分析与保守优化。目标不是简单做固定 post-processing，而是验证：

Can an automatic executability-aware optimisation module improve GMR-retargeted humanoid motions before tracking?

也就是说，系统会先用 MuJoCo forward kinematics 和 contact 信息重新评估 Raw GMR，再自动搜索候选优化参数，只有当候选结果在关键安全指标上不变差，并且 composite score 明确改善时，才保存 Optimised GMR。否则自动 rollback 到 Raw GMR 拷贝。

## 2. 为什么不是简单 smoothing

简单 smoothing、root height offset 或 foot lock 可能只改善一个局部指标，但会破坏其他指标。例如：

- smoothing 可能降低 jerk，但破坏 foot contact 或 root trajectory。
- root z 抬高可能减少 ground penetration，但可能造成 floating 或 tracking 变差。
- root xy foot lock 可能减少 foot sliding，但会增加 root drift、penetration 或 self-collision。
- joint clipping 可能减少 joint limit violation，但引入 sudden joint jumps。

本模块的核心区别是：每一个 candidate 都必须重新通过 MuJoCo `mj_forward` 评估，并经过 hard constraints、soft improvement requirement 和 composite score improvement 三层 safe selection。优化失败时不会保存更差结果。

## 3. 新增脚本

所有新增代码均位于：

`/mnt/d/GMR_WORK/GMR/scripts/mjlab_tools/`

| 脚本 | 作用 |
| --- | --- |
| `gmr_optimisation_core.py` | 共享核心模块，包含 pkl 字段识别、MuJoCo forward、指标计算、candidate 搜索、safe acceptance、pkl 保存更新。 |
| `inspect_gmr_pkl.py` | 检查 Raw GMR pkl 结构，输出所有 key、array shape/dtype/min/max/mean，并自动识别 qpos、dof_pos、root、body、fps 等字段。 |
| `evaluate_gmr_executability.py` | 对单个 Raw 或 Optimised pkl 进行可执行性评估，所有 body/geom/contact 指标均来自 MuJoCo forward 后的状态。 |
| `optimise_gmr_motion.py` | 单动作主优化器，自动生成 candidate 参数，评估每个 candidate，执行 safe selection 或 rollback。 |
| `run_batch_gmr_optimisation.sh` | 批量优化 Raw GMR pkl，并汇总所有 JSON report 为 `gmr_raw_vs_optimised_summary.csv`。 |
| `plot_gmr_optimisation_comparison.py` | 根据 summary CSV 生成 Raw vs Optimised 对比图和英文 markdown 报告。 |
| `run_batch_optimised_pkl_to_csv.sh` | 批量调用已有 `pkl_to_mjlab_csv.py`，把 optimised pkl 转换为 mjlab csv。 |

## 4. 评估指标含义

### Ground penetration

用于衡量机器人是否穿入地面。优先使用 MuJoCo contact 中 robot geom 与 floor/ground/plane geom 的 `contact.dist < 0`，penetration depth = `-contact.dist`。如果无法识别 ground geom，则使用 foot/body/geom 最低 z 值相对 `ground_z` 的深度估算。

输出包括：

- `max_penetration_depth`
- `mean_penetration_depth`
- `penetration_frame_count`
- `penetration_frame_ratio`
- `penetration_contact_count`
- `worst_penetration_frame`

### Foot sliding

用于衡量 stance foot 在接触地面时的 xy 漂移。contact frame 由 foot height 和 foot velocity 阈值共同判定。

输出包括：

- `left_foot_sliding`
- `right_foot_sliding`
- `total_foot_sliding`
- `contact_frame_count_left`
- `contact_frame_count_right`

### Self-collision

使用 MuJoCo contact 检测 robot geom 与 robot geom 的接触，排除 ground contact，并尽量排除相邻 body 的正常连接接触。

输出包括：

- `self_collision_contact_count`
- `self_collision_frame_count`
- `max_self_collision_penetration`
- `self_collision_frame_ratio`

### Smoothness

对 actuated joints 计算速度、加速度、jerk 和 sudden jump。对于 free joint qpos，默认跳过前 7 维 root qpos，不把 root x/y/z 平移作为主要 jerk 指标。

输出包括：

- `mean_joint_velocity`
- `max_joint_velocity`
- `mean_joint_acceleration`
- `max_joint_acceleration`
- `mean_jerk`
- `max_jerk`
- `max_joint_jump`

### Joint limit

从 MuJoCo XML 读取 limited hinge/slide joint range，只检测有 joint limit 的关节。

输出包括：

- `joint_limit_violation_count`
- `joint_limit_violation_ratio`
- `max_lower_violation`
- `max_upper_violation`
- `worst_joint_name`

### Root quality

用于检查 root height 和 root xy trajectory 是否异常。

输出包括：

- `root_z_min`
- `root_z_max`
- `root_z_mean`
- `root_z_std`
- `root_xy_path_length`
- `root_xy_drift`

### Composite score

`composite_score` 越低越好。当前实现保存每一项 subscore，便于论文中解释各指标权重。

形式为：

```text
score =
10.0 * max_penetration_depth
+ 2.0 * penetration_frame_ratio
+ 5.0 * total_foot_sliding
+ 5.0 * self_collision_frame_ratio
+ 2.0 * max_self_collision_penetration
+ 1.0 * mean_jerk_normalized
+ 1.0 * max_joint_jump_normalized
+ 3.0 * joint_limit_violation_ratio
+ 0.5 * root_xy_drift
```

## 5. Candidate optimisation 搜索

优化器不会只使用固定参数，而是结合：

- adaptive search：根据 Raw GMR 的主要问题优先尝试相关参数。
- coarse grid search：从代表性参数组合中抽样，最多不超过 `--max_candidates`。

搜索参数包括：

- `root_z_offset`
- `min_foot_clearance`
- `smoothing_window`
- `smoothing_strength`
- `foot_lock_strength`
- `root_xy_correction_strength`
- `joint_limit_margin`
- `contact_height_threshold`
- `contact_velocity_threshold`

具体操作包括：

- joint smoothing：优先使用 Savitzky-Golay filter，若 scipy 不可用则使用 numpy moving average。
- root height correction：基于 MuJoCo forward 后的 frame-wise minimum foot/geom height，生成平滑 correction curve，单帧 correction 不超过 0.08 m。
- foot sliding reduction：在 stance segment 中估计 foot xy drift，对 root xy 做保守平滑修正。
- joint limit check and optional clipping：默认只检测，不 clipping；只有 `--allow_joint_limit_clipping True` 时才允许 clipping。
- self-collision reduction：只使用 smoothing 和可选 clipping 等保守策略，不通过大幅移动 root 来硬修 self-collision。

## 6. Safe acceptance rules

候选结果必须满足 hard constraints：

1. `max_penetration_depth_post <= max_penetration_depth_raw + 0.002`
2. `self_collision_frame_count_post <= self_collision_frame_count_raw`
3. `joint_limit_violation_ratio_post <= joint_limit_violation_ratio_raw + 0.001`
4. `root_xy_drift_post <= root_xy_drift_raw + 0.10`
5. `mean_jerk_post <= mean_jerk_raw * 1.10`
6. `max_joint_jump_post <= max_joint_jump_raw * 1.10`

还必须满足 soft improvement requirement：

- 至少两个核心指标改善 10% 以上。

并且：

- `composite_score_post` 必须比 `composite_score_raw` 至少降低 5%。

任何 candidate 如果让关键安全指标变差，就不会被保存为最终结果。

## 7. Rollback 机制

如果没有任何 candidate 满足 safe acceptance rules：

- 不保存更差的优化结果。
- 输出 Raw GMR 的拷贝。
- 在 `optimisation_info` 和 report JSON 中写入：
  - `optimisation_status = "rollback_to_raw"`
  - `best_candidate_rejected_reason`
  - `no_safe_improvement_found`

这类动作可以在论文中作为 failure case analysis，而不是实验失败。

## 8. 输出文件

默认输出目录：

- Optimised pkl：`/mnt/d/GMR_WORK/GMR/outputs/final results/pkl gmr optimised`
- Evaluation/report：`/mnt/d/GMR_WORK/GMR/outputs/final results/gmr optimisation evaluation`
- Optimised mjlab csv：`/mnt/d/GMR_WORK/GMR/outputs/final results/mjlab csv optimised`

最终应生成：

1. optimised GMR pkl 文件
2. `gmr_raw_vs_optimised_summary.csv`
3. 每个动作的 optimisation report JSON
4. Raw GMR vs Optimised GMR 对比图
5. `gmr_optimisation_report.md`
6. `README_gmr_optimisation.md`
7. optimised GMR mjlab csv 文件

## 9. 论文写法建议

论文中可以把本模块定义为：

An automatic executability-aware optimisation module that evaluates GMR-retargeted humanoid motions in MuJoCo, searches conservative correction candidates, and safely accepts only those candidates that improve executability without worsening critical constraints.

建议在实验章节中只比较：

- Raw GMR
- Optimised GMR

不需要再加入 Direct Mapping、Basic IK 或多个手动 post-processing 版本。

对于 rollback 动作，可以作为 failure case analysis，说明某些动作虽然经过自动搜索，但无法在不破坏安全约束的情况下得到更好结果。

