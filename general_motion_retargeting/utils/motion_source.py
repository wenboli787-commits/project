from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import numpy as np


MOTION_FORMATS = (
    "auto",
    "bvh_lafan1",
    "smplx_npz",
    "amass_npz",
    "joint_positions_npy",
    "joint_positions_npz",
)


LAFAN_PARENT = {
    "Hips": None,
    "LeftUpLeg": "Hips",
    "LeftLeg": "LeftUpLeg",
    "LeftFoot": "LeftLeg",
    "LeftFootMod": "LeftLeg",
    "LeftToe": "LeftFoot",
    "RightUpLeg": "Hips",
    "RightLeg": "RightUpLeg",
    "RightFoot": "RightLeg",
    "RightFootMod": "RightLeg",
    "RightToe": "RightFoot",
    "Spine": "Hips",
    "Spine1": "Spine",
    "Spine2": "Spine1",
    "Neck": "Spine2",
    "Head": "Neck",
    "LeftShoulder": "Spine2",
    "LeftArm": "LeftShoulder",
    "LeftForeArm": "LeftArm",
    "LeftHand": "LeftForeArm",
    "RightShoulder": "Spine2",
    "RightArm": "RightShoulder",
    "RightForeArm": "RightArm",
    "RightHand": "RightForeArm",
}


SMPLX_22_NAMES = [
    "pelvis",
    "left_hip",
    "right_hip",
    "spine1",
    "left_knee",
    "right_knee",
    "spine2",
    "left_ankle",
    "right_ankle",
    "spine3",
    "left_foot",
    "right_foot",
    "neck",
    "left_collar",
    "right_collar",
    "head",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
]


SMPLX_22_PARENT = {
    "pelvis": None,
    "left_hip": "pelvis",
    "right_hip": "pelvis",
    "spine1": "pelvis",
    "left_knee": "left_hip",
    "right_knee": "right_hip",
    "spine2": "spine1",
    "left_ankle": "left_knee",
    "right_ankle": "right_knee",
    "spine3": "spine2",
    "left_foot": "left_ankle",
    "right_foot": "right_ankle",
    "neck": "spine3",
    "left_collar": "spine3",
    "right_collar": "spine3",
    "head": "neck",
    "left_shoulder": "left_collar",
    "right_shoulder": "right_collar",
    "left_elbow": "left_shoulder",
    "right_elbow": "right_shoulder",
    "left_wrist": "left_elbow",
    "right_wrist": "right_elbow",
}


H36M_17_NAMES = [
    "pelvis",
    "right_hip",
    "right_knee",
    "right_foot",
    "left_hip",
    "left_knee",
    "left_foot",
    "spine1",
    "spine3",
    "neck",
    "head",
    "left_shoulder",
    "left_elbow",
    "left_wrist",
    "right_shoulder",
    "right_elbow",
    "right_wrist",
]


H36M_17_PARENT = {
    "pelvis": None,
    "right_hip": "pelvis",
    "right_knee": "right_hip",
    "right_foot": "right_knee",
    "left_hip": "pelvis",
    "left_knee": "left_hip",
    "left_foot": "left_knee",
    "spine1": "pelvis",
    "spine3": "spine1",
    "neck": "spine3",
    "head": "neck",
    "left_shoulder": "spine3",
    "left_elbow": "left_shoulder",
    "left_wrist": "left_elbow",
    "right_shoulder": "spine3",
    "right_elbow": "right_shoulder",
    "right_wrist": "right_elbow",
}


