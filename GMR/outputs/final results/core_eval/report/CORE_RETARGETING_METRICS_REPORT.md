# Core Retargeting Metrics Report

Best method by overall score: **GMR**

## Method Summary

| method | motion_count | success_rate | overall_score | mpjpe_mean | end_effector_error_mean | joint_limit_violation_rate | foot_penetration_mean | foot_sliding_total | root_height_error_against_reference | joint_jerk_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Direct Mapping | 9 | 0.8889 | 74.09 | 1.016 | 1.062 | 0.02369 | 0.002939 | 3.646 | 0.793 | 948.1 |
| Unrestricted IK | 9 | 0.2222 | 57.8 | 0.4476 | 0.4942 | 0.194 | 0.01025 | 3.991 | 0.7369 | 4733 |
| GMR | 9 | 1 | 84.28 | 0.595 | 0.6343 | 5.854e-05 | 0.01041 | 4.712 | 0.7371 | 1066 |

## Per Motion Results

| motion_id | method | success | overall_score | failed_reason | mpjpe_mean | end_effector_error_mean | foot_penetration_mean | joint_limit_violation_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 05_04 | Direct Mapping | 1 | 75.52 |  | 1.02 | 1.109 | 0.001366 | 0.05552 |
| 05_04 | Unrestricted IK | 0 | 54.36 | body_tilt_too_large | 0.3728 | 0.431 | 0.00594 | 0.2153 |
| 05_04 | GMR | 1 | 87.15 |  | 0.5049 | 0.5626 | 0.002246 | 0.0002307 |
| 111_23 | Direct Mapping | 1 | 78.28 |  | 0.5889 | 0.5792 | 0.0003423 | 0.03424 |
| 111_23 | Unrestricted IK | 0 | 49.66 | body_tilt_too_large | 0.4953 | 0.533 | 0.008252 | 0.2024 |
| 111_23 | GMR | 1 | 80.81 |  | 0.7399 | 0.7718 | 0.005384 | 0 |
| 113_20 | Direct Mapping | 1 | 58.13 |  | 2.526 | 2.546 | 0 | 0.006192 |
| 113_20 | Unrestricted IK | 0 | 52.8 | body_tilt_too_large | 0.5246 | 0.5619 | 0.02078 | 0.1886 |
| 113_20 | GMR | 1 | 82.44 |  | 0.7149 | 0.7332 | 0.01873 | 0.000191 |
| 113_21 | Direct Mapping | 1 | 88.66 |  | 0.1874 | 0.2459 | 0.0009378 | 0.006957 |
| 113_21 | Unrestricted IK | 0 | 58.82 | body_tilt_too_large | 0.1515 | 0.2295 | 0.04911 | 0.1544 |
| 113_21 | GMR | 1 | 86.67 |  | 0.2098 | 0.2605 | 0.04641 | 0 |
| 114_15 | Direct Mapping | 1 | 71.23 |  | 1.378 | 1.381 | 4.904e-05 | 0.03448 |
| 114_15 | Unrestricted IK | 0 | 54.1 | body_tilt_too_large | 0.3423 | 0.3729 | 0.0006975 | 0.2191 |
| 114_15 | GMR | 1 | 85.67 |  | 0.4302 | 0.4517 | 0.002176 | 0 |
| 124_11 | Direct Mapping | 1 | 84.29 |  | 0.4388 | 0.5274 | 0.006068 | 0.01807 |
| 124_11 | Unrestricted IK | 0 | 48.16 | body_tilt_too_large | 0.7815 | 0.8198 | 0.001319 | 0.1643 |
| 124_11 | GMR | 1 | 80.79 |  | 1.019 | 1.061 | 0.004114 | 0 |
| 135_04 | Direct Mapping | 0 | 45.18 | foot_penetration_too_large | 1.714 | 1.758 | 0.01596 | 0.01991 |
| 135_04 | Unrestricted IK | 1 | 63.54 |  | 0.7686 | 0.8185 | 0 | 0.2639 |
| 135_04 | GMR | 1 | 82.46 |  | 0.9177 | 0.9636 | 0 | 0.0001051 |
| 47_01 | Direct Mapping | 1 | 76.04 |  | 1.14 | 1.207 | 0.0002274 | 0.02633 |
| 47_01 | Unrestricted IK | 1 | 68.11 |  | 0.4728 | 0.5128 | 0.00618 | 0.183 |
| 47_01 | GMR | 1 | 78.83 |  | 0.5833 | 0.6172 | 0.01462 | 0 |
| 76_10 | Direct Mapping | 1 | 89.43 |  | 0.1484 | 0.2055 | 0.001502 | 0.01149 |
| 76_10 | Unrestricted IK | 0 | 70.62 | body_tilt_too_large | 0.1189 | 0.1684 | 0 | 0.155 |
| 76_10 | GMR | 1 | 93.69 |  | 0.2351 | 0.2879 | 0 | 0 |

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

- `success_rate`: kinematic success rate based on completion, finite qpos, root height, body tilt, and foot penetration thresholds.
- `mpjpe_mean`: scale-normalized, root/yaw-aligned semantic keypoint error. Lower is better.
- `end_effector_error_mean`: mean error for left/right hands, left/right feet, and head. Lower is better.
- `joint_limit_violation_rate`: fraction of limited MuJoCo joints outside XML ranges. Lower is better.
- `foot_penetration_mean`: mean depth below ground. Lower is better.
- `foot_sliding_total`: horizontal sliding while feet are near ground. Lower is better.
- `root_height_error_against_reference`: root height difference against reference keypoints when available. Lower is better.
- `joint_jerk_mean`: mean jerk from qpos joint coordinates. Lower is smoother.
- `overall_score`: weighted score from available normalized metrics only; unavailable metrics are not forced to zero.

## Important Fairness Notes

- The tool does not compare human joint angles directly with robot qpos.
- Similarity metrics use semantic keypoint trajectories after time alignment, root alignment, yaw alignment, and scale normalization.
- If original AMASS/SMPL NPZ files do not contain joints/keypoints, shared `source_body_pos` from PKL files is used as the human reference when available.
- Robot feasibility metrics are computed from robot qpos/body/foot/root data and the Unitree G1 MuJoCo XML.
