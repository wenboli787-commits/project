from pathlib import Path
import pandas as pd

from retarget_core_eval.eval_core_metrics import choose_reference, evaluate_one, add_scores, aggregate_by_method, write_outputs
from retarget_core_eval.loaders.load_original import discover_original_files, load_original_motion
from retarget_core_eval.loaders.load_pkl import discover_pkl_files, load_pkl_motion
from retarget_core_eval.loaders.motion_data import EvalConfig

cfg = EvalConfig(
    original_root=Path('/mnt/d/GMR_WORK/use mode'),
    direct_pkl_root=Path('/mnt/d/GMR_WORK/GMR/outputs/final results/pkl direct'),
    ik_pkl_root=Path('/mnt/d/GMR_WORK/GMR/outputs/final results/pkl Basic IK'),
    gmr_pkl_root=Path('/mnt/d/GMR_WORK/GMR/outputs/final results/pkl gmr'),
    robot_xml=Path('/mnt/d/GMR_WORK/GMR/assets/unitree_g1/g1_mocap_29dof.xml'),
    output_dir=Path('/mnt/d/GMR_WORK/GMR/outputs/final results/four_method_eval'),
)
methods = {
    'Direct Mapping': cfg.direct_pkl_root,
    'Basic IK': cfg.ik_pkl_root,
    'GMR': cfg.gmr_pkl_root,
    'GMR Optimised': Path('/mnt/d/GMR_WORK/GMR/outputs/final results/pkl gmr optimised'),
}
originals = discover_original_files(cfg.original_root)
pkl_maps = {method: discover_pkl_files(root) for method, root in methods.items()}
all_motion_ids = sorted(originals)
per_motion_rows = []
frame_rows = []
missing_rows = []
raw = []
warnings = []

for method, pmap in pkl_maps.items():
    extra = sorted(set(pmap) - set(originals))
    for motion_id in extra:
        warnings.append(f'{method}/{motion_id}: PKL exists but no matching original motion file was found; excluded from comparison.')

for motion_id in all_motion_ids:
    original = load_original_motion(originals[motion_id])
    loaded = {}
    for method, pmap in pkl_maps.items():
        path = pmap.get(motion_id)
        if path is None:
            missing_rows.append({'motion_id': motion_id, 'method': method, 'missing': 'pkl', 'expected_root': str(methods[method])})
            continue
        try:
            loaded[method] = load_pkl_motion(path, method, cfg.robot_xml)
        except Exception as exc:
            missing_rows.append({'motion_id': motion_id, 'method': method, 'missing': 'load_failed', 'pkl_file': str(path), 'reason': str(exc)})
            warnings.append(f'{motion_id}/{method}: PKL load failed: {exc}')
    reference, ref_fps, reference_source = choose_reference(original, loaded, warnings)
    for method in methods:
        robot = loaded.get(method)
        if robot is None:
            continue
        row, frames, warn = evaluate_one(motion_id, method, original, robot, reference, ref_fps, reference_source, cfg)
        per_motion_rows.append(row)
        frame_rows.extend(frames)
        raw.append({'metrics': row, 'warnings': warn})
        warnings.extend(warn)

per_motion_df = pd.DataFrame(per_motion_rows)
if per_motion_df.empty:
    raise RuntimeError('No PKL rows evaluated. Check paths and filename matching.')
per_motion_df = add_scores(per_motion_df)
method_df = aggregate_by_method(per_motion_df)
frame_df = pd.DataFrame(frame_rows)
missing_df = pd.DataFrame(missing_rows, columns=['motion_id','method','missing','expected_root','pkl_file','reason'])
md_path, _ = write_outputs(cfg, per_motion_df, method_df, frame_df, missing_df, raw, warnings)

summary_cols = [
    'method','motion_count','success_count','failure_count','kinematic_success_rate','overall_score',
    'mpjpe_mean','end_effector_error_mean','bone_angle_error_mean','joint_limit_violation_frames',
    'self_collision_frames','foot_penetration_max','foot_penetration_mean','foot_sliding_total',
    'foot_skating_frames','fall_like_frames','joint_jerk_mean'
]
print('Four-method evaluation finished.')
print(f'Original motions: {len(all_motion_ids)}')
print(f'Evaluated rows: {len(per_motion_df)}')
print(f'Missing rows: {len(missing_df)}')
print(f'Output: {cfg.output_dir}')
print(f'Report: {md_path}')
print('\nMETHOD SUMMARY')
print(method_df[[c for c in summary_cols if c in method_df.columns]].to_string(index=False))
print('\nFAILURE REASONS')
print(per_motion_df.groupby(['method','failed_reason'], dropna=False).size().reset_index(name='count').to_string(index=False))
