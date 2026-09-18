# Core Retargeting Metrics Report

Best method by overall score: **GMR Optimised**

## Method Summary

| method | motion_count | kinematic_success_rate | overall_score | mpjpe_mean | end_effector_error_mean | joint_limit_violation_rate | joint_limit_violation_frames | foot_penetration_mean | self_collision_frames | foot_sliding_total | root_height_error_against_reference | joint_jerk_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Direct Mapping | 9 | 0 | 56.42 | 1.007 | 1.045 | 0.02369 | 141.3 | 0.007875 | 95.89 | 3.336 | 0.793 | 948.1 |
| Basic IK | 9 | 0 | 55.36 | 0.1334 | 0.1665 | 0.194 | 320.4 | 0.02741 | 281.3 | 5.16 | 0.7368 | 4733 |
| GMR | 9 | 0.3333 | 73.31 | 0.2403 | 0.2581 | 0 | 0 | 0.03029 | 20.33 | 5.909 | 0.7371 | 1066 |
| GMR Optimised | 9 | 0.2222 | 73.76 | 0.2423 | 0.261 | 5.668e-05 | 0.5556 | 0.001192 | 20.33 | 0.1591 | 0.7998 | 1004 |

## Per Motion Results

| motion_id | method | kinematic_success | overall_score | failed_reason | mpjpe_mean | end_effector_error_mean | foot_penetration_mean | self_collision_frames | joint_limit_violation_frames | joint_limit_violation_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 05_04 | Direct Mapping | 0 | 54.88 | joint_limit_violation;severe_self_collision | 0.9519 | 1.013 | 0.007302 | 147 | 215 | 0.05552 |
| 05_04 | Basic IK | 0 | 56.16 | body_tilt_too_large;joint_limit_violation;severe_self_collision;fall_like | 0.1026 | 0.1297 | 0.02128 | 127 | 300 | 0.2153 |
| 05_04 | GMR | 1 | 89.29 |  | 0.1743 | 0.1931 | 0.01587 | 8 | 0 | 0 |
| 05_04 | GMR Optimised | 1 | 87.69 |  | 0.1743 | 0.1931 | 0 | 8 | 0 | 0 |
| 111_23 | Direct Mapping | 0 | 59.56 | joint_limit_violation;severe_self_collision | 0.5946 | 0.5951 | 0.004085 | 64 | 218 | 0.03424 |
| 111_23 | Basic IK | 0 | 51.72 | body_tilt_too_large;joint_limit_violation;severe_self_collision;fall_like | 0.1236 | 0.1553 | 0.03072 | 283 | 283 | 0.2024 |
| 111_23 | GMR | 0 | 63.01 | severe_self_collision | 0.3271 | 0.3436 | 0.0304 | 26 | 0 | 0 |
| 111_23 | GMR Optimised | 0 | 68.41 | severe_self_collision | 0.3294 | 0.3467 | 0 | 26 | 0 | 0 |
| 113_20 | Direct Mapping | 0 | 40.38 | joint_limit_violation | 2.52 | 2.538 | 0.000678 | 2 | 46 | 0.006192 |
| 113_20 | Basic IK | 0 | 55.41 | body_tilt_too_large;foot_penetration_too_large;joint_limit_violation;severe_self_collision;fall_like | 0.1429 | 0.1765 | 0.0404 | 362 | 362 | 0.1886 |
| 113_20 | GMR | 0 | 66.18 | foot_penetration_too_large;severe_self_collision | 0.2815 | 0.2924 | 0.03626 | 69 | 0 | 0 |
| 113_20 | GMR Optimised | 0 | 71.04 | severe_self_collision | 0.2893 | 0.3042 | 0.00213 | 69 | 0 | 0 |
| 113_21 | Direct Mapping | 0 | 67.63 | joint_limit_violation;severe_self_collision | 0.1946 | 0.2492 | 0.01043 | 109 | 69 | 0.006957 |
| 113_21 | Basic IK | 0 | 58.49 | body_tilt_too_large;foot_penetration_too_large;joint_limit_violation;severe_self_collision;fall_like | 0.07503 | 0.125 | 0.08825 | 342 | 342 | 0.1544 |
| 113_21 | GMR | 0 | 67.26 | foot_penetration_too_large;severe_self_collision | 0.113 | 0.1377 | 0.08091 | 33 | 0 | 0 |
| 113_21 | GMR Optimised | 0 | 70.7 | severe_self_collision | 0.1129 | 0.1378 | 0.008137 | 33 | 0 | 0 |
| 114_15 | Direct Mapping | 0 | 52.66 | joint_limit_violation;severe_self_collision | 1.37 | 1.373 | 0.00126 | 237 | 282 | 0.03448 |
| 114_15 | Basic IK | 0 | 53.69 | body_tilt_too_large;joint_limit_violation;severe_self_collision;fall_like | 0.08378 | 0.1174 | 0.02019 | 346 | 346 | 0.2191 |
| 114_15 | GMR | 1 | 87.48 |  | 0.1463 | 0.1634 | 0.01992 | 0 | 0 | 0 |
| 114_15 | GMR Optimised | 0 | 72.08 | joint_limit_violation | 0.1456 | 0.1614 | 0 | 0 | 3 | 0.0002999 |
| 124_11 | Direct Mapping | 0 | 62.51 | foot_penetration_too_large;joint_limit_violation | 0.4188 | 0.4865 | 0.01404 | 17 | 62 | 0.01807 |
| 124_11 | Basic IK | 0 | 52.31 | body_tilt_too_large;joint_limit_violation;severe_self_collision;fall_like | 0.2189 | 0.2457 | 0.01479 | 179 | 250 | 0.1643 |
| 124_11 | GMR | 0 | 65.48 | severe_self_collision | 0.3938 | 0.4084 | 0.01931 | 23 | 0 | 0 |
| 124_11 | GMR Optimised | 0 | 65.17 | severe_self_collision | 0.3973 | 0.4131 | 0 | 23 | 0 | 0 |
| 135_04 | Direct Mapping | 0 | 45.32 | foot_penetration_too_large;joint_limit_violation;severe_self_collision | 1.733 | 1.769 | 0.02337 | 39 | 129 | 0.01991 |
| 135_04 | Basic IK | 0 | 48.93 | joint_limit_violation;severe_self_collision | 0.2474 | 0.281 | 0.005374 | 235 | 329 | 0.2639 |
| 135_04 | GMR | 1 | 87.46 |  | 0.3556 | 0.3754 | 0.01354 | 0 | 0 | 0 |
| 135_04 | GMR Optimised | 1 | 85.89 |  | 0.3563 | 0.3766 | 0 | 0 | 0 | 0 |
| 47_01 | Direct Mapping | 0 | 56.3 | joint_limit_violation;severe_self_collision | 1.133 | 1.181 | 0.001542 | 190 | 186 | 0.02633 |
| 47_01 | Basic IK | 0 | 51.51 | joint_limit_violation;severe_self_collision | 0.149 | 0.1791 | 0.02347 | 316 | 330 | 0.183 |
| 47_01 | GMR | 0 | 60.65 | foot_penetration_too_large | 0.2378 | 0.2574 | 0.04262 | 3 | 0 | 0 |
| 47_01 | GMR Optimised | 0 | 71.09 | joint_limit_violation | 0.2423 | 0.2642 | 0.0004654 | 3 | 2 | 0.0002103 |
| 76_10 | Direct Mapping | 0 | 68.5 | joint_limit_violation;severe_self_collision | 0.1489 | 0.1983 | 0.008173 | 58 | 65 | 0.01149 |
| 76_10 | Basic IK | 0 | 70.06 | body_tilt_too_large;joint_limit_violation;severe_self_collision;fall_like | 0.05728 | 0.08907 | 0.002186 | 342 | 342 | 0.155 |
| 76_10 | GMR | 0 | 73.01 | severe_self_collision | 0.1331 | 0.1518 | 0.01375 | 21 | 0 | 0 |
| 76_10 | GMR Optimised | 0 | 71.77 | severe_self_collision | 0.1331 | 0.1518 | 0 | 21 | 0 | 0 |

