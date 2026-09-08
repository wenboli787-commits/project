# 人形机器人动作重定向评估报告

生成时间（UTC）：2026-06-24 08:54:26

## 本次输入

- Simulator：`mujoco`
- Reference：`D:\GMR_WORK\ubisoft-laforge-animation-dataset\lafan1\extracted\dance1_subject2.bvh`
- Robot model：`D:\GMR_WORK\GMR\assets\unitree_g1\g1_mocap_29dof.xml`
- Mapping：`D:\GMR_WORK\GMR\evaluate\config\eval_mapping_template.yaml`

`unavailable` 表示日志没有提供该指标所需的数据；它不是 0，也不代表通过。

## 方法总览

| Method | EE mean error (m) | Root mean error (m) | Contact F1 | Joint-limit frame ratio | Fall | Mean DOF jerk | Energy proxy | Tracking |
|---|---:|---:|---:|---:|---|---:|---:|---:|
| Direct Mapping | unavailable | unavailable | unavailable | 0 | no | 6.6969 | unavailable | unavailable |
| Basic IK | unavailable | unavailable | unavailable | 0 | no | 6.6969 | unavailable | unavailable |
| GMR / Constrained IK | unavailable | unavailable | unavailable | 0 | no | 6.6969 | unavailable | unavailable |

## 时间对齐与归一化

- **Direct Mapping**：{'reference_fps': 30.000300003000028, 'candidate_fps': 30.0, 'resampled': False, 'trimmed': True, 'fps_mismatch_without_resampling': True, 'evaluated_frames': 100, 'normalization': {'scale': 1.0, 'root_aligned': True, 'heading_aligned': False, 'scale_warning': 'unavailable: no usable height landmarks'}}
- **Basic IK**：{'reference_fps': 30.000300003000028, 'candidate_fps': 30.0, 'resampled': False, 'trimmed': True, 'fps_mismatch_without_resampling': True, 'evaluated_frames': 100, 'normalization': {'scale': 1.0, 'root_aligned': True, 'heading_aligned': False, 'scale_warning': 'unavailable: no usable height landmarks'}}
- **GMR / Constrained IK**：{'reference_fps': 30.000300003000028, 'candidate_fps': 30.0, 'resampled': False, 'trimmed': True, 'fps_mismatch_without_resampling': True, 'evaluated_frames': 100, 'normalization': {'scale': 1.0, 'root_aligned': True, 'heading_aligned': False, 'scale_warning': 'unavailable: no usable height landmarks'}}

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

## Warnings

- dance1_subject2_unitree_g1_direct_mapping: configured foot bodies were not found in the MuJoCo model; exact contacts skipped.
- dance1_subject2_unitree_g1_direct_mapping: no torque/ctrl or dof_vel; inverse-dynamics effort is unavailable.
- dance1_subject2_unitree_g1_direct_mapping: configured foot bodies were not found in the MuJoCo model; exact contacts skipped.
- dance1_subject2_unitree_g1_direct_mapping: no torque/ctrl or dof_vel; inverse-dynamics effort is unavailable.
- dance1_subject2_unitree_g1_direct_mapping: configured foot bodies were not found in the MuJoCo model; exact contacts skipped.
- dance1_subject2_unitree_g1_direct_mapping: no torque/ctrl or dof_vel; inverse-dynamics effort is unavailable.
