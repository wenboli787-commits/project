# 人形机器人动作重定向评估报告

生成时间（UTC）：2026-06-24 08:54:00

## 本次输入

- Simulator：`offline`
- Reference：`D:\GMR_WORK\GMR\evaluate\examples\dummy_data\dummy_reference_motion.npz`
- Robot model：`None`
- Mapping：`D:\GMR_WORK\GMR\evaluate\config\eval_mapping_template.yaml`

`unavailable` 表示日志没有提供该指标所需的数据；它不是 0，也不代表通过。

## 方法总览

| Method | EE mean error (m) | Root mean error (m) | Contact F1 | Joint-limit frame ratio | Fall | Mean DOF jerk | Energy proxy | Tracking |
|---|---:|---:|---:|---:|---|---:|---:|---:|
| Direct Mapping | 0.18026 | 0.11328 | 0.67365 | 0.60556 | no | 120.95 | 604.77 | unavailable |
| Basic IK | 0.07001 | 0.016554 | 0.77344 | 0 | no | 120.95 | 604.55 | unavailable |
| GMR / Constrained IK | 0.02597 | 0.0090981 | 0.94523 | 0 | no | 120.95 | 604.49 | 0.05105 |

## 时间对齐与归一化

- **Direct Mapping**：{'reference_fps': 30.0, 'candidate_fps': 30.0, 'resampled': False, 'trimmed': False, 'evaluated_frames': 180, 'normalization': {'scale': 1.0245104341919553, 'root_aligned': True, 'heading_aligned': True}}
- **Basic IK**：{'reference_fps': 30.0, 'candidate_fps': 30.0, 'resampled': False, 'trimmed': False, 'evaluated_frames': 180, 'normalization': {'scale': 1.001814284071615, 'root_aligned': True, 'heading_aligned': True}}
- **GMR / Constrained IK**：{'reference_fps': 30.0, 'candidate_fps': 30.0, 'resampled': False, 'trimmed': False, 'evaluated_frames': 180, 'normalization': {'scale': 1.0014555533339113, 'root_aligned': True, 'heading_aligned': True}}

## 解读提示

- 末端、根轨迹和旋转误差用于比较动作相似度；它们要求 reference 与 robot landmark 在 YAML 中正确对应。
- Joint-limit、接触、穿透、平滑度和 effort 描述可执行性/动作质量；它们不直接等于动作像不像。
- Tracking error 只在同时存在 target 与 actual 轨迹时才有意义。仅有重定向 qpos 时会显示 `unavailable`。
- Locomotion success 的默认含义是未摔倒且位移达到 YAML 的 `min_forward_displacement`；非移动动作请据任务重写该规则。

## 输出文件

- `summary_metrics.json`：完整的嵌套指标，保留 unavailable 状态。
- `summary_metrics.csv`：适合 Excel 对比的扁平表。
- `per_frame_metrics.csv`：每帧误差、接触、穿透等序列。
- `plots/`：图表。

生成图表：`plots/method_comparison.png`, `plots/root_xy_trajectory.png`, `plots/per_frame_position_errors.png`

## Warnings

- 无。
