"""Offline Isaac Sim / Isaac Lab log adapter; it does not import Isaac."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from canonical_motion import CanonicalMotion
from loaders import load_canonical_motion
from simulator_adapters.base_adapter import SimulatorAdapter


class IsaacAdapter(SimulatorAdapter):
    def load_motion(self, motion_path: Path, config: dict[str, Any]) -> CanonicalMotion:
        expected = dict(config.get("isaac", {}).get("expected_keys", {}))
        expected["quaternion_order"] = config.get("input", {}).get("quaternion_order", "xyzw")
        expected["fps"] = config.get("input", {}).get("fps", 30.0)
        loader_config = {"expected_keys": expected, "input": config.get("input", {}), "quaternion_order": expected["quaternion_order"], "fps": expected["fps"]}
        motion = load_canonical_motion(motion_path, loader_config, simulator="isaac")
        limits = config.get("isaac", {}).get("dof_limits", {})
        if motion.dof_limits_lower is None and isinstance(limits, dict) and limits.get("lower") is not None:
            motion.dof_limits_lower = np.asarray(limits["lower"], dtype=float)
            motion.dof_limits_upper = np.asarray(limits.get("upper"), dtype=float)
        if motion.body_positions is None and motion.dof_pos is not None:
            self.warnings.append(
                f"{motion.name}: Isaac offline log has no rigid_body_state/body_positions. "
                "The evaluator will retain joint-space metrics and mark FK-dependent metrics unavailable."
            )
        return motion
