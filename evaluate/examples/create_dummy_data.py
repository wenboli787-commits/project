"""Create four tiny canonical NPZ files to test the whole evaluator."""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np

EVALUATE_DIR = Path(__file__).resolve().parents[1]
if str(EVALUATE_DIR) not in sys.path:
    sys.path.insert(0, str(EVALUATE_DIR))

from utils import wxyz_to_xyzw


FPS = 30.0
FRAMES = 180
DOFS = 12


def _quat_identity(frames: int) -> np.ndarray:
    quat = np.zeros((frames, 4), dtype=float)
    quat[:, 0] = 1.0
    return quat


def _reference() -> dict[str, object]:
    time = np.arange(FRAMES) / FPS
    root = np.column_stack((0.75 * time, 0.02 * np.sin(2 * np.pi * time), np.full(FRAMES, 0.82)))
    phase = 2 * np.pi * 1.2 * time
    left_lift = np.maximum(0.0, np.sin(phase)) * 0.11
    right_lift = np.maximum(0.0, np.sin(phase + np.pi)) * 0.11
    left_foot = root + np.column_stack((-0.08 + 0.09 * np.sin(phase), np.full(FRAMES, 0.10), -0.82 + left_lift))
    right_foot = root + np.column_stack((0.08 + 0.09 * np.sin(phase + np.pi), np.full(FRAMES, -0.10), -0.82 + right_lift))
    left_hand = root + np.column_stack((np.full(FRAMES, -0.24), 0.22 * np.sin(phase), np.full(FRAMES, 0.50)))
    right_hand = root + np.column_stack((np.full(FRAMES, 0.24), 0.22 * np.sin(phase + np.pi), np.full(FRAMES, 0.50)))
    head = root + np.array([0.0, 0.0, 0.78])
    joints = np.stack((root, head, left_hand, right_hand, left_foot, right_foot), axis=1)
    names = np.array(["pelvis", "head", "left_wrist", "right_wrist", "left_ankle", "right_ankle"])
    contacts = {"left_ankle": left_foot[:, 2] < 0.025, "right_ankle": right_foot[:, 2] < 0.025}
    return {"fps": FPS, "root_pos": root, "root_quat": wxyz_to_xyzw(_quat_identity(FRAMES)), "joint_positions_ref": joints, "joint_names_ref": names, "foot_contacts": contacts}


def _candidate(reference: dict[str, object], method: str, noise: float, *, tracking: bool = False) -> dict[str, object]:
    rng = np.random.default_rng({"direct": 3, "basic_ik": 7, "gmr": 11}[method])
    root = np.asarray(reference["root_pos"], dtype=float) + rng.normal(scale=noise * 0.20, size=(FRAMES, 3))
    ref_joints = np.asarray(reference["joint_positions_ref"], dtype=float)
    names = ["pelvis", "head", "left_hand", "right_hand", "left_foot", "right_foot"]
    bodies = {name: ref_joints[:, index] + rng.normal(scale=noise, size=(FRAMES, 3)) for index, name in enumerate(names)}
    bodies["pelvis"] = root
    bodies["torso"] = root + np.array([0.0, 0.0, 0.43]) + rng.normal(scale=noise * 0.2, size=(FRAMES, 3))
    quats = {name: wxyz_to_xyzw(_quat_identity(FRAMES)) for name in bodies}
    dof_pos = 0.40 * np.column_stack([np.sin(np.arange(FRAMES) / FPS * (index + 1)) for index in range(DOFS)])
    if method == "direct":
        dof_pos[:, 0] += 1.05  # gives the demo a visible limit violation
    dof_vel = np.gradient(dof_pos, 1.0 / FPS, axis=0)
    contacts = {"left_foot": bodies["left_foot"][:, 2] < 0.04, "right_foot": bodies["right_foot"][:, 2] < 0.04}
    payload: dict[str, object] = {
        "fps": FPS,
        "root_pos": root,
        "root_quat": wxyz_to_xyzw(_quat_identity(FRAMES)),
        "dof_pos": dof_pos,
        "dof_vel": dof_vel,
        "dof_names": np.array([f"joint_{index}" for index in range(DOFS)]),
        "dof_limits_lower": np.full(DOFS, -0.9),
        "dof_limits_upper": np.full(DOFS, 0.9),
        "body_positions": bodies,
        "body_quats": quats,
        "foot_contacts": contacts,
        "torques": 2.0 * dof_vel + rng.normal(scale=0.05, size=dof_vel.shape),
        "actions": dof_pos,
    }
    if tracking:
        payload["target_dof_pos"] = dof_pos
        payload["actual_dof_pos"] = dof_pos + rng.normal(scale=0.015, size=dof_pos.shape)
        payload["target_dof_vel"] = dof_vel
        payload["actual_dof_vel"] = np.gradient(np.asarray(payload["actual_dof_pos"]), 1.0 / FPS, axis=0)
    return payload


def main() -> Path:
    destination = Path(__file__).resolve().parent / "dummy_data"
    destination.mkdir(parents=True, exist_ok=True)
    reference = _reference()
    np.savez(destination / "dummy_reference_motion.npz", **reference)
    np.savez(destination / "dummy_direct_mapping_result.npz", **_candidate(reference, "direct", 0.10))
    np.savez(destination / "dummy_basic_ik_result.npz", **_candidate(reference, "basic_ik", 0.05))
    np.savez(destination / "dummy_gmr_result.npz", **_candidate(reference, "gmr", 0.018, tracking=True))
    print(f"Created dummy motion files in: {destination}")
    return destination


if __name__ == "__main__":
    main()
