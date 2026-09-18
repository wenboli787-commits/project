# Retargeting Evaluation Results

## Input and matching summary

- Source motions found: 9
- Direct Mapping PKLs found: 9
- Basic IK PKLs found: 9
- GMR PKLs found: 9
- Complete three-method matches: 9
- Complete motion IDs: 05_04, 111_23, 113_20, 113_21, 114_15, 124_11, 135_04, 47_01, 76_10
- Incomplete/unmatched motion IDs: --
- Excluded result files: 0

## Success rates

- Direct Mapping: 0/9 (0.0%)
- Basic IK: 0/9 (0.0%)
- GMR: 0/9 (0.0%)

## Metric results

### Global MPBPE (m; lower is better)

- Direct Mapping mean=1.35704, median=1.46636; Basic IK mean=1.32522, median=1.36269; GMR mean=0.30767, median=0.304851
- Best mean: GMR
- GMR improvement versus Direct Mapping: 77.33%
- GMR improvement versus Basic IK: 76.78%

### Root-relative MPBPE (m; lower is better)

- Direct Mapping mean=0.910377, median=0.415431; Basic IK mean=0.567391, median=0.527859; GMR mean=0.328784, median=0.333574
- Best mean: GMR
- GMR improvement versus Direct Mapping: 63.88%
- GMR improvement versus Basic IK: 42.05%

### Scale-normalised position error (m; lower is better)

- Direct Mapping mean=0.748333, median=0.28881; Basic IK mean=0.340531, median=0.124678; GMR mean=0.15654, median=0.12425
- Best mean: GMR
- GMR improvement versus Direct Mapping: 79.08%
- GMR improvement versus Basic IK: 54.03%

### End-effector error (m; lower is better)

- Direct Mapping mean=0.794353, median=0.362302; Basic IK mean=0.332793, median=0.111558; GMR mean=0.158889, median=0.125546
- Best mean: GMR
- GMR improvement versus Direct Mapping: 80.00%
- GMR improvement versus Basic IK: 52.26%

### Body orientation error (deg; lower is better)

- Direct Mapping mean=13.1638, median=12.6341; Basic IK mean=51.7586, median=49.3453; GMR mean=6.03119, median=6.15841
- Best mean: GMR
- GMR improvement versus Direct Mapping: 54.18%
- GMR improvement versus Basic IK: 88.35%

### Root trajectory error (m; lower is better)

- Direct Mapping mean=0.217195, median=0.270847; Basic IK mean=0.235249, median=0.28148; GMR mean=0.183039, median=0.183188
- Best mean: GMR
- GMR improvement versus Direct Mapping: 15.73%
- GMR improvement versus Basic IK: 22.19%

### Foot sliding (m; lower is better)

- Direct Mapping mean=3.55637, median=2.44173; Basic IK mean=2.64675, median=2.02547; GMR mean=2.73081, median=1.80959
- Best mean: Basic IK
- GMR improvement versus Direct Mapping: 23.21%
- GMR improvement versus Basic IK: -3.18%

### Ground penetration (m; lower is better)

- Direct Mapping mean=0.0550467, median=0.0484863; Basic IK mean=0.0604323, median=0.0543411; GMR mean=0.0695836, median=0.0596024
- Best mean: Direct Mapping
- GMR improvement versus Direct Mapping: -26.41%
- GMR improvement versus Basic IK: -15.14%

### Self-collision ratio (ratio; lower is better)

- Direct Mapping mean=0.194677, median=0.0853659; Basic IK mean=0.605509, median=0.651246; GMR mean=0.028737, median=0
- Best mean: GMR
- GMR improvement versus Direct Mapping: 85.24%
- GMR improvement versus Basic IK: 95.25%

### Joint-limit violation ratio (ratio; lower is better)

- Direct Mapping mean=0.447083, median=0.393293; Basic IK mean=0.998645, median=1; GMR mean=0.00170004, median=0
- Best mean: GMR
- GMR improvement versus Direct Mapping: 99.62%
- GMR improvement versus Basic IK: 99.83%