NAME_ALIASES = {
    "hip": "pelvis",
    "hips": "pelvis",
    "root": "pelvis",
    "pelvis": "pelvis",
    "spine": "spine1",
    "thorax": "spine3",
    "chest": "spine3",
    "upperneck": "neck",
    "neck": "neck",
    "head": "head",
    "head_top": "head",
    "headtop": "head",
    "lhip": "left_hip",
    "left_hip": "left_hip",
    "leftupleg": "left_hip",
    "lknee": "left_knee",
    "left_knee": "left_knee",
    "lankle": "left_foot",
    "lfoot": "left_foot",
    "left_foot": "left_foot",
    "rhip": "right_hip",
    "right_hip": "right_hip",
    "rightupleg": "right_hip",
    "rknee": "right_knee",
    "right_knee": "right_knee",
    "rankle": "right_foot",
    "rfoot": "right_foot",
    "right_foot": "right_foot",
    "lshoulder": "left_shoulder",
    "left_shoulder": "left_shoulder",
    "lelbow": "left_elbow",
    "left_elbow": "left_elbow",
    "lwrist": "left_wrist",
    "left_wrist": "left_wrist",
    "rshoulder": "right_shoulder",
    "right_shoulder": "right_shoulder",
    "relbow": "right_elbow",
    "right_elbow": "right_elbow",
    "rwrist": "right_wrist",
    "right_wrist": "right_wrist",
}


@dataclass
class MotionSource:
    path: Path
    motion_format: str
    src_human: str
    frames: list[dict[str, list[np.ndarray]]]
    actual_human_height: float
    fps: float
    parent_map: dict[str, str | None]
    metadata: dict[str, Any]


def add_motion_source_args(parser, default_motion_dir: Path, default_motion_name: str) -> None:
    group = parser.add_argument_group("motion source")
    group.add_argument(
        "--motion_file",
        type=Path,
        default=None,
        help="Motion file path. Supports .bvh, SMPL-X/AMASS .npz, and 3D joint .npy/.npz.",
    )
    group.add_argument(
        "--motion_format",
        choices=MOTION_FORMATS,
        default="auto",
        help="Input format. Use auto unless a .npz file is ambiguous.",
    )
    group.add_argument(
        "--motion_dir",
        type=Path,
        default=default_motion_dir,
        help="Directory used with --motion_name when --motion_file is not set.",
    )
    group.add_argument(
        "--motion_name",
        default=default_motion_name,
        help="Motion filename under --motion_dir when --motion_file is not set.",
    )
    group.add_argument(
        "--bvh_file",
        type=Path,
        default=None,
        help="Backward-compatible BVH path. Overrides --motion_dir/--motion_name.",
    )
    group.add_argument(
        "--smplx_body_model_path",
        type=Path,
        default=None,
        help="SMPL-X body model folder. Default: GMR/assets/body_models.",
    )
    group.add_argument(
        "--joint_array_key",
        default=None,
        help="Array key inside a joint-position .npz. Auto checks common keys.",
    )
    group.add_argument(
        "--joint_names",
        default=None,
        help="Comma-separated joint names for joint-position .npy/.npz files.",
    )
    group.add_argument(
        "--joint_names_file",
        type=Path,
        default=None,
        help="Text file with one joint name per line for joint-position .npy/.npz files.",
    )
    group.add_argument(
        "--joint_skeleton",
        choices=("auto", "smplx_22", "h36m_17"),
        default="auto",
        help="Skeleton order for unnamed joint-position arrays.",
    )
    group.add_argument(
        "--position_unit",
        choices=("auto", "m", "cm", "mm"),
        default="auto",
        help="Unit for joint-position arrays.",
    )
    group.add_argument(
        "--position_scale",
        type=float,
        default=None,
        help="Extra scale for joint-position arrays after unit conversion.",
    )
    group.add_argument(
        "--axis_order",
        default="xyz",
        help="Axis conversion for joint-position arrays, e.g. xyz, xzy, or x,z,-y.",
    )
    group.add_argument(
        "--actual_human_height",
        type=float,
        default=None,
        help="Override estimated human height in meters.",
    )
    group.add_argument("--start_frame", type=int, default=None)
    group.add_argument("--end_frame", type=int, default=None)


def resolve_motion_path(args) -> Path:
    if args.motion_file is not None:
        return args.motion_file.expanduser().resolve()
    if args.bvh_file is not None:
        return args.bvh_file.expanduser().resolve()
    return (args.motion_dir / args.motion_name).expanduser().resolve()