## Missing Files

No missing files.

## Warnings

- 05_04: NPZ appears to be AMASS/SMPL-style and has poses/trans but no joints/keypoints; SMPL model is required to compute human keypoints. The evaluator will use shared source_body_pos from PKL files when available.
- 111_23: NPZ appears to be AMASS/SMPL-style and has poses/trans but no joints/keypoints; SMPL model is required to compute human keypoints. The evaluator will use shared source_body_pos from PKL files when available.
- 113_20: NPZ appears to be AMASS/SMPL-style and has poses/trans but no joints/keypoints; SMPL model is required to compute human keypoints. The evaluator will use shared source_body_pos from PKL files when available.
- 113_21: NPZ appears to be AMASS/SMPL-style and has poses/trans but no joints/keypoints; SMPL model is required to compute human keypoints. The evaluator will use shared source_body_pos from PKL files when available.
- 114_15: NPZ appears to be AMASS/SMPL-style and has poses/trans but no joints/keypoints; SMPL model is required to compute human keypoints. The evaluator will use shared source_body_pos from PKL files when available.
- 124_11: NPZ appears to be AMASS/SMPL-style and has poses/trans but no joints/keypoints; SMPL model is required to compute human keypoints. The evaluator will use shared source_body_pos from PKL files when available.
- 135_04: NPZ appears to be AMASS/SMPL-style and has poses/trans but no joints/keypoints; SMPL model is required to compute human keypoints. The evaluator will use shared source_body_pos from PKL files when available.
- 47_01: NPZ appears to be AMASS/SMPL-style and has poses/trans but no joints/keypoints; SMPL model is required to compute human keypoints. The evaluator will use shared source_body_pos from PKL files when available.
- 76_10: NPZ appears to be AMASS/SMPL-style and has poses/trans but no joints/keypoints; SMPL model is required to compute human keypoints. The evaluator will use shared source_body_pos from PKL files when available.

