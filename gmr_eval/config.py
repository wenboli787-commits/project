from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


DEFAULT_CONFIG: Dict[str, Any] = {
    "original_dir": "/mnt/d/GMR_WORK/final use mode",
    "methods": {
        "Direct Mapping": {"dir": "/mnt/d/GMR_WORK/GMR/outputs/final product/pkl direct"},
        "Basic IK": {"dir": "/mnt/d/GMR_WORK/GMR/outputs/final product/pkl Basic IK"},
        "GMR": {"dir": "/mnt/d/GMR_WORK/GMR/outputs/final product/pkl"},
    },
    "robot_xml": "/mnt/d/GMR_WORK/GMR/assets/unitree_g1/g1_mocap_29dof.xml",
    "output_dir": "/mnt/d/GMR_WORK/GMR/outputs/evaluation_results",
    "name_regex": r"^([0-9]+_[0-9]+)",
    "default_fps": 30.0,
    "target_fps": 30.0,
    "sync_mode": "resample",
    "pkl_quaternion_order": "xyzw",
    "human_quaternion_order": "wxyz",
    "floor_height": 0.0,
    "compare_keypoints": [
        "pelvis",
        "torso",
        "head",
        "left_hand",
        "right_hand",
        "left_knee",
        "right_knee",
        "left_foot",
        "right_foot",
    ],
    "success_thresholds": {
        "min_completion_fraction": 0.9,
        "min_root_height_m": 0.45,
        "max_abs_roll_pitch_deg": 60.0,
        "max_ground_penetration_m": 0.08,
        "max_self_collision_count": 20,
    },
    "thresholds": {
        "foot_contact_height_m": 0.04,
        "foot_sliding_velocity_mps": 0.10,
        "sudden_jump_abs_velocity": 30.0,
        "sudden_jump_std_factor": 3.0,
    },
    "alignment": {
        "initial_root": True,
        "initial_heading": True,
        "scale": True,
    },
    "overall_score_weights": {
        "success": 0.25,
        "root_relative_error": 0.20,
        "global_error": 0.15,
        "foot_sliding": 0.15,
        "ground_penetration": 0.10,
        "sudden_jumps": 0.10,
        "self_collision": 0.05,
    },
}


def load_config(path: str | Path | None) -> Dict[str, Any]:
    """Load YAML config and merge it over defaults."""
    config = deep_copy(DEFAULT_CONFIG)
    if path:
        cfg_path = Path(path).expanduser()
        if cfg_path.exists():
            text = cfg_path.read_text(encoding="utf-8")
            loaded = _load_yaml(text)
            if loaded:
                deep_update(config, loaded)
    return config


def apply_cli_overrides(config: Dict[str, Any], args: Any) -> Dict[str, Any]:
    """Apply command-line paths and options over the config."""
    if getattr(args, "original_dir", None):
        config["original_dir"] = args.original_dir
    if getattr(args, "direct_dir", None):
        config.setdefault("methods", {}).setdefault("Direct Mapping", {})["dir"] = args.direct_dir
    if getattr(args, "ik_dir", None):
        config.setdefault("methods", {}).setdefault("Basic IK", {})["dir"] = args.ik_dir
    if getattr(args, "gmr_dir", None):
        config.setdefault("methods", {}).setdefault("GMR", {})["dir"] = args.gmr_dir
    if getattr(args, "robot_xml", None):
        config["robot_xml"] = args.robot_xml
    if getattr(args, "output_dir", None):
        config["output_dir"] = args.output_dir
    if getattr(args, "name_regex", None):
        config["name_regex"] = args.name_regex
    if getattr(args, "sync_mode", None):
        config["sync_mode"] = args.sync_mode
    if getattr(args, "target_fps", None):
        config["target_fps"] = float(args.target_fps)
    return config


def deep_update(base: Dict[str, Any], other: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in other.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_update(base[key], value)
        else:
            base[key] = value
    return base


def deep_copy(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: deep_copy(v) for k, v in value.items()}
    if isinstance(value, list):
        return [deep_copy(v) for v in value]
    return value


def _load_yaml(text: str) -> Dict[str, Any]:
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
        return data or {}
    except Exception:
        return _simple_yaml_load(text)


def _simple_yaml_load(text: str) -> Dict[str, Any]:
    """Small YAML subset parser for the default config shape."""
    lines = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if line.strip():
            lines.append(line)

    def indent(line: str) -> int:
        return len(line) - len(line.lstrip(" "))

    def parse_value(value: str) -> Any:
        value = value.strip()
        if value in {"", "null", "None", "~"}:
            return None
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            if not inner:
                return []
            return [parse_value(part.strip()) for part in inner.split(",")]
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            return value[1:-1]
        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            return value

    def parse_block(index: int, level: int) -> tuple[Any, int]:
        if index < len(lines) and lines[index].lstrip().startswith("- ") and indent(lines[index]) == level:
            values = []
            while index < len(lines) and indent(lines[index]) == level and lines[index].lstrip().startswith("- "):
                values.append(parse_value(lines[index].lstrip()[2:].strip()))
                index += 1
            return values, index

        result: Dict[str, Any] = {}
        while index < len(lines):
            line = lines[index]
            current = indent(line)
            if current < level:
                break
            if current > level:
                index += 1
                continue
            stripped = line.strip()
            if ":" not in stripped:
                index += 1
                continue
            key, raw_value = stripped.split(":", 1)
            key = key.strip().strip('"').strip("'")
            raw_value = raw_value.strip()
            index += 1
            if raw_value:
                result[key] = parse_value(raw_value)
            elif index < len(lines) and indent(lines[index]) > current:
                result[key], index = parse_block(index, indent(lines[index]))
            else:
                result[key] = {}
        return result, index

    parsed, _ = parse_block(0, 0)
    return parsed if isinstance(parsed, dict) else {}