def infer_motion_format(path: Path, requested_format: str) -> str:
    if requested_format != "auto":
        return requested_format

    suffix = path.suffix.lower()
    if suffix == ".bvh":
        return "bvh_lafan1"
    if suffix == ".npy":
        return "joint_positions_npy"
    if suffix == ".npz":
        with np.load(path, allow_pickle=True) as data:
            keys = set(data.files)
        if {"pose_body", "root_orient", "trans"}.issubset(keys):
            return "smplx_npz"
        if "poses" in keys and ("trans" in keys or "transl" in keys):
            return "amass_npz"
        return "joint_positions_npz"

    raise ValueError(
        f"Cannot infer motion format from suffix '{suffix}'. "
        f"Use --motion_format with one of: {', '.join(MOTION_FORMATS)}."
    )


def load_motion_source(args, gmr_root: Path) -> MotionSource:
    path = resolve_motion_path(args)
    motion_format = infer_motion_format(path, args.motion_format)

    if motion_format == "bvh_lafan1":
        return _load_bvh_lafan1(path, args)
    if motion_format in ("smplx_npz", "amass_npz"):
        body_model_path = args.smplx_body_model_path or (gmr_root / "assets" / "body_models")
        return _load_smplx_like_npz(path, motion_format, body_model_path, args)
    if motion_format in ("joint_positions_npy", "joint_positions_npz"):
        return _load_joint_positions(path, motion_format, args)

    raise ValueError(f"Unsupported motion format: {motion_format}")


def validate_motion_source_targets(
    motion_source: MotionSource,
    ik_config_path: Path,
) -> None:
    with open(ik_config_path, encoding="utf-8") as f:
        ik_config = json.load(f)

    required = {ik_config["human_root_name"]}
    for table_name in ("ik_match_table1", "ik_match_table2"):
        if not ik_config.get(f"use_{table_name}", True):
            continue
        for entry in ik_config[table_name].values():
            body_name, pos_weight, rot_weight, _, _ = entry
            if pos_weight != 0 or rot_weight != 0:
                required.add(body_name)

    available = set(motion_source.frames[0].keys()) if motion_source.frames else set()
    missing = sorted(required - available)
    if missing:
        available_preview = ", ".join(sorted(available)[:30])
        raise ValueError(
            f"Motion source '{motion_source.path}' is missing required human bodies "
            f"for IK config '{ik_config_path.name}': {', '.join(missing)}. "
            f"Available bodies include: {available_preview}. "
            "Use --joint_names/--joint_names_file, --joint_skeleton, or convert the file "
            "to SMPL-X/AMASS/BVH format."
        )


def _load_bvh_lafan1(path: Path, args) -> MotionSource:
    from general_motion_retargeting.utils.lafan1 import load_bvh_file

    frames, human_height = load_bvh_file(str(path), format="lafan1")
    frames = _slice_frames(frames, args.start_frame, args.end_frame)
    if args.actual_human_height is not None:
        human_height = args.actual_human_height
    return MotionSource(
        path=path,
        motion_format="bvh_lafan1",
        src_human="bvh_lafan1",
        frames=frames,
        actual_human_height=float(human_height),
        fps=float(args.motion_fps),
        parent_map=LAFAN_PARENT,
        metadata={"loader": "load_bvh_file", "source_type": "LAFAN1 BVH"},
    )


