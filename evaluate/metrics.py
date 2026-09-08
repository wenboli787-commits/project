"""Independent, simulator-agnostic metrics over CanonicalMotion."""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

from canonical_motion import CanonicalMotion
from contact_metrics import evaluate_contact_metrics, landmark_position
from utils import UNAVAILABLE, finite_difference, normalize_quaternions, quat_rotate


LANDMARKS = ("root", "head", "left_hand", "right_hand", "left_foot", "right_foot")


def _summary(values: np.ndarray) -> dict[str, float]:
    return {"mean": float(np.mean(values)), "max": float(np.max(values)), "min": float(np.min(values))}


def landmark_quaternion(motion: CanonicalMotion, semantic: str, mapping: dict[str, Any], *, reference: bool) -> Optional[np.ndarray]:
    if semantic == "root":
        return motion.root_quat
    section = mapping.get("reference" if reference else "robot", {})
    configured = section.get(f"{semantic}_{'joint' if reference else 'body'}")
    candidates = [configured, semantic]
    aliases = {"left_hand": ["left_wrist"], "right_hand": ["right_wrist"], "left_foot": ["left_ankle"], "right_foot": ["right_ankle"]}
    candidates.extend(aliases.get(semantic, []))
    for name in candidates:
        if name:
            quat = motion.quaternion(str(name))
            if quat is not None:
                return quat
    return None


def end_effector_position_error(reference: CanonicalMotion, candidate: CanonicalMotion, mapping: dict[str, Any]) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    result: dict[str, Any] = {}
    per_frame: dict[str, np.ndarray] = {}
    for landmark in LANDMARKS:
        ref = landmark_position(reference, landmark, mapping, reference=True)
        robot = landmark_position(candidate, landmark, mapping, reference=False)
        if ref is None or robot is None:
            result[landmark] = UNAVAILABLE
            continue
        error = np.linalg.norm(ref - robot, axis=-1)
        result[landmark] = _summary(error)
        per_frame[f"end_effector_error.{landmark}"] = error
    available = [item["mean"] for item in result.values() if isinstance(item, dict)]
    result["aggregate_mean"] = float(np.mean(available)) if available else UNAVAILABLE
    return result, per_frame


def root_trajectory_error(reference: CanonicalMotion, candidate: CanonicalMotion) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    if reference.root_pos is None or candidate.root_pos is None:
        return UNAVAILABLE, {}
    error = reference.root_pos - candidate.root_pos
    result: dict[str, Any] = {"position": _summary(np.linalg.norm(error, axis=-1)), "xy": _summary(np.linalg.norm(error[:, :2], axis=-1)), "height": _summary(np.abs(error[:, 2]))}
    frames = {"root_error.position": np.linalg.norm(error, axis=-1), "root_error.xy": np.linalg.norm(error[:, :2], axis=-1), "root_error.height": np.abs(error[:, 2])}
    if reference.root_quat is not None and candidate.root_quat is not None:
        angle = quaternion_angle_error(reference.root_quat, candidate.root_quat)
        result["orientation"] = {**_summary(angle), "mean_degrees": float(np.degrees(np.mean(angle))), "max_degrees": float(np.degrees(np.max(angle)))}
        frames["root_error.orientation_rad"] = angle
    reference_velocity = reference.root_lin_vel if reference.root_lin_vel is not None else finite_difference(reference.root_pos, reference.fps)
    candidate_velocity = candidate.root_lin_vel if candidate.root_lin_vel is not None else finite_difference(candidate.root_pos, candidate.fps)
    velocity_error = np.linalg.norm(reference_velocity - candidate_velocity, axis=-1)
    result["velocity"] = _summary(velocity_error)
    frames["root_error.velocity"] = velocity_error
    return result, frames


def quaternion_angle_error(reference_quat: np.ndarray, candidate_quat: np.ndarray) -> np.ndarray:
    ref = normalize_quaternions(reference_quat)
    cand = normalize_quaternions(candidate_quat)
    dot = np.sum(ref * cand, axis=-1)
    return 2.0 * np.arccos(np.clip(np.abs(dot), -1.0, 1.0))


def rotation_error(reference: CanonicalMotion, candidate: CanonicalMotion, mapping: dict[str, Any]) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    result: dict[str, Any] = {}
    frames: dict[str, np.ndarray] = {}
    for landmark in LANDMARKS:
        ref = landmark_quaternion(reference, landmark, mapping, reference=True)
        robot = landmark_quaternion(candidate, landmark, mapping, reference=False)
        if ref is None or robot is None:
            result[landmark] = UNAVAILABLE
            continue
        error = quaternion_angle_error(ref, robot)
        result[landmark] = {**_summary(error), "mean_degrees": float(np.degrees(np.mean(error))), "max_degrees": float(np.degrees(np.max(error)))}
        frames[f"rotation_error.{landmark}_rad"] = error
    return result, frames


