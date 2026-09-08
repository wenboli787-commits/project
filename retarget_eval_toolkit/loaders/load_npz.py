from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .common_motion import as_array, first_existing, make_motion, read_names, rotvec_to_wxyz, unwrap_np_value


DEFAULT_SMPLX_22 = [
    "pelvis", "left_hip", "right_hip", "spine1", "left_knee", "right_knee",
    "spine2", "left_ankle", "right_ankle", "spine3", "left_foot", "right_foot",
    "neck", "left_collar", "right_collar", "head", "left_shoulder",
    "right_shoulder", "left_elbow", "right_elbow", "left_wrist", "right_wrist",
]


def load_npz(path: str | Path, config: Optional[Dict[str, Any]] = None, *, method: Optional[str] = None) -> Any:
    """Load NPZ motion files.

    Supports canonical keypoint NPZ, SMPL-X/AMASS-style parameter NPZ, and
    generic joint-position NPZ. SMPL-X parameters are converted to root data by
    default; full SMPL-X keypoints are computed only when `smplx` + model files
    are available via config.
    """
    config = config or {}
    path = Path(path)
    with np.load(path, allow_pickle=True) as data:
        raw = {key: unwrap_np_value(data[key]) for key in data.files}

    fps = _read_fps(raw, config)
    warnings: List[str] = []
    root_pos = as_array(first_existing(raw, ["root_pos", "pelvis_pos", "trans", "transl", "global_translation"]), dtype=float)
    root_rot = as_array(first_existing(raw, ["root_quat", "root_rot", "root_orient", "global_orient"]), dtype=float)

    if root_rot is not None and root_rot.shape[-1] == 3:
        root_rot = rotvec_to_wxyz(root_rot)
    elif root_rot is not None and root_rot.shape[-1] == 4:
        order = str(config.get("npz_quaternion_order", "wxyz")).lower()
        if order == "xyzw":
            from .common_motion import quat_xyzw_to_wxyz

            root_rot = quat_xyzw_to_wxyz(root_rot)

    joint_pos, joint_names = _extract_joint_positions(raw, config, warnings)
    if joint_pos is None:
        smpl_result = _try_smplx_keypoints(raw, config, warnings)
        if smpl_result is not None:
            joint_pos, joint_names = smpl_result

    if root_pos is None and joint_pos is not None and joint_names:
        for candidate in ["pelvis", "root", "Hips"]:
            if candidate in joint_names:
                root_pos = joint_pos[:, joint_names.index(candidate), :]
                break

    if root_pos is None and "poses" in raw:
        warnings.append("NPZ contains SMPL/AMASS `poses` but no usable translation/root key; root_pos is unavailable.")
    if joint_pos is None and ("poses" in raw or "pose_body" in raw):
        warnings.append("SMPL-X/AMASS keypoints require optional `smplx`, `torch`, and body model files; keypoint metrics will be NaN without them.")

    return make_motion(
        path,
        fps,
        method=method,
        root_pos=root_pos,
        root_rot=root_rot,
        joint_pos=joint_pos,
        joint_names=joint_names,
        extra={"raw_keys": sorted(raw.keys())},
        warnings=warnings,
    )


def _read_fps(raw: Dict[str, Any], config: Dict[str, Any]) -> float:
    for key in ["fps", "frame_rate", "mocap_framerate", "mocap_frame_rate"]:
        if key in raw:
            return float(np.asarray(raw[key]).reshape(-1)[0])
    return float(config.get("target_fps", config.get("fps", 30.0)))


def _extract_joint_positions(raw: Dict[str, Any], config: Dict[str, Any], warnings: List[str]) -> Tuple[Optional[np.ndarray], Optional[List[str]]]:
    value = first_existing(raw, ["joint_pos", "joint_positions", "joints", "positions", "keypoints", "keypoints3d", "poses_3d"])
    if value is None:
        return None, None
    arr = _coerce_joint_array(value)
    if arr is None:
        warnings.append("A joint-position key exists, but its shape could not be interpreted as [T, J, 3].")
        return None, None
    names = read_names(first_existing(raw, ["joint_names", "joints_name", "names", "keypoint_names"]))
    if names is None:
        names = _default_names(arr.shape[1], str(config.get("joint_skeleton", "auto")))
    return arr, names[: arr.shape[1]]


def _coerce_joint_array(value: Any) -> Optional[np.ndarray]:
    arr = np.asarray(value, dtype=float)
    arr = np.squeeze(arr)
    if arr.ndim == 2 and arr.shape[-1] == 3:
        return arr[None, :, :]
    if arr.ndim == 2 and arr.shape[1] % 3 == 0:
        return arr.reshape(arr.shape[0], arr.shape[1] // 3, 3)
    if arr.ndim == 3:
        if arr.shape[-1] >= 3:
            return arr[..., :3]
        if arr.shape[1] == 3:
            return np.transpose(arr, (0, 2, 1))
    return None


def _default_names(joint_count: int, skeleton: str) -> List[str]:
    if skeleton in {"smplx_22", "auto"} and joint_count <= len(DEFAULT_SMPLX_22):
        return DEFAULT_SMPLX_22[:joint_count]
    if joint_count == 22:
        return DEFAULT_SMPLX_22
    return [f"joint_{i}" for i in range(joint_count)]


def _try_smplx_keypoints(raw: Dict[str, Any], config: Dict[str, Any], warnings: List[str]) -> Optional[Tuple[np.ndarray, List[str]]]:
    model_path = config.get("smplx_body_model_path") or config.get("body_model_path")
    if not model_path:
        return None
    try:
        import torch
        import smplx
        from smplx.joint_names import JOINT_NAMES
    except Exception as exc:
        warnings.append(f"SMPL-X keypoint conversion skipped: optional dependency missing ({exc}).")
        return None

    try:
        if "pose_body" in raw:
            pose_body = np.asarray(raw["pose_body"], dtype=float)
            root_orient = np.asarray(raw.get("root_orient", np.zeros((pose_body.shape[0], 3))), dtype=float)
            trans = np.asarray(raw.get("trans", np.zeros((pose_body.shape[0], 3))), dtype=float)
        elif "poses" in raw:
            poses = np.asarray(raw["poses"], dtype=float)
            root_orient = poses[:, :3]
            pose_body = poses[:, 3:66]
            trans = np.asarray(raw.get("trans", np.zeros((poses.shape[0], 3))), dtype=float)
        else:
            return None
        betas = np.asarray(raw.get("betas", np.zeros(16)), dtype=float).reshape(1, -1)
        gender = str(np.asarray(raw.get("gender", "neutral")).reshape(-1)[0])
        model = smplx.create(str(model_path), "smplx", gender=gender, use_pca=False)
        n = pose_body.shape[0]
        out = model(
            betas=torch.tensor(betas).float(),
            global_orient=torch.tensor(root_orient).float(),
            body_pose=torch.tensor(pose_body[:, :63]).float(),
            transl=torch.tensor(trans).float(),
            left_hand_pose=torch.zeros(n, 45).float(),
            right_hand_pose=torch.zeros(n, 45).float(),
            jaw_pose=torch.zeros(n, 3).float(),
            leye_pose=torch.zeros(n, 3).float(),
            reye_pose=torch.zeros(n, 3).float(),
        )
        joints = out.joints.detach().cpu().numpy()
        names = list(JOINT_NAMES[: joints.shape[1]])
        return joints, names
    except Exception as exc:
        warnings.append(f"SMPL-X keypoint conversion failed: {exc}. Keypoint metrics will be NaN.")
        return None