def _load_smplx_like_npz(
    path: Path,
    motion_format: str,
    body_model_path: Path,
    args,
) -> MotionSource:
    import smplx
    import torch
    from smplx.joint_names import JOINT_NAMES

    from general_motion_retargeting.utils.smpl import get_smplx_data_offline_fast

    smplx_data = _normalize_smplx_npz(path)
    gender = _scalar_to_str(smplx_data.get("gender", "neutral"))
    body_model = smplx.create(
        str(body_model_path),
        "smplx",
        gender=gender,
        use_pca=False,
    )

    num_frames = smplx_data["pose_body"].shape[0]
    smplx_output = body_model(
        betas=torch.tensor(smplx_data["betas"]).float().view(1, -1),
        global_orient=torch.tensor(smplx_data["root_orient"]).float(),
        body_pose=torch.tensor(smplx_data["pose_body"]).float(),
        transl=torch.tensor(smplx_data["trans"]).float(),
        left_hand_pose=torch.zeros(num_frames, 45).float(),
        right_hand_pose=torch.zeros(num_frames, 45).float(),
        jaw_pose=torch.zeros(num_frames, 3).float(),
        leye_pose=torch.zeros(num_frames, 3).float(),
        reye_pose=torch.zeros(num_frames, 3).float(),
        return_full_pose=True,
    )

    frames, aligned_fps = get_smplx_data_offline_fast(
        smplx_data,
        body_model,
        smplx_output,
        tgt_fps=args.motion_fps,
    )
    frames = _slice_frames(frames, args.start_frame, args.end_frame)

    human_height = _estimate_smplx_height(smplx_data)
    if args.actual_human_height is not None:
        human_height = args.actual_human_height

    joint_names = JOINT_NAMES[: len(body_model.parents)]
    parent_map = {}
    for i, joint_name in enumerate(joint_names):
        parent_id = int(body_model.parents[i])
        parent_map[joint_name] = joint_names[parent_id] if parent_id >= 0 else None

    return MotionSource(
        path=path,
        motion_format=motion_format,
        src_human="smplx",
        frames=frames,
        actual_human_height=float(human_height),
        fps=float(aligned_fps),
        parent_map=parent_map,
        metadata={
            "loader": "smplx_body_model",
            "source_type": "SMPL-X/AMASS npz",
            "body_model_path": str(body_model_path),
            "gender": gender,
        },
    )


def _normalize_smplx_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=True) as data:
        keys = set(data.files)
        if "pose_body" in keys:
            pose_body = np.asarray(data["pose_body"], dtype=np.float32)
            root_orient = np.asarray(data["root_orient"], dtype=np.float32)
            trans = np.asarray(data["trans"], dtype=np.float32)
        elif "poses" in keys:
            poses = np.asarray(data["poses"], dtype=np.float32)
            if poses.ndim != 2 or poses.shape[1] < 3:
                raise ValueError("AMASS 'poses' must have shape (frames, pose_dim).")
            root_orient = poses[:, :3]
            pose_body = poses[:, 3:66]
            trans_key = "trans" if "trans" in keys else "transl"
            trans = np.asarray(data[trans_key], dtype=np.float32)
        else:
            raise ValueError(
                f"{path} is not a SMPL-X/AMASS npz. Expected pose_body/root_orient or poses."
            )

        if pose_body.ndim == 3:
            pose_body = pose_body.reshape(pose_body.shape[0], -1)
        if pose_body.shape[1] < 63:
            pose_body = np.pad(pose_body, ((0, 0), (0, 63 - pose_body.shape[1])))
        elif pose_body.shape[1] > 63:
            pose_body = pose_body[:, :63]

        betas = np.asarray(data["betas"], dtype=np.float32) if "betas" in keys else np.zeros(16)
        betas = np.asarray(betas).reshape(-1)
        if betas.shape[0] < 16:
            betas = np.pad(betas, (0, 16 - betas.shape[0]))
        elif betas.shape[0] > 16:
            betas = betas[:16]

        raw_gender = data["gender"] if "gender" in keys else "neutral"
        gender = np.asarray(_scalar_to_str(raw_gender))
        fps = _read_fps_from_mapping(data, default=30)

    return {
        "pose_body": pose_body,
        "root_orient": root_orient,
        "trans": trans,
        "betas": betas,
        "gender": gender,
        "mocap_frame_rate": np.asarray(fps),
    }


