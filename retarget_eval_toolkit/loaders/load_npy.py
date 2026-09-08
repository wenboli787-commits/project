from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from .common_motion import make_motion
from .load_npz import _coerce_joint_array, _default_names


def load_npy(path: str | Path, config: Optional[Dict[str, Any]] = None, *, method: Optional[str] = None) -> Any:
    """Load NPY motion files.

    Recognizes `[T, J, 3]`, `[T, J*3]`, and scalar dict payloads. HumanML3D-like
    feature arrays that cannot be safely decoded are loaded as `extra` and
    reported with a warning instead of being misinterpreted as keypoints.
    """
    config = config or {}
    path = Path(path)
    arr = np.load(path, allow_pickle=True)
    warnings = []
    if isinstance(arr, np.ndarray) and arr.dtype == object and arr.shape == ():
        obj = arr.item()
        if isinstance(obj, dict):
            from .load_npz import _extract_joint_positions, _read_fps

            joint_pos, joint_names = _extract_joint_positions(obj, config, warnings)
            return make_motion(path, _read_fps(obj, config), method=method, joint_pos=joint_pos, joint_names=joint_names, extra={"raw_keys": sorted(obj.keys())}, warnings=warnings)

    joint_pos = _coerce_joint_array(arr)
    joint_names = None
    if joint_pos is not None:
        joint_names = _default_names(joint_pos.shape[1], str(config.get("joint_skeleton", "auto")))
    else:
        warnings.append(
            f"NPY shape {getattr(arr, 'shape', None)} is not a recognizable [T,J,3] joint array. "
            "It may be a HumanML3D feature vector; convert it to joint positions before keypoint evaluation."
        )
    return make_motion(path, float(config.get("target_fps", 30.0)), method=method, joint_pos=joint_pos, joint_names=joint_names, extra={"npy_shape": getattr(arr, "shape", None)}, warnings=warnings)

