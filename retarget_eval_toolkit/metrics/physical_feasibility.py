from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np

from loaders.common_motion import MotionData
from .common import safe_max, safe_mean, safe_std


def compute_physical_feasibility(motion: MotionData, config: Dict[str, Any], kinematic_summary: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, np.ndarray], Dict[str, str]]:
    """Compute torque/control effort and dynamics proxy metrics."""
    n = motion.num_frames
    summary: Dict[str, Any] = {}
    per_frame: Dict[str, np.ndarray] = {}
    unavailable: Dict[str, str] = {}
    effort = _first_array(motion.extra, ["torque", "torques", "qfrc", "actuator_force", "control", "ctrl", "action", "actions"])
    if effort is not None:
        effort = np.asarray(effort, dtype=float)[:n]
        per_frame["torque_norm_per_frame"] = np.linalg.norm(effort.reshape(n, -1), axis=1)
        summary["torque_mean"] = safe_mean(np.abs(effort))
        summary["torque_max"] = safe_max(np.abs(effort))
        summary["torque_std"] = safe_std(effort)
        summary["control_effort"] = safe_mean(per_frame["torque_norm_per_frame"])
        torque_limits = np.asarray(config.get("robot", {}).get("torque_limits", []), dtype=float)
        if torque_limits.size:
            flat = effort.reshape(n, -1)
            d = min(flat.shape[1], torque_limits.size)
            summary["torque_limit_violation_rate"] = float(np.mean(np.abs(flat[:, :d]) > torque_limits[:d]))
        else:
            summary["torque_limit_violation_rate"] = np.nan
            unavailable["torque_limit_violation_rate"] = "not_available: torque limits missing"
    else:
        for key in ["torque_mean", "torque_max", "torque_std", "torque_limit_violation_rate", "control_effort", "mechanical_energy_proxy"]:
            summary[key] = np.nan
            unavailable[key] = "not_available: no torque/control/action field in PKL"
        per_frame["torque_norm_per_frame"] = np.full(n, np.nan)

    qvel = motion.qvel
    qacc = motion.qacc
    qvel_term = safe_mean(np.square(qvel)) if qvel is not None else np.nan
    qacc_term = safe_mean(np.square(qacc)) if qacc is not None else np.nan
    summary["qacc_mean"] = safe_mean(np.abs(qacc)) if qacc is not None else np.nan
    summary["qacc_max"] = safe_max(np.abs(qacc)) if qacc is not None else np.nan
    summary["motion_energy_proxy"] = float(np.nansum([qvel_term, qacc_term]))
    if effort is not None and qvel is not None:
        flat_e = effort.reshape(n, -1)
        flat_v = qvel.reshape(n, -1)
        d = min(flat_e.shape[1], flat_v.shape[1])
        summary["mechanical_energy_proxy"] = float(np.nanmean(np.abs(flat_e[:, :d] * flat_v[:, :d])))

    penalty = 0.0
    count = 0
    for value, scale in [
        (kinematic_summary.get("joint_limit_violation_rate"), 0.05),
        (kinematic_summary.get("joint_velocity_mean"), 5.0),
        (kinematic_summary.get("joint_acceleration_mean"), 50.0),
        (summary.get("torque_mean"), 50.0),
    ]:
        if value is not None and np.isfinite(float(value)):
            penalty += min(float(value) / scale, 3.0)
            count += 1
    summary["physical_feasibility_score"] = float(100.0 / (1.0 + penalty / max(count, 1))) if count else np.nan
    return summary, per_frame, unavailable


def _first_array(extra: Dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = extra.get(key)
        if value is not None:
            return value
        meta = extra.get("metadata")
        if isinstance(meta, dict) and key in meta:
            return meta[key]
    return None