def _load_joint_positions(path: Path, motion_format: str, args) -> MotionSource:
    raw = _load_joint_position_payload(path, motion_format)
    positions = _extract_joint_array(raw, args.joint_array_key)
    positions = _coerce_positions_shape(positions)
    names = _resolve_joint_names(raw, args, positions.shape[1])
    parent_map = _parent_map_for_names(names, args.joint_skeleton)

    positions = _apply_axis_order(positions, args.axis_order)
    unit_scale, unit_name = _position_unit_scale(positions, args.position_unit)
    scale = unit_scale * (args.position_scale if args.position_scale is not None else 1.0)
    positions = positions * scale

    source_fps = _read_fps_from_mapping(raw, default=args.motion_fps)
    positions, aligned_fps = _resample_positions(positions, source_fps, args.motion_fps)

    frames = _positions_to_frames(positions, names, parent_map)
    frames = _slice_frames(frames, args.start_frame, args.end_frame)

    human_height = args.actual_human_height
    if human_height is None:
        human_height = _estimate_height_from_frames(frames)

    return MotionSource(
        path=path,
        motion_format=motion_format,
        src_human="smplx",
        frames=frames,
        actual_human_height=float(human_height),
        fps=float(aligned_fps),
        parent_map=parent_map,
        metadata={
            "loader": "joint_positions",
            "source_type": "3D joint positions",
            "joint_count": len(names),
            "joint_names": names,
            "position_unit": unit_name,
            "position_scale": scale,
            "axis_order": args.axis_order,
            "rotation_note": "joint rotations are estimated from bone directions",
        },
    )


def _load_joint_position_payload(path: Path, motion_format: str) -> Any:
    if motion_format == "joint_positions_npz":
        with np.load(path, allow_pickle=True) as data:
            return {key: data[key] for key in data.files}

    data = np.load(path, allow_pickle=True)
    if isinstance(data, np.ndarray) and data.shape == () and data.dtype == object:
        return data.item()
    return data


def _extract_joint_array(payload: Any, requested_key: str | None) -> np.ndarray:
    if isinstance(payload, np.ndarray):
        return np.asarray(payload)

    if not isinstance(payload, dict):
        raise ValueError("Joint position input must be an array or a dict-like npz/npy object.")

    if requested_key is not None:
        if requested_key not in payload:
            raise KeyError(f"Joint array key '{requested_key}' was not found.")
        return np.asarray(payload[requested_key])

    candidate_keys = (
        "positions",
        "joints",
        "joint_positions",
        "keypoints3d",
        "keypoints_3d",
        "poses_3d",
        "pose_3d",
        "joints3d",
        "pred_joints",
    )
    for key in candidate_keys:
        if key in payload:
            return np.asarray(payload[key])

    arrays = [
        (key, value)
        for key, value in payload.items()
        if isinstance(value, np.ndarray) and value.ndim >= 2
    ]
    if len(arrays) == 1:
        return np.asarray(arrays[0][1])

    available = ", ".join(str(k) for k in payload.keys())
    raise ValueError(
        "Could not infer the joint position array key. "
        f"Use --joint_array_key. Available keys: {available}"
    )


