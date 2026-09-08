from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np

from loaders.common_motion import MotionData
from .common import body_tilt_deg, safe_max, safe_mean, safe_min, safe_std


def compute_stability(reference: MotionData, prediction: MotionData, config: Dict[str, Any], contact_summary: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, np.ndarray], Dict[str, str]]:
    """Compute root height, tilt, COM proxy, and completion metrics."""
    n = min(reference.num_frames, prediction.num_frames)
    thresholds = config.get("stability", {})
    summary: Dict[str, Any] = {}
    per_frame: Dict[str, np.ndarray] = {}
    unavailable: Dict[str, str] = {}
    if prediction.root_pos is not None:
        h = prediction.root_pos[:n, 2]
        per_frame["root_height_per_frame"] = h
        summary["root_height_mean"] = safe_mean(h)
        summary["root_height_std"] = safe_std(h)
        summary["root_height_min"] = safe_min(h)
        summary["root_height_max"] = safe_max(h)
        if reference.root_pos is not None:
            summary["root_height_error_against_reference"] = safe_mean(np.abs(h - reference.root_pos[:n, 2]))
        else:
            summary["root_height_error_against_reference"] = np.nan
            unavailable["root_height_error_against_reference"] = "not_available: reference root_pos missing"
    else:
        for key in ["root_height_mean", "root_height_std", "root_height_min", "root_height_max", "root_height_error_against_reference"]:
            summary[key] = np.nan
            unavailable[key] = "not_available: prediction root_pos missing"
        per_frame["root_height_per_frame"] = np.full(n, np.nan)

    quat = prediction.get_quat("torso")
    if quat is None:
        quat = prediction.root_rot
    tilt = body_tilt_deg(quat)
    if tilt is not None:
        tilt = tilt[:n]
        per_frame["body_tilt_per_frame"] = tilt
        summary["body_tilt_mean_deg"] = safe_mean(tilt)
        summary["body_tilt_max_deg"] = safe_max(tilt)
        summary["body_tilt_std_deg"] = safe_std(tilt)
        fall_like = tilt > float(thresholds.get("fall_tilt_deg", 45.0))
        summary["fall_like_frames"] = int(np.sum(fall_like))
        summary["fall_like_rate"] = float(np.mean(fall_like))
    else:
        for key in ["body_tilt_mean_deg", "body_tilt_max_deg", "body_tilt_std_deg", "fall_like_frames", "fall_like_rate"]:
            summary[key] = np.nan
            unavailable[key] = "not_available: root/torso orientation missing"
        per_frame["body_tilt_per_frame"] = np.full(n, np.nan)

    com = prediction.extra.get("com")
    if com is not None:
        com = np.asarray(com, dtype=float)[:n]
        summary["com_height_mean"] = safe_mean(com[:, 2])
        summary["com_height_std"] = safe_std(com[:, 2])
        speed = np.concatenate([[0.0], np.linalg.norm(np.diff(com[:, :2], axis=0), axis=1) * prediction.fps])
        summary["com_horizontal_speed_mean"] = safe_mean(speed)
        summary["com_support_distance"] = np.nan
        unavailable["com_support_distance"] = "not_available: support polygon not available in offline logs"
    else:
        for key in ["com_height_mean", "com_height_std", "com_horizontal_speed_mean", "com_support_distance"]:
            summary[key] = np.nan
            unavailable[key] = "not_available: COM was not exported and MuJoCo mass COM aggregation is not enabled"

    min_root_height = float(thresholds.get("fall_root_height", 0.35))
    fall_by_height = bool(prediction.root_pos is not None and np.nanmin(prediction.root_pos[:n, 2]) < min_root_height)
    fall_by_tilt = bool(np.isfinite(summary.get("fall_like_rate", np.nan)) and summary["fall_like_rate"] > 0)
    severe_pen = bool(np.isfinite(contact_summary.get("foot_penetration_max", np.nan)) and contact_summary["foot_penetration_max"] > float(thresholds.get("max_penetration_for_success", 0.08)))
    short = prediction.num_frames < max(2, int(reference.num_frames * float(thresholds.get("min_completion_fraction", 0.9))))
    summary["fall_detected"] = bool(fall_by_height or fall_by_tilt)
    summary["episode_completed"] = bool(not summary["fall_detected"] and not severe_pen and not short)
    summary["completion_rate"] = float(min(prediction.num_frames / max(reference.num_frames, 1), 1.0))
    return summary, per_frame, unavailable
