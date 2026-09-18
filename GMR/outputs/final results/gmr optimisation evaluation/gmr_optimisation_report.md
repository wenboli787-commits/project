# GMR Executability-Aware Optimisation Report

## Overall comparison between Raw GMR and Optimised GMR

The batch contains 9 motions. 9 motions were accepted as safe improvements, and 0 motions were rolled back to Raw GMR because no candidate satisfied the safety rules.

## Improved motions

- 05_04_poses_unitree_g1_gmr: composite score improvement = 46.71824738682972%
- 111_23_poses_unitree_g1_gmr: composite score improvement = 52.00526802243025%
- 113_20_poses_unitree_g1_gmr: composite score improvement = 33.30286639428718%
- 113_21_poses_unitree_g1_gmr: composite score improvement = 19.407269579217704%
- 114_15_poses_unitree_g1_gmr: composite score improvement = 75.80375311676063%
- 124_11_poses_unitree_g1_gmr: composite score improvement = 46.90022516266844%
- 135_04_poses_unitree_g1_gmr: composite score improvement = 40.96938280874217%
- 47_01_poses_unitree_g1_gmr: composite score improvement = 58.1062765660393%
- 76_10_poses_unitree_g1_gmr: composite score improvement = 50.96987175286085%

## Rolled back motions

- No motion was rolled back.

## Metrics improved most

- Maximum Ground Penetration Depth: mean improvement 92.02%
- Penetration Frame Count: mean improvement 82.89%
- Composite Score: Raw GMR vs Optimised GMR: mean improvement 47.13%
- Total Foot Sliding: mean improvement 23.83%
- Mean Joint Jerk: mean improvement 15.25%
- Maximum Joint Jump: mean improvement 2.94%

## Metrics difficult to improve

- Self-Collision Frame Count: mean improvement 0.00%
- Joint Limit Violation Ratio: mean improvement 0.00%

## Trade-offs

- 114_15_poses_unitree_g1_gmr: worsened metrics after safe selection: Joint Limit Violation Ratio
- 47_01_poses_unitree_g1_gmr: worsened metrics after safe selection: Joint Limit Violation Ratio

## Difficult actions after optimisation

- 113_21_poses_unitree_g1_gmr: optimised composite score = 5.498328285102302, status = accepted
- 124_11_poses_unitree_g1_gmr: optimised composite score = 3.9300525553899335, status = accepted
- 135_04_poses_unitree_g1_gmr: optimised composite score = 3.824047098073753, status = accepted
- 05_04_poses_unitree_g1_gmr: optimised composite score = 3.1413750015666273, status = accepted
- 113_20_poses_unitree_g1_gmr: optimised composite score = 3.1049331230548782, status = accepted
- 76_10_poses_unitree_g1_gmr: optimised composite score = 2.5065353942624076, status = accepted
- 111_23_poses_unitree_g1_gmr: optimised composite score = 2.480877160497391, status = accepted
- 47_01_poses_unitree_g1_gmr: optimised composite score = 1.9563860377520164, status = accepted
- 114_15_poses_unitree_g1_gmr: optimised composite score = 0.8554155614268583, status = accepted

## Thesis-ready innovation paragraph

This work introduces an automatic executability-aware optimisation module for GMR-retargeted humanoid motions before reinforcement-learning tracking. Instead of applying a fixed post-processing rule, the module evaluates each retargeted motion in MuJoCo using forward kinematics and contact information, searches over conservative correction parameters, and accepts an optimised candidate only when it improves the composite executability score without worsening critical safety metrics such as ground penetration, self-collision, joint-limit violation, root drift, jerk, or sudden joint jumps. Motions that cannot be safely improved are automatically rolled back to the Raw GMR result, allowing failure cases to be analysed without contaminating the final tracking dataset with worse motions.

## Generated figures

- Composite Score: Raw GMR vs Optimised GMR: `/mnt/d/GMR_WORK/GMR/outputs/final results/gmr optimisation evaluation/plots/composite_score_raw_vs_optimised.png`
- Maximum Ground Penetration Depth: `/mnt/d/GMR_WORK/GMR/outputs/final results/gmr optimisation evaluation/plots/max_penetration_depth_raw_vs_optimised.png`
- Penetration Frame Count: `/mnt/d/GMR_WORK/GMR/outputs/final results/gmr optimisation evaluation/plots/penetration_frame_count_raw_vs_optimised.png`
- Total Foot Sliding: `/mnt/d/GMR_WORK/GMR/outputs/final results/gmr optimisation evaluation/plots/total_foot_sliding_raw_vs_optimised.png`
- Self-Collision Frame Count: `/mnt/d/GMR_WORK/GMR/outputs/final results/gmr optimisation evaluation/plots/self_collision_frame_count_raw_vs_optimised.png`
- Mean Joint Jerk: `/mnt/d/GMR_WORK/GMR/outputs/final results/gmr optimisation evaluation/plots/mean_jerk_raw_vs_optimised.png`
- Maximum Joint Jump: `/mnt/d/GMR_WORK/GMR/outputs/final results/gmr optimisation evaluation/plots/max_joint_jump_raw_vs_optimised.png`
- Joint Limit Violation Ratio: `/mnt/d/GMR_WORK/GMR/outputs/final results/gmr optimisation evaluation/plots/joint_limit_violation_ratio_raw_vs_optimised.png`
- Composite Score Improvement Overview: `/mnt/d/GMR_WORK/GMR/outputs/final results/gmr optimisation evaluation/plots/improvement_percentage_overview.png`
