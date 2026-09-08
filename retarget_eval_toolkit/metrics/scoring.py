from __future__ import annotations

from typing import Any, Dict

import numpy as np


def add_scores(summary: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """Add six category scores and an overall score in [0, 100]."""
    summary["similarity_score"] = _avg_scores([
        _lower(summary.get("mpjpe_mean"), 0.25),
        _lower(summary.get("end_effector_error_mean"), 0.25),
        _lower(summary.get("root_position_error_mean"), 0.25),
        _lower(summary.get("root_orientation_error_deg"), 30.0),
    ])
    summary["kinematic_score"] = _avg_scores([
        _rate(summary.get("joint_limit_violation_rate")),
        _lower(summary.get("joint_velocity_mean"), 5.0),
        _lower(summary.get("joint_acceleration_mean"), 50.0),
    ])
    summary["physical_score"] = _avg_scores([
        summary.get("physical_feasibility_score"),
        _lower(summary.get("motion_energy_proxy"), 100.0),
        _lower(summary.get("torque_mean"), 50.0),
    ])
    summary["contact_score"] = _avg_scores([
        _lower(summary.get("foot_penetration_mean"), 0.03),
        _lower(summary.get("foot_sliding_total"), 0.5),
        _higher_f1(summary.get("left_contact_f1")),
        _higher_f1(summary.get("right_contact_f1")),
    ])
    summary["stability_score"] = _avg_scores([
        _lower(summary.get("root_height_error_against_reference"), 0.2),
        _lower(summary.get("body_tilt_max_deg"), 45.0),
        _rate(summary.get("fall_like_rate")),
        100.0 if summary.get("episode_completed") is True else 0.0 if summary.get("episode_completed") is False else np.nan,
    ])
    summary["smoothness_score"] = _avg_scores([
        _lower(summary.get("joint_jerk_mean"), 200.0),
        _lower(summary.get("keypoint_jerk_mean"), 50.0),
        _rate(summary.get("frame_jump_rate")),
        _rate(summary.get("self_collision_rate")),
    ])

    weights = config.get("score_weights", {
        "similarity": 0.25,
        "kinematic_feasibility": 0.15,
        "physical_feasibility": 0.10,
        "contact_quality": 0.20,
        "stability": 0.20,
        "smoothness": 0.10,
    })
    terms = [
        ("similarity", "similarity_score"),
        ("kinematic_feasibility", "kinematic_score"),
        ("physical_feasibility", "physical_score"),
        ("contact_quality", "contact_score"),
        ("stability", "stability_score"),
        ("smoothness", "smoothness_score"),
    ]
    total = 0.0
    weight_sum = 0.0
    for weight_key, score_key in terms:
        score = _finite(summary.get(score_key))
        if score is None:
            continue
        weight = float(weights.get(weight_key, 0.0))
        total += weight * score
        weight_sum += weight
    summary["overall_score"] = float(total / weight_sum) if weight_sum > 0 else np.nan
    return summary


def _lower(value: Any, scale: float) -> float:
    x = _finite(value)
    if x is None:
        return np.nan
    return float(100.0 / (1.0 + max(x, 0.0) / scale))


def _rate(value: Any) -> float:
    x = _finite(value)
    if x is None:
        return np.nan
    return float(100.0 * max(0.0, 1.0 - min(max(x, 0.0), 1.0)))


def _higher_f1(value: Any) -> float:
    x = _finite(value)
    if x is None:
        return np.nan
    return float(100.0 * min(max(x, 0.0), 1.0))


def _avg_scores(values: list[Any]) -> float:
    finite = [float(v) for v in values if _finite(v) is not None]
    return float(np.mean(finite)) if finite else np.nan


def _finite(value: Any) -> float | None:
    try:
        x = float(value)
    except Exception:
        return None
    return x if np.isfinite(x) else None

