"""Adapter for already-exported trajectories without a simulator runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from canonical_motion import CanonicalMotion
from loaders import load_canonical_motion
from simulator_adapters.base_adapter import SimulatorAdapter


class OfflineAdapter(SimulatorAdapter):
    def load_motion(self, motion_path: Path, config: dict[str, Any]) -> CanonicalMotion:
        expected = dict(config.get("offline", {}).get("expected_keys", {}))
        expected["quaternion_order"] = config.get("input", {}).get("quaternion_order", "xyzw")
        expected["fps"] = config.get("input", {}).get("fps", 30.0)
        loader_config = {"expected_keys": expected, "input": config.get("input", {}), "quaternion_order": expected["quaternion_order"], "fps": expected["fps"]}
        motion = load_canonical_motion(motion_path, loader_config, simulator="offline")
        if motion.body_positions is None and motion.end_effector_positions is None and motion.dof_pos is not None:
            self.warnings.append(
                f"{motion.name}: dof_pos is present but no robot model/FK body trajectory is available; "
                "end-effector and contact-position metrics will be unavailable."
            )
        return motion