def _coerce_positions_shape(array: np.ndarray) -> np.ndarray:
    positions = np.asarray(array, dtype=float)
    positions = np.squeeze(positions)
    if positions.ndim == 2 and positions.shape[-1] == 3:
        positions = positions[None, :, :]
    elif positions.ndim == 2 and positions.shape[1] % 3 == 0:
        positions = positions.reshape(positions.shape[0], positions.shape[1] // 3, 3)
    elif positions.ndim == 3:
        if positions.shape[1] == 3 and positions.shape[-1] != 3:
            positions = np.transpose(positions, (0, 2, 1))
        elif (
            positions.shape[0] in (17, 22, 24, 25, 32)
            and positions.shape[1] not in (17, 22, 24, 25, 32)
            and positions.shape[-1] >= 3
        ):
            positions = np.transpose(positions[..., :3], (1, 0, 2))
        elif positions.shape[0] <= 64 and positions.shape[1] > 64 and positions.shape[-1] >= 3:
            positions = np.transpose(positions[..., :3], (1, 0, 2))
        elif positions.shape[-1] >= 3:
            positions = positions[..., :3]
        else:
            raise ValueError(
                "Joint positions must have shape (frames, joints, 3), "
                "(frames, 3, joints), (joints, frames, 3), "
                "(joints, 3), or (frames, joints*3)."
            )
    else:
        raise ValueError(
            "Joint positions must have shape (frames, joints, 3), "
            "(frames, 3, joints), (joints, frames, 3), "
            "(joints, 3), or (frames, joints*3)."
        )

    if not np.isfinite(positions).all():
        positions = np.nan_to_num(positions, nan=0.0, posinf=0.0, neginf=0.0)
    return positions


def _resolve_joint_names(payload: Any, args, joint_count: int) -> list[str]:
    if args.joint_names:
        names = [name.strip() for name in args.joint_names.split(",") if name.strip()]
    elif args.joint_names_file:
        names = [
            line.strip()
            for line in args.joint_names_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    elif isinstance(payload, dict):
        names = _read_joint_names_from_payload(payload)
    else:
        names = []

    if not names:
        if args.joint_skeleton == "h36m_17" or (args.joint_skeleton == "auto" and joint_count == 17):
            names = H36M_17_NAMES
        else:
            names = _default_smplx_like_names(joint_count)

    canonical_names = _canonicalize_joint_names(names)
    if len(canonical_names) < joint_count:
        raise ValueError(
            f"Only {len(canonical_names)} joint names were provided for {joint_count} joints."
        )
    return canonical_names[:joint_count]


def _default_smplx_like_names(joint_count: int) -> list[str]:
    if joint_count <= len(SMPLX_22_NAMES):
        return SMPLX_22_NAMES[:joint_count]
    extras = [f"extra_joint_{idx}" for idx in range(len(SMPLX_22_NAMES), joint_count)]
    return SMPLX_22_NAMES + extras


def _read_joint_names_from_payload(payload: dict[str, Any]) -> list[str]:
    for key in ("joint_names", "joints_name", "joint_name", "names", "keypoint_names"):
        if key not in payload:
            continue
        value = payload[key]
        if isinstance(value, np.ndarray):
            value = value.tolist()
        if isinstance(value, (list, tuple)):
            return [_scalar_to_str(item) for item in value]
    return []


def _canonical_joint_name(name: str) -> str:
    cleaned = str(name).strip()
    key = _joint_name_key(cleaned)
    return NAME_ALIASES.get(key, cleaned)


def _canonicalize_joint_names(names: list[str]) -> list[str]:
    keys = [_joint_name_key(name) for name in names]
    has_left_foot = any(key in ("left_foot", "leftfoot", "lfoot") for key in keys)
    has_right_foot = any(key in ("right_foot", "rightfoot", "rfoot") for key in keys)

    canonical_names = []
    used_names = set()
    for idx, name in enumerate(names):
        cleaned = str(name).strip()
        key = keys[idx]
        if key in ("left_ankle", "leftankle") and not has_left_foot:
            canonical = "left_foot"
        elif key in ("right_ankle", "rightankle") and not has_right_foot:
            canonical = "right_foot"
        else:
            canonical = _canonical_joint_name(cleaned)
        if canonical in used_names:
            canonical = cleaned if cleaned not in used_names else f"{cleaned}_{idx}"
        canonical_names.append(canonical)
        used_names.add(canonical)
    return canonical_names


def _joint_name_key(name: str) -> str:
    return str(name).strip().replace(" ", "_").replace("-", "_").lower()


def _parent_map_for_names(names: list[str], skeleton: str) -> dict[str, str | None]:
    if skeleton == "h36m_17" or (skeleton == "auto" and len(names) == 17):
        base_parent = H36M_17_PARENT
    else:
        base_parent = SMPLX_22_PARENT

    available = set(names)
    parent_map = {}
    for name in names:
        parent = base_parent.get(name)
        parent_map[name] = parent if parent in available else None
    return parent_map


def _positions_to_frames(
    positions: np.ndarray,
    names: list[str],
    parent_map: dict[str, str | None],
) -> list[dict[str, list[np.ndarray]]]:
    name_to_idx = {name: i for i, name in enumerate(names)}
    children = {name: [] for name in names}
    for child, parent in parent_map.items():
        if parent in children:
            children[parent].append(child)

    frames = []
    for frame_positions in positions:
        side = _side_vector(frame_positions, name_to_idx)
        result = {}
        for name in names:
            idx = name_to_idx[name]
            primary = _primary_bone_vector(name, frame_positions, name_to_idx, parent_map, children)
            quat = _rotation_from_primary_and_side(primary, side).as_quat(scalar_first=True)
            result[name] = [frame_positions[idx].copy(), quat]
        frames.append(result)
    return frames


def _side_vector(frame_positions: np.ndarray, name_to_idx: dict[str, int]) -> np.ndarray:
    for left, right in (("left_hip", "right_hip"), ("left_shoulder", "right_shoulder")):
        if left in name_to_idx and right in name_to_idx:
            return frame_positions[name_to_idx[right]] - frame_positions[name_to_idx[left]]
    return np.array([1.0, 0.0, 0.0])


def _primary_bone_vector(
    name: str,
    frame_positions: np.ndarray,
    name_to_idx: dict[str, int],
    parent_map: dict[str, str | None],
    children: dict[str, list[str]],
) -> np.ndarray:
    idx = name_to_idx[name]
    for child in children.get(name, []):
        if child in name_to_idx:
            return frame_positions[name_to_idx[child]] - frame_positions[idx]

    parent = parent_map.get(name)
    if parent in name_to_idx:
        return frame_positions[idx] - frame_positions[name_to_idx[parent]]

    if name == "pelvis" and "spine3" in name_to_idx:
        return frame_positions[name_to_idx["spine3"]] - frame_positions[idx]
    return np.array([0.0, 0.0, 1.0])


def _rotation_from_primary_and_side(primary: np.ndarray, side: np.ndarray):
    from scipy.spatial.transform import Rotation as R

    z_axis = _normalized(primary, fallback=np.array([0.0, 0.0, 1.0]))
    side_projected = side - np.dot(side, z_axis) * z_axis
    x_axis = _normalized(side_projected, fallback=_orthogonal_axis(z_axis))
    y_axis = np.cross(z_axis, x_axis)
    y_axis = _normalized(y_axis, fallback=np.array([0.0, 1.0, 0.0]))
    x_axis = _normalized(np.cross(y_axis, z_axis), fallback=x_axis)
    matrix = np.column_stack([x_axis, y_axis, z_axis])
    return R.from_matrix(matrix)


def _normalized(vector: np.ndarray, fallback: np.ndarray) -> np.ndarray:
    vector = np.asarray(vector, dtype=float)
    norm = np.linalg.norm(vector)
    if norm < 1e-8:
        return np.asarray(fallback, dtype=float)
    return vector / norm


def _orthogonal_axis(axis: np.ndarray) -> np.ndarray:
    candidates = (np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]))
    for candidate in candidates:
        projected = candidate - np.dot(candidate, axis) * axis
        if np.linalg.norm(projected) > 1e-8:
            return projected
    return np.array([0.0, 0.0, 1.0])


