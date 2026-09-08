"""Simulator-neutral contact, foot-sliding and ground-penetration metrics."""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

from canonical_motion import CanonicalMotion
from utils import UNAVAILABLE, finite_difference


FOOT_SEMANTICS = ("left_foot", "right_foot")


def landmark_position(motion: CanonicalMotion, semantic: str, mapping: dict[str, Any], *, reference: bool) -> Optional[np.ndarray]:
    section = mapping.get("reference" if reference else "robot", {})
    suffix = "joint" if reference else "body"
    configured = section.get(f"{semantic}_{suffix}")
    candidates = [configured, semantic]
    aliases = {
        "left_foot": ["left_ankle", "l_ankle", "left_foot_link"],
        "right_foot": ["right_ankle", "r_ankle", "right_foot_link"],
        "left_hand": ["left_wrist", "l_wrist", "left_hand_link"],
        "right_hand": ["right_wrist", "r_wrist", "right_hand_link"],
        "root": ["pelvis", "base", "base_link"],
    }
    candidates.extend(aliases.get(semantic, []))
    for name in candidates:
        if name:
            result = motion.position(str(name))
            if result is not None:
                return result
    return None


def _contact_from_dict(motion: CanonicalMotion, semantic: str, mapping: dict[str, Any], reference: bool) -> Optional[np.ndarray]:
    if not motion.foot_contacts:
        return None
    section = mapping.get("reference" if reference else "robot", {})
    name = section.get(f"{semantic}_{'joint' if reference else 'body'}")
    candidates = [semantic, name, semantic.replace("foot", "ankle")]
    for candidate in candidates:
        if candidate and candidate in motion.foot_contacts:
            return np.asarray(motion.foot_contacts[candidate]).reshape(-1).astype(bool)
    return None


def _contact_from_force(motion: CanonicalMotion, semantic: str, mapping: dict[str, Any], reference: bool, threshold: float) -> Optional[np.ndarray]:
    if not motion.contact_forces:
        return None
    section = mapping.get("reference" if reference else "robot", {})
    name = section.get(f"{semantic}_{'joint' if reference else 'body'}")
    candidates = [semantic, name, semantic.replace("foot", "ankle")]
    for candidate in candidates:
        if candidate and candidate in motion.contact_forces:
            force = np.asarray(motion.contact_forces[candidate], dtype=float)
            magnitude = np.abs(force) if force.ndim == 1 else np.linalg.norm(force, axis=-1)
            return magnitude >= threshold
    return None


def resolve_foot_contact(motion: CanonicalMotion, semantic: str, mapping: dict[str, Any], thresholds: dict[str, Any], *, reference: bool) -> tuple[Optional[np.ndarray], str]:
    """Use logged boolean contacts, then force, then a kinematic estimate."""
    direct = _contact_from_dict(motion, semantic, mapping, reference)
    if direct is not None:
        return direct, "logged_contact"
    from_force = _contact_from_force(motion, semantic, mapping, reference, float(thresholds.get("foot_contact_force", 5.0)))
    if from_force is not None:
        return from_force, "force_threshold"
    position = landmark_position(motion, semantic, mapping, reference=reference)
    if position is None:
        return None, UNAVAILABLE
    speed = np.linalg.norm(finite_difference(position, motion.fps), axis=-1)
    ground = float(thresholds.get("ground_height", 0.0))
    height = float(thresholds.get("foot_contact_height", 0.05))
    velocity = float(thresholds.get("foot_contact_velocity", 0.2))
    return (position[:, 2] <= ground + height) & (speed <= velocity), "kinematic_estimate"