def velocity_error(reference: CanonicalMotion, candidate: CanonicalMotion, mapping: dict[str, Any]) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    result: dict[str, Any] = {}
    frames: dict[str, np.ndarray] = {}
    for landmark in LANDMARKS:
        ref = landmark_position(reference, landmark, mapping, reference=True)
        robot = landmark_position(candidate, landmark, mapping, reference=False)
        if ref is None or robot is None:
            result[landmark] = UNAVAILABLE
            continue
        error = np.linalg.norm(finite_difference(ref, reference.fps) - finite_difference(robot, candidate.fps), axis=-1)
        result[landmark] = _summary(error)
        frames[f"velocity_error.{landmark}"] = error
    return result, frames


def joint_limit_violation(candidate: CanonicalMotion) -> tuple[Any, dict[str, np.ndarray]]:
    if candidate.dof_pos is None or candidate.dof_limits_lower is None or candidate.dof_limits_upper is None:
        return UNAVAILABLE, {}
    lower, upper = np.asarray(candidate.dof_limits_lower), np.asarray(candidate.dof_limits_upper)
    if lower.ndim != 1 or upper.ndim != 1 or lower.shape[0] != candidate.dof_pos.shape[1] or upper.shape[0] != candidate.dof_pos.shape[1]:
        return UNAVAILABLE, {}
    below = np.maximum(lower - candidate.dof_pos, 0.0)
    above = np.maximum(candidate.dof_pos - upper, 0.0)
    amount = below + above
    violated = amount > 0
    names = candidate.dof_names or [f"dof_{index}" for index in range(candidate.dof_pos.shape[1])]
    return {
        "violation_frame_ratio": float(np.mean(np.any(violated, axis=1))),
        "violation_value_ratio": float(np.mean(violated)),
        "per_joint_violation_count": {name: int(count) for name, count in zip(names, np.sum(violated, axis=0))},
        "max_violation_amount": float(np.max(amount)), "mean_violation_amount": float(np.mean(amount[violated])) if np.any(violated) else 0.0,
    }, {"joint_limit.max_violation": np.max(amount, axis=1), "joint_limit.violated": np.any(violated, axis=1).astype(int)}


def effort_energy(candidate: CanonicalMotion) -> tuple[Any, dict[str, np.ndarray]]:
    if candidate.torques is None:
        return UNAVAILABLE, {}
    torque = np.asarray(candidate.torques, dtype=float)
    if torque.ndim != 2:
        return UNAVAILABLE, {}
    velocity = candidate.dof_vel
    result: dict[str, Any] = {"mean_abs_torque": float(np.mean(np.abs(torque))), "max_abs_torque": float(np.max(np.abs(torque)))}
    frames = {"effort.mean_abs_torque": np.mean(np.abs(torque), axis=1)}
    if velocity is not None and velocity.shape == torque.shape:
        power = np.sum(np.abs(torque * velocity), axis=1)
        result["mean_abs_power"] = float(np.mean(power))
        result["energy_proxy"] = float(np.sum(power) / candidate.fps)
        frames["effort.abs_power"] = power
    else:
        result["energy_proxy"] = UNAVAILABLE
        result["energy_note"] = "dof_vel is missing or dimensionally incompatible with torque"
    if candidate.torque_limits_lower is not None and candidate.torque_limits_upper is not None:
        lower, upper = np.asarray(candidate.torque_limits_lower), np.asarray(candidate.torque_limits_upper)
        if lower.shape == (torque.shape[1],) and upper.shape == (torque.shape[1],):
            violation = np.maximum(lower - torque, 0.0) + np.maximum(torque - upper, 0.0)
            result["torque_limit_violation_frame_ratio"] = float(np.mean(np.any(violation > 0.0, axis=1)))
            result["max_torque_limit_violation"] = float(np.max(violation))
            frames["effort.max_torque_limit_violation"] = np.max(violation, axis=1)
        else:
            result["torque_limit_violation"] = UNAVAILABLE
    if candidate.metadata.get("torque_source"):
        result["torque_source"] = candidate.metadata["torque_source"]
    return result, frames


