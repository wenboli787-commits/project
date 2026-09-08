from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np

from loaders.common_motion import MotionData, finite_difference
from .common import safe_max, safe_mean, safe_std


def compute_kinematic_feasibility(motion: MotionData, config: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, np.ndarray], Dict[str, str]]:
    """Compute joint-limit, velocity, acceleration, and range-usage metrics."""
    n = motion.num_frames
    summary: Dict[str, Any] = {}
    per_frame: Dict[str, np.ndarray] = {}
    unavailable: Dict[str, str] = {}
    dof = motion.dof_pos if motion.dof_pos is not None else (motion.qpos[:, 7:] if motion.qpos is not None and motion.qpos.shape[1] > 7 else None)
    if dof is None:
        unavailable["dof_pos"] = "not_available: no robot qpos/dof_pos"
        for key in ["joint_limit_violation_count", "joint_limit_violation_rate", "joint_limit_violation_max_margin", "joint_range_usage_mean", "joint_range_usage_max"]:
            summary[key] = np.nan
        per_frame["joint_limit_violation_per_frame"] = np.full(n, np.nan)
        return summary, per_frame, unavailable

    dof = np.asarray(dof[:n], dtype=float)
    qvel = motion.qvel[:, 7:] if motion.qvel is not None and motion.qvel.shape[1] == dof.shape[1] + 7 else motion.qvel
    qvel = np.asarray(qvel[:n], dtype=float) if qvel is not None and qvel.shape[-1] == dof.shape[-1] else finite_difference(dof, motion.fps)
    qacc = motion.qacc[:, 7:] if motion.qacc is not None and motion.qacc.shape[1] == dof.shape[1] + 7 else motion.qacc
    qacc = np.asarray(qacc[:n], dtype=float) if qacc is not None and qacc.shape[-1] == dof.shape[-1] else finite_difference(qvel, motion.fps)

    if motion.joint_limits_lower is not None and motion.joint_limits_upper is not None:
        lower = np.asarray(motion.joint_limits_lower, dtype=float)
        upper = np.asarray(motion.joint_limits_upper, dtype=float)
        d = min(dof.shape[1], len(lower), len(upper))
        lower = lower[:d]
        upper = upper[:d]
        finite_limits = np.isfinite(lower) & np.isfinite(upper)
        violation = np.zeros((n, d), dtype=float)
        violation[:, finite_limits] = np.maximum(lower[finite_limits] - dof[:, :d][:, finite_limits], 0.0) + np.maximum(dof[:, :d][:, finite_limits] - upper[finite_limits], 0.0)
        mask = violation > 0
        per_frame["joint_limit_violation_per_frame"] = np.max(violation, axis=1)
        summary["joint_limit_violation_count"] = int(np.sum(mask))
        summary["joint_limit_violation_rate"] = float(np.mean(mask)) if mask.size else np.nan
        summary["joint_limit_violation_max_margin"] = safe_max(violation)
        names = motion.dof_names or [f"dof_{i}" for i in range(d)]
        summary["joint_limit_violation_per_joint"] = {names[i] if i < len(names) else f"dof_{i}": int(np.sum(mask[:, i])) for i in range(d)}
        ranges = upper - lower
        usage = np.divide(np.nanmax(dof[:, :d], axis=0) - np.nanmin(dof[:, :d], axis=0), ranges, out=np.full(d, np.nan), where=(ranges > 1e-12) & finite_limits)
        summary["joint_range_usage_mean"] = safe_mean(usage)
        summary["joint_range_usage_max"] = safe_max(usage)
        summary["joint_range_usage_per_joint"] = {names[i] if i < len(names) else f"dof_{i}": float(usage[i]) if np.isfinite(usage[i]) else np.nan for i in range(d)}
    else:
        for key in ["joint_limit_violation_count", "joint_limit_violation_rate", "joint_limit_violation_max_margin", "joint_limit_violation_per_joint", "joint_range_usage_mean", "joint_range_usage_max", "joint_range_usage_per_joint"]:
            summary[key] = np.nan if not key.endswith("per_joint") else {}
            unavailable[key] = "not_available: joint limits missing; provide MuJoCo XML or limits in PKL"
        per_frame["joint_limit_violation_per_frame"] = np.full(n, np.nan)

    vel_norm = np.linalg.norm(qvel, axis=1)
    acc_norm = np.linalg.norm(qacc, axis=1)
    per_frame["joint_velocity_norm_per_frame"] = vel_norm
    per_frame["joint_acceleration_norm_per_frame"] = acc_norm
    summary["joint_velocity_mean"] = safe_mean(np.abs(qvel))
    summary["joint_velocity_max"] = safe_max(np.abs(qvel))
    summary["joint_acceleration_mean"] = safe_mean(np.abs(qacc))
    summary["joint_acceleration_max"] = safe_max(np.abs(qacc))
    summary["joint_acceleration_std"] = safe_std(qacc)

    limits = motion.joint_velocity_limits
    if limits is not None:
        limits = np.asarray(limits, dtype=float).reshape(-1)
        d = min(qvel.shape[1], len(limits))
        vel_violation = np.abs(qvel[:, :d]) > limits[:d]
        summary["joint_velocity_violation_count"] = int(np.sum(vel_violation))
        summary["joint_velocity_violation_rate"] = float(np.mean(vel_violation))
    else:
        summary["joint_velocity_violation_count"] = np.nan
        summary["joint_velocity_violation_rate"] = np.nan
        unavailable["joint_velocity_violation_rate"] = "not_available: velocity limits missing"
    return summary, per_frame, unavailable