def contact_accuracy(reference: CanonicalMotion, candidate: CanonicalMotion, mapping: dict[str, Any], thresholds: dict[str, Any]) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    result: dict[str, Any] = {}
    per_frame: dict[str, np.ndarray] = {}
    for foot in FOOT_SEMANTICS:
        ref_contact, ref_source = resolve_foot_contact(reference, foot, mapping, thresholds, reference=True)
        robot_contact, robot_source = resolve_foot_contact(candidate, foot, mapping, thresholds, reference=False)
        prefix = f"contact.{foot}"
        if ref_contact is None or robot_contact is None:
            result[foot] = UNAVAILABLE
            continue
        count = min(len(ref_contact), len(robot_contact))
        truth, prediction = ref_contact[:count], robot_contact[:count]
        tp = int(np.sum(truth & prediction))
        fp = int(np.sum(~truth & prediction))
        fn = int(np.sum(truth & ~prediction))
        precision = tp / (tp + fp) if tp + fp else 1.0
        recall = tp / (tp + fn) if tp + fn else 1.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        mismatch = truth != prediction
        result[foot] = {
            "accuracy": float(np.mean(~mismatch)), "precision": precision, "recall": recall,
            "f1": f1, "mismatch_rate": float(np.mean(mismatch)),
            "reference_source": ref_source, "robot_source": robot_source,
        }
        per_frame[f"{prefix}.mismatch"] = mismatch.astype(int)
    return result, per_frame


def foot_sliding(candidate: CanonicalMotion, mapping: dict[str, Any], thresholds: dict[str, Any]) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    result: dict[str, Any] = {}
    per_frame: dict[str, np.ndarray] = {}
    threshold = float(thresholds.get("foot_sliding_velocity", 0.15))
    for foot in FOOT_SEMANTICS:
        position = landmark_position(candidate, foot, mapping, reference=False)
        contact, source = resolve_foot_contact(candidate, foot, mapping, thresholds, reference=False)
        if position is None or contact is None:
            result[foot] = UNAVAILABLE
            continue
        horizontal_speed = np.linalg.norm(finite_difference(position, candidate.fps)[:, :2], axis=-1)
        active = horizontal_speed[contact]
        sliding = contact & (horizontal_speed > threshold)
        result[foot] = {
            "mean_sliding_speed": float(np.mean(active)) if len(active) else 0.0,
            "max_sliding_speed": float(np.max(active)) if len(active) else 0.0,
            "sliding_frame_ratio": float(np.mean(sliding)), "contact_source": source,
        }
        per_frame[f"sliding.{foot}.speed"] = horizontal_speed
        per_frame[f"sliding.{foot}.active"] = sliding.astype(int)
    return result, per_frame


def ground_penetration(candidate: CanonicalMotion, mapping: dict[str, Any], thresholds: dict[str, Any]) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    ground = float(thresholds.get("ground_height", 0.0))
    result: dict[str, Any] = {}
    per_frame: dict[str, np.ndarray] = {}
    all_heights: list[np.ndarray] = []
    for foot in FOOT_SEMANTICS:
        position = landmark_position(candidate, foot, mapping, reference=False)
        if position is None:
            result[foot] = UNAVAILABLE
            continue
        height = position[:, 2]
        depth = np.maximum(ground - height, 0.0)
        result[foot] = {"min_height": float(np.min(height)), "max_penetration_depth": float(np.max(depth)), "penetration_frame_ratio": float(np.mean(depth > 0.0))}
        per_frame[f"penetration.{foot}.depth"] = depth
        all_heights.append(height)
    if not all_heights:
        result["aggregate"] = UNAVAILABLE
    else:
        heights = np.stack(all_heights, axis=1)
        depth = np.maximum(ground - heights, 0.0)
        result["aggregate"] = {"min_foot_height": float(np.min(heights)), "max_penetration_depth": float(np.max(depth)), "penetration_frame_ratio": float(np.mean(np.any(depth > 0.0, axis=1)))}
    return result, per_frame


def evaluate_contact_metrics(reference: CanonicalMotion, candidate: CanonicalMotion, mapping: dict[str, Any]) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    thresholds = mapping.get("thresholds", {})
    accuracy, accuracy_frames = contact_accuracy(reference, candidate, mapping, thresholds)
    sliding, sliding_frames = foot_sliding(candidate, mapping, thresholds)
    penetration, penetration_frames = ground_penetration(candidate, mapping, thresholds)
    return {"foot_contact_accuracy": accuracy, "foot_sliding": sliding, "ground_penetration": penetration}, {**accuracy_frames, **sliding_frames, **penetration_frames}
