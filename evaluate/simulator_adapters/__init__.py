"""Simulator-specific ingestion adapters."""

from simulator_adapters.base_adapter import SimulatorAdapter
from simulator_adapters.isaac_adapter import IsaacAdapter
from simulator_adapters.mujoco_adapter import MuJoCoAdapter
from simulator_adapters.offline_adapter import OfflineAdapter


def create_adapter(simulator: str, robot_model=None):
    name = simulator.lower()
    if name == "mujoco":
        return MuJoCoAdapter(robot_model)
    if name in {"isaac", "isaac_sim", "isaac_lab"}:
        return IsaacAdapter(robot_model)
    if name == "offline":
        return OfflineAdapter(robot_model)
    raise ValueError("--simulator must be one of: mujoco, isaac, offline.")


__all__ = ["SimulatorAdapter", "MuJoCoAdapter", "IsaacAdapter", "OfflineAdapter", "create_adapter"]
