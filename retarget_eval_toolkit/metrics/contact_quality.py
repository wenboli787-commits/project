from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np

from loaders.common_motion import MotionData
from .common import safe_max, safe_mean, safe_min


def compute_contact_quality(reference: MotionData, prediction: MotionData, config: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, np.ndarray], Dict[str, str]]:
    """Compute foot penetration, sliding, timing, and clearance metrics."""
    n = min(reference.num_frames, prediction.num_frames)
    ground = float(config.get("robot", {}).get("ground_height", 0.0))
    threshold = float(config.get("contact", {}).get("contact_threshold", 0.05))
    slide_threshold = float(config.get("contact", {}).get("sliding_threshold", 0.02))
    summary: Dict[str, Any] = {}
    per_frame: Dict[str, np.ndarray] = {}
    unavailable: Dict[str, str] = {}
    penetrations = []
    slidings = []
    for side in ["left", "right"]:
        foot = prediction.get_keypoint(f"{side}_foot")
        if foot is None:
            for key in [f"{side}_foot_penetration_depth", f"{side}_foot_sliding_distance", f"{side}_foot_clearance_mean"]:
                summary[key] = np.nan
                unavailable[key] = f"not_available: {side}_foot keypoint missing"
            per_frame[f"{side}_foot_penetration_per_frame"] = np.full(n, np.nan)
            per_frame[f"{side}_foot_sliding_per_frame"] = np.full(n, np.nan)
            continue
        foot = np.asarray(foot[:n], dtype=float)
        penetration = np.maximum(0.0, ground - foot[:, 2])
        contact = _contact_from_motion(prediction, side, foot, ground, threshold)
        step = np.concatenate([[0.0], np.linalg.norm(np.diff(foot[:, :2], axis=0), axis=1)])
        sliding = np.where(contact, step, 0.0)
        per_frame[f"{side}_foot_penetration_per_frame"] = penetration
        per_frame[f"{side}_foot_sliding_per_frame"] = sliding
        per_frame[f"{side}_foot_contact"] = contact.astype(float)
        summary[f"{side}_foot_penetration_depth"] = safe_mean(penetration)
        summary[f"{side}_foot_sliding_distance"] = float(np.nansum(sliding))
        summary[f"{side}_foot_clearance_mean"] = safe_mean(foot[:, 2] - ground)
        penetrations.append(penetration)
        slidings.append(sliding)

        ref_foot = reference.get_keypoint(f"{side}_foot")
        if ref_foot is None:
            summary[f"{side}_contact_precision"] = np.nan
            summary[f"{side}_contact_recall"] = np.nan
            summary[f"{side}_contact_f1"] = np.nan
            unavailable[f"{side}_contact_f1"] = f"not_available: reference {side}_foot keypoint missing"
        else:
            ref_contact = _contact_from_motion(reference, side, np.asarray(ref_foot[:n], dtype=float), ground, threshold)
            p, r, f1 = _precision_recall_f1(ref_contact, contact)
            summary[f"{side}_contact_precision"] = p
            summary[f"{side}_contact_recall"] = r
            summary[f"{side}_contact_f1"] = f1
            per_frame[f"reference_{side}_foot_contact"] = ref_contact.astype(float)

    if penetrations:
        pen = np.stack(penetrations, axis=1)
        summary["foot_penetration_mean"] = safe_mean(pen)
        summary["foot_penetration_max"] = safe_max(pen)
        summary["foot_penetration_frames"] = int(np.sum(np.any(pen > 0, axis=1)))
        summary["foot_penetration_rate"] = float(np.mean(np.any(pen > 0, axis=1)))
    else:
        for key in ["foot_penetration_mean", "foot_penetration_max", "foot_penetration_frames", "foot_penetration_rate"]:
            summary[key] = np.nan
            unavailable[key] = "not_available: both robot foot keypoints missing"
    if slidings:
        slide = np.stack(slidings, axis=1)
        summary["foot_sliding_total"] = float(np.nansum(slide))
        summary["foot_sliding_mean"] = safe_mean(slide)
        summary["foot_sliding_rate"] = float(np.mean(np.any(slide > slide_threshold, axis=1)))
    else:
        for key in ["foot_sliding_total", "foot_sliding_mean", "foot_sliding_rate"]:
            summary[key] = np.nan
            unavailable[key] = "not_available: both robot foot keypoints missing"

    f1s = [summary.get("left_contact_f1", np.nan), summary.get("right_contact_f1", np.nan)]
    summary["contact_timing_error"] = 1.0 - safe_mean(f1s) if np.isfinite(safe_mean(f1s)) else np.nan
    clearances = []
    for side in ["left", "right"]:
        foot = prediction.get_keypoint(f"{side}_foot")
        if foot is not None:
            clearances.append(np.asarray(foot[:n])[:, 2] - ground)
    if clearances:
        clearance = np.concatenate(clearances)
        summary["foot_clearance_min"] = safe_min(clearance)
        summary["foot_clearance_max"] = safe_max(clearance)
    else:
        summary["foot_clearance_min"] = np.nan
        summary["foot_clearance_max"] = np.nan
    return summary, per_frame, unavailable


def _contact_from_motion(motion: MotionData, side: str, foot: np.ndarray, ground: float, threshold: float) -> np.ndarray:
    if motion.contacts and f"{side}_foot" in motion.contacts:
        return np.asarray(motion.contacts[f"{side}_foot"][: len(foot)], dtype=bool)
    return foot[:, 2] < ground + threshold


def _precision_recall_f1(ref: np.ndarray, pred: np.ndarray) -> Tuple[float, float, float]:
    tp = float(np.sum(ref & pred))
    fp = float(np.sum(~ref & pred))
    fn = float(np.sum(ref & ~pred))
    precision = tp / (tp + fp) if tp + fp > 0 else np.nan
    recall = tp / (tp + fn) if tp + fn > 0 else np.nan
    f1 = 2 * precision * recall / (precision + recall) if np.isfinite(precision) and np.isfinite(recall) and precision + recall > 0 else np.nan
    return precision, recall, f1