def _apply_axis_order(positions: np.ndarray, axis_order: str) -> np.ndarray:
    tokens = _parse_axis_order(axis_order)
    axis_lookup = {"x": 0, "y": 1, "z": 2}
    converted = []
    for sign, axis_name in tokens:
        converted.append(sign * positions[..., axis_lookup[axis_name]])
    return np.stack(converted, axis=-1)


def _parse_axis_order(axis_order: str) -> list[tuple[float, str]]:
    spec = axis_order.strip().lower()
    if "," in spec:
        raw_tokens = [token.strip() for token in spec.split(",") if token.strip()]
    else:
        raw_tokens = list(spec)

    tokens = []
    for token in raw_tokens:
        sign = -1.0 if token.startswith("-") else 1.0
        axis_name = token[1:] if token.startswith("-") else token
        if axis_name not in ("x", "y", "z"):
            raise ValueError(
                f"Invalid --axis_order '{axis_order}'. Use xyz, xzy, or comma form like x,z,-y."
            )
        tokens.append((sign, axis_name))
    if len(tokens) != 3:
        raise ValueError(f"--axis_order must select exactly 3 axes, got: {axis_order}")
    return tokens


def _position_unit_scale(positions: np.ndarray, unit: str) -> tuple[float, str]:
    if unit == "m":
        return 1.0, "m"
    if unit == "cm":
        return 0.01, "cm"
    if unit == "mm":
        return 0.001, "mm"

    bbox = np.nanmax(positions.reshape(-1, 3), axis=0) - np.nanmin(
        positions.reshape(-1, 3), axis=0
    )
    span = float(np.nanmax(bbox))
    if span > 1000.0:
        return 0.001, "auto_mm"
    if span > 3.0:
        return 0.01, "auto_cm"
    return 1.0, "auto_m"