def smoothness(candidate: CanonicalMotion, mapping: dict[str, Any]) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    result: dict[str, Any] = {}
    frames: dict[str, np.ndarray] = {}
    if candidate.dof_pos is None:
        result["dof"] = UNAVAILABLE
    else:
        velocity = candidate.dof_vel if candidate.dof_vel is not None else finite_difference(candidate.dof_pos, candidate.fps)
        acceleration = candidate.dof_acc if candidate.dof_acc is not None else finite_difference(velocity, candidate.fps)
        jerk = finite_difference(acceleration, candidate.fps)
        result["dof"] = {"mean_joint_velocity": float(np.mean(np.abs(velocity))), "max_joint_velocity": float(np.max(np.abs(velocity))), "mean_joint_acceleration": float(np.mean(np.abs(acceleration))), "max_joint_acceleration": float(np.max(np.abs(acceleration))), "mean_jerk": float(np.mean(np.abs(jerk))), "max_jerk": float(np.max(np.abs(jerk)))}
        frames.update({"smoothness.dof_velocity": np.mean(np.abs(velocity), axis=1), "smoothness.dof_acceleration": np.mean(np.abs(acceleration), axis=1), "smoothness.dof_jerk": np.mean(np.abs(jerk), axis=1)})
    end_effector_result: dict[str, Any] = {}
    for landmark in LANDMARKS:
        position = landmark_position(candidate, landmark, mapping, reference=False)
        if position is None:
            end_effector_result[landmark] = UNAVAILABLE
            continue
        velocity = finite_difference(position, candidate.fps)
        acceleration = finite_difference(velocity, candidate.fps)
        jerk = finite_difference(acceleration, candidate.fps)
        end_effector_result[landmark] = {"mean_velocity": float(np.mean(np.linalg.norm(velocity, axis=-1))), "max_velocity": float(np.max(np.linalg.norm(velocity, axis=-1))), "mean_acceleration": float(np.mean(np.linalg.norm(acceleration, axis=-1))), "max_acceleration": float(np.max(np.linalg.norm(acceleration, axis=-1))), "mean_jerk": float(np.mean(np.linalg.norm(jerk, axis=-1))), "max_jerk": float(np.max(np.linalg.norm(jerk, axis=-1)))}
    result["end_effectors"] = end_effector_result
    return result, frames


def stability_and_fall(candidate: CanonicalMotion, mapping: dict[str, Any]) -> tuple[Any, dict[str, np.ndarray]]:
    if candidate.root_pos is None:
        return UNAVAILABLE, {}
    thresholds = mapping.get("thresholds", {})
    base_height = candidate.root_pos[:, 2]
    base_fail = base_height < float(thresholds.get("fall_base_height", 0.45))
    torso = landmark_quaternion(candidate, "torso", mapping, reference=False)
    tilt = None
    tilt_fail = np.zeros(candidate.num_frames, dtype=bool)
    if torso is not None:
        upright = quat_rotate(torso, np.broadcast_to(np.array([0.0, 0.0, 1.0]), (candidate.num_frames, 3)))
        tilt = np.arccos(np.clip(upright[:, 2], -1.0, 1.0))
        tilt_fail = np.degrees(tilt) > float(thresholds.get("fall_torso_tilt_deg", 60.0))
    fallen = base_fail | tilt_fail
    frames = {"stability.base_height": base_height, "stability.fallen": fallen.astype(int)}
    if tilt is not None:
        frames["stability.torso_tilt_deg"] = np.degrees(tilt)
    first = int(np.argmax(fallen)) if np.any(fallen) else None
    return {"fall_detected": bool(np.any(fallen)), "fall_frame": first, "survival_time_s": float((first if first is not None else candidate.num_frames) / candidate.fps), "fall_rate": float(np.mean(fallen)), "min_base_height": float(np.min(base_height)), "max_torso_tilt_deg": float(np.max(np.degrees(tilt))) if tilt is not None else UNAVAILABLE}, frames