### RMS joint jerk (rad/s^3; lower is better)

- Direct Mapping mean=236.213, median=202.428; Basic IK mean=1385.22, median=1264.75; GMR mean=267.494, median=230.667
- Best mean: Direct Mapping
- GMR improvement versus Direct Mapping: -13.24%
- GMR improvement versus Basic IK: 80.69%

### Discontinuity ratio (ratio; lower is better)

- Direct Mapping mean=0, median=0; Basic IK mean=0.0681195, median=0.0322581; GMR mean=0, median=0
- Best mean: Direct Mapping
- GMR improvement versus Direct Mapping: not_defined
- GMR improvement versus Basic IK: 100.00%

## Statistical tests

- global_body_position_error_mean, Friedman: all methods: corrected p=0.0009119, effect=0.778.
- global_body_position_error_mean, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- global_body_position_error_mean, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- scale_normalised_position_error_mean, Friedman: all methods: corrected p=0.004828, effect=0.593.
- scale_normalised_position_error_mean, direct_mapping vs basic_ik: corrected p=0.01562, effect=0.956.
- scale_normalised_position_error_mean, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- end_effector_error_mean, Friedman: all methods: corrected p=0.001139, effect=0.753.
- end_effector_error_mean, direct_mapping vs basic_ik: corrected p=0.01172, effect=1.000.
- end_effector_error_mean, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- body_orientation_error_mean, Friedman: all methods: corrected p=0.0001234, effect=1.000.
- body_orientation_error_mean, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- body_orientation_error_mean, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- body_orientation_error_mean, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- self_collision_frame_ratio, Friedman: all methods: corrected p=0.009494, effect=0.517.
- self_collision_frame_ratio, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- joint_limit_violation_ratio, Friedman: all methods: corrected p=0.0001234, effect=1.000.
- joint_limit_violation_ratio, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- joint_limit_violation_ratio, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- joint_limit_violation_ratio, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- rms_joint_jerk, Friedman: all methods: corrected p=0.0005847, effect=0.827.
- rms_joint_jerk, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- rms_joint_jerk, direct_mapping vs gmr: corrected p=0.03906, effect=-0.778.
- rms_joint_jerk, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- discontinuity_frame_ratio, Friedman: all methods: corrected p=0.0001234, effect=1.000.
- discontinuity_frame_ratio, direct_mapping vs basic_ik: corrected p=0.007812, effect=-1.000.
- discontinuity_frame_ratio, basic_ik vs gmr: corrected p=0.007812, effect=1.000.
- global_body_position_error_median, Friedman: all methods: corrected p=0.001139, effect=0.753.
- global_body_position_error_median, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- global_body_position_error_median, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- global_body_position_error_std, Friedman: all methods: corrected p=0.008415, effect=0.531.
- global_body_position_error_std, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- global_body_position_error_max, Friedman: all methods: corrected p=0.0001234, effect=1.000.
- global_body_position_error_max, direct_mapping vs basic_ik: corrected p=0.01172, effect=1.000.
- global_body_position_error_max, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- global_body_position_error_max, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- global_body_position_error_p95, Friedman: all methods: corrected p=0.0003002, effect=0.901.
- global_body_position_error_p95, direct_mapping vs basic_ik: corrected p=0.01172, effect=0.956.
- global_body_position_error_p95, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- global_body_position_error_p95, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- root_relative_position_error_std, Friedman: all methods: corrected p=0.04455, effect=0.346.
- root_relative_position_error_std, basic_ik vs gmr: corrected p=0.03516, effect=0.911.
- scale_normalised_position_error_median, Friedman: all methods: corrected p=0.004828, effect=0.593.
- scale_normalised_position_error_median, direct_mapping vs basic_ik: corrected p=0.03906, effect=0.867.
- scale_normalised_position_error_median, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- scale_normalised_position_error_std, Friedman: all methods: corrected p=0.004828, effect=0.593.
- scale_normalised_position_error_std, direct_mapping vs basic_ik: corrected p=0.01562, effect=0.956.
- scale_normalised_position_error_std, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- scale_normalised_position_error_max, Friedman: all methods: corrected p=0.004828, effect=0.593.
- scale_normalised_position_error_max, direct_mapping vs basic_ik: corrected p=0.01562, effect=0.956.
- scale_normalised_position_error_max, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- scale_normalised_position_error_p95, Friedman: all methods: corrected p=0.004828, effect=0.593.
- scale_normalised_position_error_p95, direct_mapping vs basic_ik: corrected p=0.01562, effect=0.956.
- scale_normalised_position_error_p95, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- end_effector_error_median, Friedman: all methods: corrected p=0.001139, effect=0.753.
- end_effector_error_median, direct_mapping vs basic_ik: corrected p=0.01172, effect=1.000.
- end_effector_error_median, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- end_effector_error_std, Friedman: all methods: corrected p=0.001139, effect=0.753.
- end_effector_error_std, direct_mapping vs basic_ik: corrected p=0.01172, effect=1.000.
- end_effector_error_std, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- end_effector_error_max, Friedman: all methods: corrected p=0.004828, effect=0.593.
- end_effector_error_max, direct_mapping vs basic_ik: corrected p=0.01562, effect=0.956.
- end_effector_error_max, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- end_effector_error_p95, Friedman: all methods: corrected p=0.001139, effect=0.753.
- end_effector_error_p95, direct_mapping vs basic_ik: corrected p=0.01172, effect=1.000.
- end_effector_error_p95, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- left_foot_end_effector_error_mean, Friedman: all methods: corrected p=0.001139, effect=0.753.
- left_foot_end_effector_error_mean, direct_mapping vs basic_ik: corrected p=0.01172, effect=1.000.
- left_foot_end_effector_error_mean, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- left_foot_end_effector_error_max, Friedman: all methods: corrected p=0.004828, effect=0.593.
- left_foot_end_effector_error_max, direct_mapping vs basic_ik: corrected p=0.01172, effect=1.000.
- left_foot_end_effector_error_max, direct_mapping vs gmr: corrected p=0.01562, effect=0.956.
- right_foot_end_effector_error_mean, Friedman: all methods: corrected p=0.004828, effect=0.593.
- right_foot_end_effector_error_mean, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- right_foot_end_effector_error_max, Friedman: all methods: corrected p=0.01639, effect=0.457.
- right_foot_end_effector_error_max, direct_mapping vs basic_ik: corrected p=0.03906, effect=0.867.
- right_foot_end_effector_error_max, direct_mapping vs gmr: corrected p=0.03516, effect=0.911.
- left_hand_end_effector_error_mean, Friedman: all methods: corrected p=0.001139, effect=0.753.
- left_hand_end_effector_error_mean, direct_mapping vs basic_ik: corrected p=0.01172, effect=1.000.
- left_hand_end_effector_error_mean, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- left_hand_end_effector_error_max, Friedman: all methods: corrected p=0.004828, effect=0.593.
- left_hand_end_effector_error_max, direct_mapping vs basic_ik: corrected p=0.01562, effect=0.956.
- left_hand_end_effector_error_max, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- right_hand_end_effector_error_mean, Friedman: all methods: corrected p=0.001139, effect=0.753.
- right_hand_end_effector_error_mean, direct_mapping vs basic_ik: corrected p=0.01172, effect=1.000.
- right_hand_end_effector_error_mean, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- right_hand_end_effector_error_max, Friedman: all methods: corrected p=0.004828, effect=0.593.
- right_hand_end_effector_error_max, direct_mapping vs basic_ik: corrected p=0.01562, effect=0.956.
- right_hand_end_effector_error_max, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- head_end_effector_error_mean, Friedman: all methods: corrected p=0.003096, effect=0.642.
- head_end_effector_error_mean, direct_mapping vs basic_ik: corrected p=0.03906, effect=0.867.
- head_end_effector_error_mean, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- head_end_effector_error_max, Friedman: all methods: corrected p=0.003096, effect=0.642.
- head_end_effector_error_max, direct_mapping vs basic_ik: corrected p=0.03906, effect=0.867.
- head_end_effector_error_max, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- root_vertical_position_error_mean, Friedman: all methods: corrected p=0.0005847, effect=0.827.
- root_vertical_position_error_mean, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- root_vertical_position_error_mean, direct_mapping vs gmr: corrected p=0.01172, effect=-1.000.
- root_vertical_position_error_mean, basic_ik vs gmr: corrected p=0.03906, effect=-0.778.
- motion_range_preservation_error_mean, Friedman: all methods: corrected p=0.01639, effect=0.457.
- motion_range_preservation_error_mean, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- body_orientation_error_median, Friedman: all methods: corrected p=0.0001234, effect=1.000.
- body_orientation_error_median, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- body_orientation_error_median, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- body_orientation_error_median, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- body_orientation_error_std, Friedman: all methods: corrected p=0.0001234, effect=1.000.
- body_orientation_error_std, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- body_orientation_error_std, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- body_orientation_error_std, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- body_orientation_error_max, Friedman: all methods: corrected p=0.0005847, effect=0.827.
- body_orientation_error_max, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- body_orientation_error_max, direct_mapping vs gmr: corrected p=0.01953, effect=0.867.
- body_orientation_error_max, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- body_orientation_error_p95, Friedman: all methods: corrected p=0.0003002, effect=0.901.
- body_orientation_error_p95, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- body_orientation_error_p95, direct_mapping vs gmr: corrected p=0.01172, effect=0.956.
- body_orientation_error_p95, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- mean_joint_velocity, Friedman: all methods: corrected p=0.0003002, effect=0.901.
- mean_joint_velocity, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- mean_joint_velocity, direct_mapping vs gmr: corrected p=0.01172, effect=-0.956.
- mean_joint_velocity, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- rms_joint_velocity, Friedman: all methods: corrected p=0.0003002, effect=0.901.
- rms_joint_velocity, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- rms_joint_velocity, direct_mapping vs gmr: corrected p=0.01172, effect=-0.956.
- rms_joint_velocity, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- maximum_joint_velocity, Friedman: all methods: corrected p=0.0005847, effect=0.827.
- maximum_joint_velocity, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- maximum_joint_velocity, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- p95_joint_velocity, Friedman: all methods: corrected p=0.0005847, effect=0.827.
- p95_joint_velocity, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- p95_joint_velocity, direct_mapping vs gmr: corrected p=0.01953, effect=-0.867.
- p95_joint_velocity, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- mean_joint_acceleration, Friedman: all methods: corrected p=0.0003002, effect=0.901.
- mean_joint_acceleration, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- mean_joint_acceleration, direct_mapping vs gmr: corrected p=0.01953, effect=-0.867.
- mean_joint_acceleration, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- rms_joint_acceleration, Friedman: all methods: corrected p=0.0003002, effect=0.901.
- rms_joint_acceleration, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- rms_joint_acceleration, direct_mapping vs gmr: corrected p=0.01172, effect=-0.911.
- rms_joint_acceleration, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- maximum_joint_acceleration, Friedman: all methods: corrected p=0.0005847, effect=0.827.
- maximum_joint_acceleration, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- maximum_joint_acceleration, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- p95_joint_acceleration, Friedman: all methods: corrected p=0.0005847, effect=0.827.
- p95_joint_acceleration, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- p95_joint_acceleration, direct_mapping vs gmr: corrected p=0.01953, effect=-0.867.
- p95_joint_acceleration, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- mean_joint_jerk, Friedman: all methods: corrected p=0.0005847, effect=0.827.
- mean_joint_jerk, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- mean_joint_jerk, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- maximum_joint_jerk, Friedman: all methods: corrected p=0.001139, effect=0.753.
- maximum_joint_jerk, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- maximum_joint_jerk, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- p95_joint_jerk, Friedman: all methods: corrected p=0.0009119, effect=0.778.
- p95_joint_jerk, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- p95_joint_jerk, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- root_linear_velocity_rms, basic_ik vs gmr: corrected p=0.03516, effect=-0.911.
- root_angular_velocity_rms, Friedman: all methods: corrected p=0.00432, effect=0.605.
- root_angular_velocity_rms, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- root_angular_velocity_rms, direct_mapping vs gmr: corrected p=0.03906, effect=-0.778.
- root_angular_velocity_rms, basic_ik vs gmr: corrected p=0.03906, effect=0.867.
- root_angular_acceleration_rms, Friedman: all methods: corrected p=0.001776, effect=0.704.
- root_angular_acceleration_rms, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- root_angular_acceleration_rms, direct_mapping vs gmr: corrected p=0.03906, effect=-0.778.
- root_angular_acceleration_rms, basic_ik vs gmr: corrected p=0.02344, effect=0.911.
- root_angular_jerk, Friedman: all methods: corrected p=0.001776, effect=0.704.
- root_angular_jerk, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- root_angular_jerk, direct_mapping vs gmr: corrected p=0.03906, effect=-0.867.
- root_angular_jerk, basic_ik vs gmr: corrected p=0.03906, effect=0.867.
- discontinuity_count, Friedman: all methods: corrected p=0.0001234, effect=1.000.
- discontinuity_count, direct_mapping vs basic_ik: corrected p=0.007812, effect=-1.000.
- discontinuity_count, basic_ik vs gmr: corrected p=0.007812, effect=1.000.
- maximum_discontinuity, Friedman: all methods: corrected p=0.0009119, effect=0.778.
- maximum_discontinuity, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- maximum_discontinuity, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- first_discontinuity_frame, Friedman: all methods: corrected p=0.0001234, effect=1.000.
- first_discontinuity_frame, direct_mapping vs basic_ik: corrected p=0.007812, effect=-1.000.
- first_discontinuity_frame, basic_ik vs gmr: corrected p=0.007812, effect=1.000.
- worst_discontinuity_frame, Friedman: all methods: corrected p=0.01639, effect=0.457.
- worst_discontinuity_frame, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- mean_contact_sliding_velocity, Friedman: all methods: corrected p=0.01312, effect=0.481.
- mean_contact_sliding_velocity, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- right_foot_contact_duration, Friedman: all methods: corrected p=0.005336, effect=0.581.
- right_foot_contact_duration, direct_mapping vs basic_ik: corrected p=0.04688, effect=-0.929.
- right_foot_contact_duration, direct_mapping vs gmr: corrected p=0.04688, effect=-1.000.
- right_foot_contact_duration, basic_ik vs gmr: corrected p=0.04688, effect=-0.889.
- unexpected_ground_contact_count, Friedman: all methods: corrected p=0.01481, effect=0.468.
- penetration_frame_count, Friedman: all methods: corrected p=0.0006041, effect=0.824.
- penetration_frame_count, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- penetration_frame_count, direct_mapping vs gmr: corrected p=0.01172, effect=-1.000.
- penetration_frame_ratio, Friedman: all methods: corrected p=0.0006041, effect=0.824.
- penetration_frame_ratio, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- penetration_frame_ratio, direct_mapping vs gmr: corrected p=0.01172, effect=-1.000.
- mean_ground_penetration, Friedman: all methods: corrected p=0.004828, effect=0.593.
- mean_ground_penetration, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- mean_ground_penetration, direct_mapping vs gmr: corrected p=0.01562, effect=-0.956.
- self_collision_frame_count, Friedman: all methods: corrected p=0.009494, effect=0.517.
- self_collision_frame_count, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- total_self_contact_count, Friedman: all methods: corrected p=0.005361, effect=0.581.
- total_self_contact_count, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- maximum_contacts_in_one_frame, Friedman: all methods: corrected p=0.01885, effect=0.441.
- maximum_contacts_in_one_frame, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- maximum_self_penetration_depth, Friedman: all methods: corrected p=0.04194, effect=0.352.
- maximum_self_penetration_depth, basic_ik vs gmr: corrected p=0.02344, effect=0.956.
- joint_limit_violation_frame_count, Friedman: all methods: corrected p=0.0001234, effect=1.000.
- joint_limit_violation_frame_count, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- joint_limit_violation_frame_count, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- joint_limit_violation_frame_count, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- mean_joint_limit_violation, Friedman: all methods: corrected p=0.0001234, effect=1.000.
- mean_joint_limit_violation, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- mean_joint_limit_violation, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- mean_joint_limit_violation, basic_ik vs gmr: corrected p=0.01172, effect=1.000.
- maximum_joint_limit_violation, Friedman: all methods: corrected p=0.0001234, effect=1.000.
- maximum_joint_limit_violation, direct_mapping vs basic_ik: corrected p=0.01172, effect=-1.000.
- maximum_joint_limit_violation, direct_mapping vs gmr: corrected p=0.01172, effect=1.000.
- maximum_joint_limit_violation, basic_ik vs gmr: corrected p=0.01172, effect=1.000.