def _read_fps_from_mapping(mapping: Any, default: float) -> float:
    if not isinstance(mapping, dict) and not hasattr(mapping, "files"):
        return float(default)
    for key in ("mocap_frame_rate", "mocap_framerate", "frame_rate", "fps"):
        try:
            if key in mapping:
                return float(np.asarray(mapping[key]).reshape(-1)[0])
        except Exception:
            continue
    return float(default)


def _resample_positions(
    positions: np.ndarray,
    source_fps: float,
    target_fps: float,
) -> tuple[np.ndarray, float]:
    if source_fps <= 0 or target_fps <= 0 or abs(source_fps - target_fps) < 1e-6:
        return positions, float(target_fps)

    frame_count = positions.shape[0]
    if frame_count < 2:
        return positions, float(target_fps)

    duration = (frame_count - 1) / source_fps
    target_count = max(2, int(round(duration * target_fps)) + 1)
    src_t = np.linspace(0.0, duration, frame_count)
    dst_t = np.linspace(0.0, duration, target_count)

    flat = positions.reshape(frame_count, -1)
    resampled = np.empty((target_count, flat.shape[1]), dtype=float)
    for col in range(flat.shape[1]):
        resampled[:, col] = np.interp(dst_t, src_t, flat[:, col])
    return resampled.reshape(target_count, positions.shape[1], 3), float(target_fps)


def _slice_frames(frames: list[Any], start_frame: int | None, end_frame: int | None) -> list[Any]:
    start = start_frame if start_frame is not None else 0
    end = end_frame if end_frame is not None else None
    return frames[start:end]


def _estimate_smplx_height(smplx_data: dict[str, np.ndarray]) -> float:
    betas = smplx_data.get("betas", np.zeros(1))
    betas = np.asarray(betas).reshape(-1)
    return float(1.66 + 0.1 * betas[0])


def _estimate_height_from_frames(frames: list[dict[str, list[np.ndarray]]]) -> float:
    if not frames:
        return 1.7

    samples = frames[: min(len(frames), 30)]
    heights = []
    for frame in samples:
        if "head" in frame and ("left_foot" in frame or "right_foot" in frame):
            head_z = frame["head"][0][2]
            foot_z = min(
                frame.get("left_foot", [np.array([0.0, 0.0, head_z])])[0][2],
                frame.get("right_foot", [np.array([0.0, 0.0, head_z])])[0][2],
            )
            heights.append(head_z - foot_z)
        else:
            all_pos = np.asarray([value[0] for value in frame.values()])
            heights.append(float(np.max(all_pos[:, 2]) - np.min(all_pos[:, 2])))

    height = float(np.median(heights))
    if not np.isfinite(height) or height < 0.5:
        return 1.7
    return height


def _scalar_to_str(value: Any) -> str:
    if isinstance(value, np.ndarray):
        if value.shape == ():
            return _scalar_to_str(value.item())
        if value.size == 1:
            return _scalar_to_str(value.reshape(-1)[0])
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, np.bytes_):
        return value.tobytes().decode("utf-8")
    return str(value)
