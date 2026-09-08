from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np

from loaders.common_motion import MotionData, finite_difference
from .common import safe_max, safe_mean


def compute_smoothness(prediction: MotionData, config: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, np.ndarray], Dict[str, str]]:
    """Compute joint/keypoint jerk, frame jumps, collision, and playback FPS metrics."""
    n = prediction.num_frames
    summary: Dict[str, Any] = {}
    per_frame: Dict[str, np.ndarray] = {}
    unavailable: Dict[str, str] = {}
    dof = prediction.dof_pos if prediction.dof_pos is not None else (prediction.qpos[:, 7:] if prediction.qpos is not None and prediction.qpos.shape[1] > 7 else None)
    if dof is not None:
        vel = finite_difference(dof, prediction.fps)
        acc = finite_difference(vel, prediction.fps)
        jerk = finite_difference(acc, prediction.fps)
        per_frame["joint_jerk_per_frame"] = np.linalg.norm(jerk, axis=1)
        summary["joint_velocity_smoothness"] = 1.0 / (1.0 + safe_mean(np.linalg.norm(vel, axis=1)))
        summary["joint_acceleration_smoothness"] = 1.0 / (1.0 + safe_mean(np.linalg.norm(acc, axis=1)))
        summary["joint_jerk_mean"] = safe_mean(np.abs(jerk))
        summary["joint_jerk_max"] = safe_max(np.abs(jerk))
    else:
        for key in ["joint_velocity_smoothness", "joint_acceleration_smoothness", "joint_jerk_mean", "joint_jerk_max"]:
            summary[key] = np.nan
            unavailable[key] = "not_available: dof_pos/qpos missing"
        per_frame["joint_jerk_per_frame"] = np.full(n, np.nan)

    kp_jerks = []
    jumps = []
    for name in ["pelvis", "left_hand", "right_hand", "left_foot", "right_foot", "head"]:
        pos = prediction.get_keypoint(name)
        if pos is None:
            continue
        vel = finite_difference(pos, prediction.fps)
        acc = finite_difference(vel, prediction.fps)
        jerk = finite_difference(acc, prediction.fps)
        kp_jerks.append(np.linalg.norm(jerk, axis=1))
        jumps.append(np.concatenate([[0.0], np.linalg.norm(np.diff(pos, axis=0), axis=1)]))
    if kp_jerks:
        stack = np.stack(kp_jerks, axis=1)
        per_frame["keypoint_jerk_per_frame"] = np.nanmean(stack, axis=1)
        summary["keypoint_jerk_mean"] = safe_mean(stack)
        summary["keypoint_jerk_max"] = safe_max(stack)
    else:
        summary["keypoint_jerk_mean"] = np.nan
        summary["keypoint_jerk_max"] = np.nan
        unavailable["keypoint_jerk_mean"] = "not_available: keypoints missing"
        per_frame["keypoint_jerk_per_frame"] = np.full(n, np.nan)

    if jumps:
        jump = np.nanmax(np.stack(jumps, axis=1), axis=1)
        threshold = float(config.get("smoothness", {}).get("frame_jump_threshold", 0.5))
        summary["frame_jump_count"] = int(np.sum(jump > threshold))
        summary["frame_jump_rate"] = float(np.mean(jump > threshold))
        summary["max_frame_jump"] = safe_max(jump)
        per_frame["frame_jump_per_frame"] = jump
    else:
        for key in ["frame_jump_count", "frame_jump_rate", "max_frame_jump"]:
            summary[key] = np.nan
            unavailable[key] = "not_available: root/keypoints missing"
        per_frame["frame_jump_per_frame"] = np.full(n, np.nan)

    summary["self_collision_count"] = prediction.extra.get("self_collision_count", np.nan)
    summary["self_collision_rate"] = prediction.extra.get("self_collision_rate", np.nan)
    if not np.isfinite(float(summary["self_collision_rate"])) if summary["self_collision_rate"] is not None else True:
        unavailable["self_collision_rate"] = "not_available: MuJoCo FK/contact check unavailable"
    summary["simulation_fps_mean"] = prediction.extra.get("simulation_fps_mean", np.nan)
    summary["simulation_fps_min"] = prediction.extra.get("simulation_fps_min", np.nan)
    if not np.isfinite(float(summary["simulation_fps_mean"])) if summary["simulation_fps_mean"] is not None else True:
        unavailable["simulation_fps_mean"] = "not_available: no playback benchmark was run"
    return summary, per_frame, unavailable

