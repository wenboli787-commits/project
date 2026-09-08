from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np

from loaders.common_motion import MotionData
from .common import dtw_distance, keypoint_stack, quat_angle_deg, safe_max, safe_mean, safe_std, trajectory_length


def compute_motion_similarity(reference: MotionData, prediction: MotionData, config: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, np.ndarray], Dict[str, str]]:
    """Compute keypoint, end-effector, root, orientation, and trajectory errors."""
    names = list(config.get("evaluation", {}).get("compare_keypoints", [])) or [
        "pelvis", "head", "left_hand", "right_hand", "left_foot", "right_foot", "left_knee", "right_knee", "left_elbow", "right_elbow",
    ]
    n = min(reference.num_frames, prediction.num_frames)
    ref, _ = keypoint_stack(reference, names)
    pred, _ = keypoint_stack(prediction, names)
    ref = ref[:n]
    pred = pred[:n]
    diff = pred - ref
    dist = np.linalg.norm(diff, axis=2)
    valid = np.isfinite(dist)
    mpjpe_per_frame = np.divide(np.nansum(dist, axis=1), np.sum(valid, axis=1), out=np.full(n, np.nan), where=np.sum(valid, axis=1) > 0)
    summary: Dict[str, Any] = {
        "mpjpe_mean": safe_mean(mpjpe_per_frame),
        "mpjpe_std": safe_std(mpjpe_per_frame),
        "mpjpe_max": safe_max(mpjpe_per_frame),
        "available_keypoint_count": int(np.sum(np.any(valid, axis=0))),
    }
    per_frame = {"mpjpe_per_frame": mpjpe_per_frame}
    unavailable: Dict[str, str] = {}
    for i, name in enumerate(names):
        if not np.isfinite(dist[:, i]).any():
            summary[f"{name}_error"] = np.nan
            unavailable[f"{name}_error"] = "not_available: keypoint missing in reference or prediction"
        else:
            summary[f"{name}_error"] = safe_mean(dist[:, i])

    ee_names = ["left_hand", "right_hand", "left_foot", "right_foot", "head"]
    ee_values = [summary.get(f"{name}_error", np.nan) for name in ee_names]
    for name in ee_names:
        summary[f"{name}_error"] = summary.get(f"{name}_error", np.nan)
    summary["end_effector_error_mean"] = safe_mean(ee_values)

    if reference.root_pos is not None and prediction.root_pos is not None:
        root_delta = prediction.root_pos[:n] - reference.root_pos[:n]
        root_err = np.linalg.norm(root_delta, axis=1)
        per_frame["root_position_error_per_frame"] = root_err
        summary["root_position_error_mean"] = safe_mean(root_err)
        summary["root_position_error_max"] = safe_max(root_err)
        summary["root_horizontal_error"] = safe_mean(np.linalg.norm(root_delta[:, :2], axis=1))
        summary["root_height_error"] = safe_mean(np.abs(root_delta[:, 2]))
    else:
        for key in ["root_position_error_mean", "root_position_error_max", "root_horizontal_error", "root_height_error"]:
            summary[key] = np.nan
            unavailable[key] = "not_available: root_pos missing in reference or prediction"
        per_frame["root_position_error_per_frame"] = np.full(n, np.nan)

    root_ori = quat_angle_deg(reference.root_rot, prediction.root_rot, n)
    if root_ori is None:
        summary["root_orientation_error_deg"] = np.nan
        summary["base_orientation_error_deg"] = np.nan
        unavailable["root_orientation_error_deg"] = "not_available: root/base orientation missing"
        per_frame["root_orientation_error_per_frame"] = np.full(n, np.nan)
    else:
        summary["root_orientation_error_deg"] = safe_mean(root_ori)
        summary["base_orientation_error_deg"] = summary["root_orientation_error_deg"]
        per_frame["root_orientation_error_per_frame"] = root_ori

    ref_len = trajectory_length(reference.root_pos[:n] if reference.root_pos is not None else None)
    pred_len = trajectory_length(prediction.root_pos[:n] if prediction.root_pos is not None else None)
    summary["trajectory_length_human"] = ref_len
    summary["trajectory_length_robot"] = pred_len
    summary["trajectory_length_ratio"] = pred_len / ref_len if np.isfinite(ref_len) and abs(ref_len) > 1e-12 else np.nan
    summary["trajectory_dtw_distance"] = dtw_distance(reference.root_pos[:n] if reference.root_pos is not None else None, prediction.root_pos[:n] if prediction.root_pos is not None else None)
    return summary, per_frame, unavailable

