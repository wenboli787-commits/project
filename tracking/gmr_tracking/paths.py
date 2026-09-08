from __future__ import annotations

import importlib.util
from functools import lru_cache
from pathlib import Path
from types import ModuleType


TRACKING_ROOT = Path(__file__).resolve().parents[1]
GMR_ROOT = TRACKING_ROOT.parent
PARAMS_PATH = GMR_ROOT / "general_motion_retargeting" / "params.py"


@lru_cache(maxsize=1)
def load_gmr_params() -> ModuleType:
    """Load GMR params.py without importing the heavy retargeting package."""

    if not PARAMS_PATH.exists():
        raise FileNotFoundError(f"GMR params.py not found: {PARAMS_PATH}")
    spec = importlib.util.spec_from_file_location("_gmr_tracking_params", PARAMS_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not create import spec for {PARAMS_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_robot_xml_path(robot: str) -> Path:
    params = load_gmr_params()
    if robot not in params.ROBOT_XML_DICT:
        supported = ", ".join(sorted(params.ROBOT_XML_DICT))
        raise ValueError(f"Unsupported robot '{robot}'. Supported robots: {supported}")
    return Path(params.ROBOT_XML_DICT[robot]).resolve()


def get_robot_base_name(robot: str) -> str | None:
    params = load_gmr_params()
    return params.ROBOT_BASE_DICT.get(robot)


def get_viewer_camera_distance(robot: str) -> float:
    params = load_gmr_params()
    return float(params.VIEWER_CAM_DISTANCE_DICT.get(robot, 2.5))


def list_supported_robots() -> list[str]:
    params = load_gmr_params()
    return sorted(params.ROBOT_XML_DICT)