def tracking_error(candidate: CanonicalMotion) -> tuple[Any, dict[str, np.ndarray]]:
    result: dict[str, Any] = {}
    frames: dict[str, np.ndarray] = {}
    for field, target, actual in (("dof_pos", candidate.target_dof_pos, candidate.actual_dof_pos), ("dof_vel", candidate.target_dof_vel, candidate.actual_dof_vel)):
        if target is None or actual is None or target.shape != actual.shape:
            result[field] = UNAVAILABLE
            continue
        error = np.linalg.norm(target - actual, axis=-1)
        result[field] = _summary(error)
        frames[f"tracking.{field}"] = error
    if candidate.target_root_pos is not None and candidate.actual_root_pos is not None and candidate.target_root_pos.shape == candidate.actual_root_pos.shape:
        error = np.linalg.norm(candidate.target_root_pos - candidate.actual_root_pos, axis=-1)
        result["root_pos"] = _summary(error)
        frames["tracking.root_pos"] = error
    for label, target, actual in (("body_position", candidate.target_body_positions, candidate.actual_body_positions), ("end_effector_position", candidate.target_end_effector_positions, candidate.actual_end_effector_positions)):
        if not target or not actual:
            result[label] = UNAVAILABLE
            continue
        shared = sorted(set(target) & set(actual))
        if not shared:
            result[label] = UNAVAILABLE
            continue
        errors = {name: np.linalg.norm(np.asarray(target[name]) - np.asarray(actual[name]), axis=-1) for name in shared if np.asarray(target[name]).shape == np.asarray(actual[name]).shape}
        if not errors:
            result[label] = UNAVAILABLE
            continue
        stacked = np.stack(list(errors.values()), axis=1)
        result[label] = {"aggregate": _summary(np.mean(stacked, axis=1)), "per_body": {name: _summary(error) for name, error in errors.items()}}
        frames[f"tracking.{label}"] = np.mean(stacked, axis=1)
    return result if any(value != UNAVAILABLE for value in result.values()) else UNAVAILABLE, frames


def locomotion_task_success(candidate: CanonicalMotion, stability: Any, mapping: dict[str, Any]) -> Any:
    if candidate.root_pos is None:
        return UNAVAILABLE
    thresholds = mapping.get("thresholds", {})
    delta = candidate.root_pos[-1] - candidate.root_pos[0]
    step = np.diff(candidate.root_pos[:, :2], axis=0)
    travel = float(np.sum(np.linalg.norm(step, axis=-1)))
    displacement = float(np.linalg.norm(delta[:2]))
    duration = max(candidate.duration, 1.0 / candidate.fps)
    fell = bool(stability.get("fall_detected", False)) if isinstance(stability, dict) else False
    moved = displacement >= float(thresholds.get("min_forward_displacement", 0.3))
    heading_error = UNAVAILABLE
    if candidate.root_quat is not None and displacement > 1e-8:
        heading = np.arctan2(delta[1], delta[0])
        facing = np.arctan2(2 * (candidate.root_quat[-1, 0] * candidate.root_quat[-1, 3] + candidate.root_quat[-1, 1] * candidate.root_quat[-1, 2]), 1 - 2 * (candidate.root_quat[-1, 2] ** 2 + candidate.root_quat[-1, 3] ** 2))
        heading_error = float(np.degrees(np.abs(np.arctan2(np.sin(heading - facing), np.cos(heading - facing)))))
    return {"root_displacement": displacement, "travel_distance": travel, "average_speed": travel / duration, "heading_error_deg": heading_error, "moved_forward": moved, "fell": fell, "success_flag": bool(moved and not fell)}


def evaluate_all_metrics(reference: CanonicalMotion, candidate: CanonicalMotion, mapping: dict[str, Any]) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    """Evaluate one candidate; disabled or data-starved metrics remain explicit."""
    enabled = mapping.get("metrics", {})
    summary: dict[str, Any] = {}
    frames: dict[str, np.ndarray] = {}
    def add(name: str, flag: str, function):
        if enabled.get(flag, True):
            value, per_frame = function()
            summary[name] = value
            frames.update(per_frame)
        else:
            summary[name] = "disabled"
    add("end_effector_position_error", "compute_end_effector_error", lambda: end_effector_position_error(reference, candidate, mapping))
    add("root_trajectory_error", "compute_root_error", lambda: root_trajectory_error(reference, candidate))
    add("rotation_error", "compute_rotation_error", lambda: rotation_error(reference, candidate, mapping))
    add("velocity_error", "compute_velocity_error", lambda: velocity_error(reference, candidate, mapping))
    if enabled.get("compute_contact_metrics", True):
        contact, contact_frames = evaluate_contact_metrics(reference, candidate, mapping)
        summary["contact"] = contact
        frames.update(contact_frames)
    else:
        summary["contact"] = "disabled"
    add("joint_limit_violation", "compute_joint_limit_violation", lambda: joint_limit_violation(candidate))
    add("smoothness", "compute_smoothness", lambda: smoothness(candidate, mapping))
    stability, stability_frames = stability_and_fall(candidate, mapping) if enabled.get("compute_stability", True) else ("disabled", {})
    summary["stability"] = stability
    frames.update(stability_frames)
    add("effort_energy", "compute_energy", lambda: effort_energy(candidate))
    add("tracking_error", "compute_tracking_error", lambda: tracking_error(candidate))
    if enabled.get("compute_task_success", True):
        summary["locomotion_task_success"] = locomotion_task_success(candidate, stability, mapping)
    else:
        summary["locomotion_task_success"] = "disabled"
    return summary, frames
