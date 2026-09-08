from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from .common_motion import make_motion
from kinematics.bvh_fk import load_bvh_as_arrays


def load_bvh(path: str | Path, config: Optional[Dict[str, Any]] = None, *, method: Optional[str] = None) -> Any:
    """Load a standard BVH file with built-in FK."""
    config = config or {}
    positions, quats, names, fps = load_bvh_as_arrays(path)
    return make_motion(path, fps or float(config.get("target_fps", 30.0)), method=method, root_pos=positions[:, 0, :], root_rot=quats[:, 0, :], joint_pos=positions, joint_names=names)

