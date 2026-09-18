# Fair Retargeting Evaluation Report

This report compares Direct Mapping, Basic IK, and GMR with the same original motions, Unitree G1 XML, target fps, semantic keypoint map, scale rule, root/yaw alignment rule, and thresholds.

Important: `kinematic_success_rate` is not dynamic tracking success. It only means the qpos file is complete enough and passes kinematic checks: qpos shape, joint limits, foot penetration, self-collision, base stability, and fall detection.

## Data and Configuration

- Original motion root: `D:/GMR_WORK/final use mode`
- Robot XML: `D:/GMR_WORK/GMR/assets/unitree_g1/g1_mocap_29dof.xml`
- XML-derived model_nq: `36`
- XML-derived robot leg length: `0.9215` m
- Target fps: `30.0`
- Human source reference: `source_body_pos/source_body_names` from the shared source-reference PKLs, not GMR robot output.

## Method Summary

|method|expected|evaluated|missing|kinematic_success_rate|pose_error_mm|bone_error_deg|ee_error_mm|foot_skating_m|penetration_m|self_collision_frames|joint_limit_frames|mean_jerk|
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
|Direct Mapping|9|9|0|0.000|306.939|62.175|361.810|10.130843|0.073289|245.778|139.111|522.260|
|Basic IK|9|9|0|0.000|249.059|48.873|241.106|7.808306|0.093796|112.333|0.000|145.399|
|GMR|9|9|0|0.444|170.213|36.687|138.910|4.468550|0.057114|20.000|0.000|676.867|

## Success / Failure / Missing

|method|success|failure|missing|kinematic_success_rate|
|---|---:|---:|---:|---:|
|Direct Mapping|0|9|0|0.000|
|Basic IK|0|9|0|0.000|
|GMR|4|5|0|0.444|

## Failure Reason Counts

|method|failure_reason|count|
|---|---|---:|
|Basic IK|severe_foot_penetration|6|
|Basic IK|severe_self_collision|9|
|Direct Mapping|joint_limit_violation|9|
|Direct Mapping|severe_foot_penetration|3|
|Direct Mapping|severe_self_collision|8|
|GMR|severe_foot_penetration|3|
|GMR|severe_self_collision|2|

## Category Winners

- Most similar to original motion: GMR (170.213)
- Least foot skating: GMR (4.469)
- Least foot penetration: GMR (0.057)
- Least self-collision: GMR (20.000)
- Least joint-limit violation: Basic IK / GMR (0.000)
- Smoothest motion by mean jerk: Basic IK (145.399)
- Highest kinematic_success_rate: GMR (0.444)

These are separate conclusions; no single overall score is used to declare a universal best method.

## Figures

- `/mnt/d/GMR_WORK/GMR/outputs/fair_method_evaluation/figures/root_relative_keypoint_error_mm_by_motion.png`
- `/mnt/d/GMR_WORK/GMR/outputs/fair_method_evaluation/figures/bone_direction_error_deg_by_motion.png`
- `/mnt/d/GMR_WORK/GMR/outputs/fair_method_evaluation/figures/end_effector_relative_error_mm_by_motion.png`
- `/mnt/d/GMR_WORK/GMR/outputs/fair_method_evaluation/figures/normalized_root_trajectory_error_by_motion.png`
- `/mnt/d/GMR_WORK/GMR/outputs/fair_method_evaluation/figures/foot_skating_distance_m_by_motion.png`
- `/mnt/d/GMR_WORK/GMR/outputs/fair_method_evaluation/figures/foot_penetration_max_m_by_motion.png`
- `/mnt/d/GMR_WORK/GMR/outputs/fair_method_evaluation/figures/self_collision_frames_by_motion.png`
- `/mnt/d/GMR_WORK/GMR/outputs/fair_method_evaluation/figures/joint_limit_violation_frames_by_motion.png`
- `/mnt/d/GMR_WORK/GMR/outputs/fair_method_evaluation/figures/mean_joint_jerk_rad_s3_by_motion.png`
- `/mnt/d/GMR_WORK/GMR/outputs/fair_method_evaluation/figures/kinematic_success_rate_by_method.png`

## Warnings

- Basic IK/smoke_follow_camera_basic_ik_pure: PKL exists but no matching original motion file was found; excluded from fair comparison.
