# Core Retargeting Metrics Report

Best method by overall score: **GMR**

## Method Summary

| method | motion_count | kinematic_success_rate | overall_score | mpjpe_mean | end_effector_error_mean | joint_limit_violation_rate | joint_limit_violation_frames | foot_penetration_mean | self_collision_frames | foot_sliding_total | root_height_error_against_reference | joint_jerk_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Direct Mapping | 9 | 0 | 56.38 | 1.011 | 1.049 | 0.02369 | 141.3 | 0.007878 | 95.89 | 3.34 | 0.793 | 948.1 |
| Unrestricted IK | 9 | 0 | 55.49 | 0.1326 | 0.1657 | 0.194 | 320.4 | 0.02741 | 281.3 | 5.16 | 0.7369 | 4733 |
| GMR | 9 | 0.3333 | 73.41 | 0.2413 | 0.259 | 0 | 0 | 0.03029 | 20.33 | 5.909 | 0.7371 | 1066 |

## Per Motion Results

| motion_id | method | kinematic_success | overall_score | failed_reason | mpjpe_mean | end_effector_error_mean | foot_penetration_mean | self_collision_frames | joint_limit_violation_frames | joint_limit_violation_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 05_04 | Direct Mapping | 0 | 54.42 | joint_limit_violation;severe_self_collision | 0.9894 | 1.05 | 0.00732 | 147 | 215 | 0.05552 |
| 05_04 | Unrestricted IK | 0 | 56.36 | body_tilt_too_large;joint_limit_violation;severe_self_collision;fall_like | 0.09623 | 0.123 | 0.02128 | 127 | 300 | 0.2153 |
| 05_04 | GMR | 1 | 89.28 |  | 0.1852 | 0.2027 | 0.01587 | 8 | 0 | 0 |
| 111_23 | Direct Mapping | 0 | 59.53 | joint_limit_violation;severe_self_collision | 0.5942 | 0.5947 | 0.004085 | 64 | 218 | 0.03424 |
| 111_23 | Unrestricted IK | 0 | 51.78 | body_tilt_too_large;joint_limit_violation;severe_self_collision;fall_like | 0.1236 | 0.1553 | 0.03072 | 283 | 283 | 0.2024 |
| 111_23 | GMR | 0 | 63.04 | severe_self_collision | 0.3275 | 0.3439 | 0.0304 | 26 | 0 | 0 |
| 113_20 | Direct Mapping | 0 | 40.41 | joint_limit_violation | 2.521 | 2.539 | 0.000678 | 2 | 46 | 0.006192 |
| 113_20 | Unrestricted IK | 0 | 55.61 | body_tilt_too_large;foot_penetration_too_large;joint_limit_violation;severe_self_collision;fall_like | 0.1428 | 0.1764 | 0.0404 | 362 | 362 | 0.1886 |
| 113_20 | GMR | 0 | 66.32 | foot_penetration_too_large;severe_self_collision | 0.2814 | 0.2923 | 0.03626 | 69 | 0 | 0 |
| 113_21 | Direct Mapping | 0 | 67.65 | joint_limit_violation;severe_self_collision | 0.1946 | 0.2491 | 0.01044 | 109 | 69 | 0.006957 |
| 113_21 | Unrestricted IK | 0 | 58.75 | body_tilt_too_large;foot_penetration_too_large;joint_limit_violation;severe_self_collision;fall_like | 0.07486 | 0.1248 | 0.08825 | 342 | 342 | 0.1544 |
| 113_21 | GMR | 0 | 67.48 | foot_penetration_too_large;severe_self_collision | 0.1129 | 0.1376 | 0.08091 | 33 | 0 | 0 |
| 114_15 | Direct Mapping | 0 | 52.73 | joint_limit_violation;severe_self_collision | 1.367 | 1.37 | 0.00126 | 237 | 282 | 0.03448 |
| 114_15 | Unrestricted IK | 0 | 53.88 | body_tilt_too_large;joint_limit_violation;severe_self_collision;fall_like | 0.08234 | 0.1164 | 0.02019 | 346 | 346 | 0.2191 |
| 114_15 | GMR | 1 | 87.57 |  | 0.1443 | 0.1608 | 0.01992 | 0 | 0 | 0 |
| 124_11 | Direct Mapping | 0 | 62.5 | foot_penetration_too_large;joint_limit_violation | 0.4189 | 0.4866 | 0.01404 | 17 | 62 | 0.01807 |
| 124_11 | Unrestricted IK | 0 | 52.22 | body_tilt_too_large;joint_limit_violation;severe_self_collision;fall_like | 0.219 | 0.2458 | 0.01479 | 179 | 250 | 0.1643 |
| 124_11 | GMR | 0 | 65.56 | severe_self_collision | 0.3939 | 0.4085 | 0.01931 | 23 | 0 | 0 |
| 135_04 | Direct Mapping | 0 | 45.28 | foot_penetration_too_large;joint_limit_violation;severe_self_collision | 1.734 | 1.771 | 0.02337 | 39 | 129 | 0.01991 |
| 135_04 | Unrestricted IK | 0 | 48.94 | joint_limit_violation;severe_self_collision | 0.2472 | 0.2809 | 0.005374 | 235 | 329 | 0.2639 |
| 135_04 | GMR | 1 | 87.57 |  | 0.3553 | 0.3752 | 0.01354 | 0 | 0 | 0 |
| 47_01 | Direct Mapping | 0 | 56.35 | joint_limit_violation;severe_self_collision | 1.133 | 1.181 | 0.001542 | 190 | 186 | 0.02633 |
| 47_01 | Unrestricted IK | 0 | 51.42 | joint_limit_violation;severe_self_collision | 0.1491 | 0.1791 | 0.02347 | 316 | 330 | 0.183 |
| 47_01 | GMR | 0 | 60.62 | foot_penetration_too_large | 0.2378 | 0.2574 | 0.04262 | 3 | 0 | 0 |
| 76_10 | Direct Mapping | 0 | 68.54 | joint_limit_violation;severe_self_collision | 0.1491 | 0.1987 | 0.008172 | 58 | 65 | 0.01149 |
| 76_10 | Unrestricted IK | 0 | 70.45 | body_tilt_too_large;joint_limit_violation;severe_self_collision;fall_like | 0.05788 | 0.0899 | 0.002186 | 342 | 342 | 0.155 |
| 76_10 | GMR | 0 | 73.21 | severe_self_collision | 0.1336 | 0.1529 | 0.01375 | 21 | 0 | 0 |

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