## Failures and unavailable metrics

- 05_04 / direct_mapping: severe_ground_penetration;long_ground_penetration;long_self_collision;joint_limit_violation
- 05_04 / basic_ik: long_ground_penetration;long_self_collision;joint_limit_violation;motion_discontinuity
- 05_04 / gmr: severe_ground_penetration;long_ground_penetration
- 111_23 / direct_mapping: long_ground_penetration;joint_limit_violation
- 111_23 / basic_ik: long_ground_penetration;long_self_collision;joint_limit_violation
- 111_23 / gmr: severe_ground_penetration;long_ground_penetration
- 113_20 / direct_mapping: joint_limit_violation
- 113_20 / basic_ik: long_ground_penetration;long_self_collision;joint_limit_violation
- 113_20 / gmr: severe_ground_penetration;long_ground_penetration
- 113_21 / direct_mapping: long_ground_penetration;joint_limit_violation
- 113_21 / basic_ik: long_ground_penetration;long_self_collision;joint_limit_violation
- 113_21 / gmr: severe_ground_penetration;long_ground_penetration
- 114_15 / direct_mapping: long_ground_penetration;long_self_collision;joint_limit_violation
- 114_15 / basic_ik: severe_ground_penetration;long_ground_penetration;long_self_collision;joint_limit_violation;motion_discontinuity
- 114_15 / gmr: severe_ground_penetration;long_ground_penetration
- 124_11 / direct_mapping: severe_ground_penetration;long_ground_penetration;joint_limit_violation
- 124_11 / basic_ik: severe_ground_penetration;long_ground_penetration;long_self_collision;joint_limit_violation;motion_discontinuity
- 124_11 / gmr: severe_ground_penetration;long_ground_penetration
- 135_04 / direct_mapping: severe_ground_penetration;long_ground_penetration;joint_limit_violation
- 135_04 / basic_ik: severe_ground_penetration;long_ground_penetration;long_self_collision;joint_limit_violation;motion_discontinuity
- 135_04 / gmr: long_ground_penetration
- 47_01 / direct_mapping: long_ground_penetration;long_self_collision;joint_limit_violation
- 47_01 / basic_ik: severe_ground_penetration;long_ground_penetration;long_self_collision;joint_limit_violation
- 47_01 / gmr: severe_ground_penetration;long_ground_penetration
- 76_10 / direct_mapping: long_ground_penetration;long_self_collision;joint_limit_violation
- 76_10 / basic_ik: severe_ground_penetration;long_ground_penetration;long_self_collision;joint_limit_violation;motion_discontinuity
- 76_10 / gmr: long_ground_penetration
- All configured metrics were available for evaluated motion-method rows.

## Current limitations

- Human-to-robot scale normalization uses one constant skeleton-height ratio per motion; no frame-wise scaling is allowed.
- Source body orientations depend on the project SMPL-X/BVH loader and may be unavailable for array-only sources without orientations.
- Contact metrics are kinematic MuJoCo geometry/contact checks; they do not evaluate PD or RL tracking, forces, balance, or torque feasibility.
- Statistical conclusions require at least the configured number of complete paired motions.
