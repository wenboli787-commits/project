"""Abstract boundary between raw simulator logs and CanonicalMotion."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional, Tuple

import numpy as np

from canonical_motion import CanonicalMotion


class SimulatorAdapter(ABC):
    def __init__(self, robot_model: Optional[Path] = None) -> None:
        self.robot_model = Path(robot_model).expanduser() if robot_model else None
        self.warnings: list[str] = []

    @abstractmethod
    def load_motion(self, motion_path: Path, config: dict[str, Any]) -> CanonicalMotion:
        """Read one motion source and return the standard representation."""

    def compute_forward_kinematics(self, motion: CanonicalMotion) -> CanonicalMotion:
        self.warnings.append("Forward kinematics unavailable for this adapter/input.")
        return motion

    def get_joint_limits(self) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        return None, None

    def estimate_contacts(self, motion: CanonicalMotion) -> CanonicalMotion:
        return motion

    def estimate_effort(self, motion: CanonicalMotion) -> CanonicalMotion:
        return motion
