try:
    from rich import print
except ImportError:
    pass

from .params import IK_CONFIG_ROOT, ASSET_ROOT, ROBOT_XML_DICT, IK_CONFIG_DICT, ROBOT_BASE_DICT, VIEWER_CAM_DISTANCE_DICT
from .data_loader import load_robot_motion


def _unavailable_class(name, exc):
    class Unavailable:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                f"{name} cannot be used because an optional dependency is missing: {exc}. "
                "Install the full GMR retargeting environment if you need retargeting."
            ) from exc

    Unavailable.__name__ = name
    return Unavailable


try:
    from .motion_retarget import GeneralMotionRetargeting
except ImportError as exc:
    GeneralMotionRetargeting = _unavailable_class("GeneralMotionRetargeting", exc)

try:
    from .robot_motion_viewer import RobotMotionViewer, draw_frame
except ImportError as exc:
    RobotMotionViewer = _unavailable_class("RobotMotionViewer", exc)
    draw_frame = None

try:
    from .kinematics_model import KinematicsModel
except ImportError as exc:
    KinematicsModel = _unavailable_class("KinematicsModel", exc)

try:
    from .neck_retarget import human_head_to_robot_neck
except ImportError as exc:
    def human_head_to_robot_neck(*args, **kwargs):
        raise ImportError(
            f"human_head_to_robot_neck cannot be used because an optional dependency is missing: {exc}."
        ) from exc

try:
    from .xrobot_utils import XRobotStreamer, XRobotRecorder
except ImportError:
    XRobotStreamer = None
    XRobotRecorder = None