## Metric Interpretation

- `kinematic_success_rate`: qpos shape/finite values, completion, joint limits, foot penetration, self-collision, base height, and body tilt. It is not dynamic tracking success.
- `mpjpe_mean`: scale-normalized, root/yaw-aligned semantic keypoint error. Lower is better.
- `end_effector_error_mean`: mean error for left/right hands, left/right feet, and head. Lower is better.
- `joint_limit_violation_rate`: fraction of limited MuJoCo joints outside XML ranges. Lower is better.
- `foot_penetration_mean`: mean depth below ground based on MuJoCo foot geom lowest points when qpos/XML are available. Lower is better.
- `self_collision_frames`: frames with non-ground, non-adjacent MuJoCo contact pairs. Lower is better.
- `foot_sliding_total`: horizontal sliding while feet are near ground. Lower is better.
- `root_height_error_against_reference`: root height difference against reference keypoints when available. Lower is better.
- `joint_jerk_mean`: mean jerk from qpos joint coordinates. Lower is smoother.
- `overall_score`: weighted score from available normalized metrics only; unavailable metrics are not forced to zero.

## Important Fairness Notes

- The tool does not compare human joint angles directly with robot qpos.
- Similarity metrics use semantic keypoint trajectories after time alignment, root alignment, yaw alignment, and scale normalization.
- If original AMASS/SMPL NPZ files do not contain joints/keypoints, shared `source_body_pos` from PKL files is used as the human reference when available.
- Robot feasibility metrics are computed from robot qpos/body/foot/root data and the Unitree G1 MuJoCo XML.
