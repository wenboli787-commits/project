import argparse
import copy
import pickle
import sys
import time
from pathlib import Path


GMR_ROOT = Path(__file__).resolve().parents[1]
WORK_ROOT = GMR_ROOT.parent
ASSETS_DIR = GMR_ROOT / "assets"
DEFAULT_MOTION_DIR = (
    WORK_ROOT / "ubisoft-laforge-animation-dataset" / "lafan1" / "extracted"
)
DEFAULT_MOTION_NAME = "dance1_subject2.bvh"
METHOD_NAME = "direct_mapping"

if str(GMR_ROOT) not in sys.path:
    sys.path.insert(0, str(GMR_ROOT))

from general_motion_retargeting.utils.motion_source import (
    add_motion_source_args,
    load_motion_source,
    resolve_motion_path,
    validate_motion_source_targets,
)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Directly map BVH, SMPL-X/AMASS npz, or 3D joint motion to a MuJoCo robot."
    )
    add_motion_source_args(parser, DEFAULT_MOTION_DIR, DEFAULT_MOTION_NAME)
    parser.add_argument("--robot", default="unitree_g1", help="GMR robot name.")
    parser.add_argument("--motion_fps", type=int, default=30)
    parser.add_argument("--save_path", type=Path, default=None)
    parser.add_argument("--no_visualize", action="store_true")
    parser.add_argument("--rate_limit", action="store_true")
    parser.add_argument("--record_video", action="store_true")
    parser.add_argument("--video_path", type=Path, default=None)
    parser.add_argument("--max_frames", type=int, default=None)
    parser.add_argument("--direct_gain", type=float, default=1.0)
    parser.add_argument(
        "--clip_joint_limits",
        action="store_true",
        help="Clip mapped joint values to MuJoCo joint ranges.",
    )
    parser.add_argument(
        "--check_paths_only",
        action="store_true",
        help="Only print and check GMR/assets/motion paths, without importing GMR dependencies.",
    )
    parser.add_argument("--quiet", action="store_true")
    return parser


def default_save_path(robot, motion_path):
    out_dir = GMR_ROOT / "outputs" / "direct_mapping"
    return out_dir / f"{motion_path.stem}_{robot}_direct_mapping.pkl"


def check_paths(args):
    motion_path = resolve_motion_path(args)
    print(f"GMR_ROOT   : {GMR_ROOT}")
    print(f"ASSETS_DIR : {ASSETS_DIR}")
    print(f"MOTION_DIR : {args.motion_dir}")
    print(f"MOTION_FILE: {motion_path}")
    print(f"assets exists: {ASSETS_DIR.exists()}")
    print(f"motion exists: {motion_path.exists()}")
    if not ASSETS_DIR.exists():
        raise FileNotFoundError(f"Robot assets directory not found: {ASSETS_DIR}")
    if not motion_path.exists():
        raise FileNotFoundError(f"Motion file not found: {motion_path}")


def deep_copy_human_frame(frame):
    return copy.deepcopy(frame)


def load_runtime_modules():
    import mujoco as mj
    import numpy as np
    from scipy.spatial.transform import Rotation as R

    from general_motion_retargeting import GeneralMotionRetargeting as GMR
    from general_motion_retargeting import RobotMotionViewer
    from general_motion_retargeting.params import IK_CONFIG_DICT, ROBOT_XML_DICT

    return mj, np, R, GMR, RobotMotionViewer, IK_CONFIG_DICT, ROBOT_XML_DICT


class DirectMapper:
    def __init__(
        self,
        mj,
        np,
        rotation_cls,
        retargeter,
        robot,
        gain,
        clip_joint_limits,
        parent_map,
    ):
        self.mj = mj
        self.np = np
        self.R = rotation_cls
        self.retargeter = retargeter
        self.model = retargeter.model
        self.robot = robot
        self.gain = gain
        self.clip_joint_limits = clip_joint_limits
        self.parent_map = parent_map
        self.children_by_body = self._build_body_children()
        self.robot_body_to_human = self._collect_robot_body_matches()
        self.joint_mappings = self._build_joint_mappings()

        self.initial_qpos = None
        self.initial_human = None
        self.initial_root_pos = None
        self.initial_root_rot = None
        self.initial_local_rots = {}
        self.scaled_human_data = None

    def reset(self, initial_qpos, initial_human_frame):
        self.initial_qpos = self.np.asarray(initial_qpos, dtype=float).copy()
        self.initial_human = self.prepare_human_frame(initial_human_frame)
        self.initial_root_pos, self.initial_root_rot = self._root_pose(self.initial_human)
        self.initial_local_rots = {}
        for _, _, _, human_body, _, _ in self.joint_mappings:
            if human_body in self.initial_human and human_body not in self.initial_local_rots:
                self.initial_local_rots[human_body] = self._local_rotation(
                    self.initial_human, human_body
                )

    def prepare_human_frame(self, human_frame):
        self.retargeter.update_targets(deep_copy_human_frame(human_frame))
        prepared = deep_copy_human_frame(self.retargeter.scaled_human_data)
        self.scaled_human_data = prepared
        return prepared

    def retarget(self, human_frame, frame_index):
        if frame_index == 0:
            self.scaled_human_data = self.initial_human
            return self.initial_qpos.copy()

        human = self.prepare_human_frame(human_frame)
        qpos = self.initial_qpos.copy()

        root_pos, root_rot = self._root_pose(human)
        root_delta_pos = root_pos - self.initial_root_pos
        root_delta_rot = root_rot * self.initial_root_rot.inv()
        initial_robot_root_rot = self.R.from_quat(qpos[3:7], scalar_first=True)

        qpos[:3] = self.initial_qpos[:3] + root_delta_pos
        qpos[3:7] = (root_delta_rot * initial_robot_root_rot).as_quat(scalar_first=True)

        for joint_id, qpos_addr, axis, human_body, joint_name, robot_body in self.joint_mappings:
            if human_body not in human or human_body not in self.initial_local_rots:
                continue
            local_rot = self._local_rotation(human, human_body)
            delta_rot = local_rot * self.initial_local_rots[human_body].inv()
            angle = float(self.np.dot(delta_rot.as_rotvec(), axis))
            qpos[qpos_addr] = self.initial_qpos[qpos_addr] + self.gain * angle

            if self.clip_joint_limits and self.model.jnt_limited[joint_id]:
                lower, upper = self.model.jnt_range[joint_id]
                qpos[qpos_addr] = self.np.clip(qpos[qpos_addr], lower, upper)

        return qpos

    def _collect_robot_body_matches(self):
        matches = {}
        for table in (self.retargeter.ik_match_table2, self.retargeter.ik_match_table1):
            for robot_body, entry in table.items():
                human_body, pos_weight, rot_weight, _, _ = entry
                if pos_weight == 0 and rot_weight == 0:
                    continue
                matches.setdefault(robot_body, human_body)
        return matches

    def _build_body_children(self):
        children = {body_id: [] for body_id in range(self.model.nbody)}
        for body_id in range(1, self.model.nbody):
            parent_id = int(self.model.body_parentid[body_id])
            children[parent_id].append(body_id)
        return children

    def _build_joint_mappings(self):
        mappings = []
        for joint_id in range(self.model.njnt):
            if self.model.jnt_type[joint_id] != self.mj.mjtJoint.mjJNT_HINGE:
                continue
            robot_body_id = int(self.model.jnt_bodyid[joint_id])
            matched_body, human_body = self._nearest_descendant_match(robot_body_id)
            if human_body is None:
                continue

            axis = self.np.asarray(self.model.jnt_axis[joint_id], dtype=float)
            axis_norm = self.np.linalg.norm(axis)
            if axis_norm < 1e-8:
                continue
            axis = axis / axis_norm
            joint_name = self.mj.mj_id2name(self.model, self.mj.mjtObj.mjOBJ_JOINT, joint_id)
            robot_body = self.mj.mj_id2name(self.model, self.mj.mjtObj.mjOBJ_BODY, robot_body_id)
            mappings.append(
                (
                    joint_id,
                    int(self.model.jnt_qposadr[joint_id]),
                    axis,
                    human_body,
                    joint_name,
                    matched_body or robot_body,
                )
            )
        if not mappings:
            raise RuntimeError("No direct joint mappings were built for this robot.")
        return mappings

    def _nearest_descendant_match(self, body_id):
        queue = [body_id]
        seen = set()
        while queue:
            current = queue.pop(0)
            if current in seen:
                continue
            seen.add(current)
            body_name = self.mj.mj_id2name(self.model, self.mj.mjtObj.mjOBJ_BODY, current)
            if body_name in self.robot_body_to_human:
                return body_name, self.robot_body_to_human[body_name]
            queue.extend(self.children_by_body.get(current, []))
        return None, None

    def _root_pose(self, human):
        root_pos, root_quat = human[self.retargeter.human_root_name]
        return self.np.asarray(root_pos, dtype=float), self.R.from_quat(
            root_quat, scalar_first=True
        )

    def _available_parent(self, human, body_name):
        parent = self.parent_map.get(body_name)
        while parent is not None:
            if parent in human:
                return parent
            parent = self.parent_map.get(parent)
        return None

    def _local_rotation(self, human, body_name):
        body_rot = self.R.from_quat(human[body_name][1], scalar_first=True)
        parent_name = self._available_parent(human, body_name)
        if parent_name is None:
            return body_rot
        parent_rot = self.R.from_quat(human[parent_name][1], scalar_first=True)
        return parent_rot.inv() * body_rot


def save_motion(np, save_path, qpos_list, fps, metadata):
    save_path.parent.mkdir(parents=True, exist_ok=True)
    root_pos = np.asarray([qpos[:3] for qpos in qpos_list])
    root_rot = np.asarray([qpos[3:7][[1, 2, 3, 0]] for qpos in qpos_list])
    dof_pos = np.asarray([qpos[7:] for qpos in qpos_list])
    motion_data = {
        "fps": fps,
        "root_pos": root_pos,
        "root_rot": root_rot,
        "dof_pos": dof_pos,
        "local_body_pos": None,
        "link_body_list": None,
        "metadata": metadata,
    }
    with open(save_path, "wb") as f:
        pickle.dump(motion_data, f)


def main():
    argv = [arg for arg in sys.argv[1:] if arg.strip()]
    args = build_parser().parse_args(argv)
    check_paths(args)
    if args.check_paths_only:
        return

    (
        mj,
        np,
        R,
        GMR,
        RobotMotionViewer,
        IK_CONFIG_DICT,
        ROBOT_XML_DICT,
    ) = load_runtime_modules()

    motion_source = load_motion_source(args, GMR_ROOT)
    src_human = motion_source.src_human
    if args.robot not in IK_CONFIG_DICT[src_human]:
        supported = ", ".join(sorted(IK_CONFIG_DICT[src_human].keys()))
        raise ValueError(
            f"Robot '{args.robot}' is not supported for source '{src_human}'. "
            f"Supported: {supported}"
        )
    validate_motion_source_targets(motion_source, IK_CONFIG_DICT[src_human][args.robot])

    robot_xml = Path(ROBOT_XML_DICT[args.robot]).resolve()
    if ASSETS_DIR.resolve() not in robot_xml.parents:
        raise RuntimeError(f"Robot XML is not under expected assets dir: {robot_xml}")

    save_path = args.save_path or default_save_path(args.robot, motion_source.path)
    save_path = save_path.expanduser().resolve()

    frames = motion_source.frames
    if args.max_frames is not None:
        frames = frames[: args.max_frames]
    if not frames:
        raise RuntimeError(f"No frames loaded from {motion_source.path}")

    seed_gmr = GMR(
        src_human=src_human,
        tgt_robot=args.robot,
        actual_human_height=motion_source.actual_human_height,
        verbose=not args.quiet,
    )
    initial_qpos = seed_gmr.retarget(deep_copy_human_frame(frames[0]))

    mapper = DirectMapper(
        mj=mj,
        np=np,
        rotation_cls=R,
        retargeter=seed_gmr,
        robot=args.robot,
        gain=args.direct_gain,
        clip_joint_limits=args.clip_joint_limits,
        parent_map=motion_source.parent_map,
    )
    mapper.reset(initial_qpos, frames[0])
    if not args.quiet:
        print(f"[direct] mapped hinge joints: {len(mapper.joint_mappings)}")
        print(f"[direct] source: {motion_source.motion_format} -> {src_human}")

    viewer = None
    if not args.no_visualize:
        viewer = RobotMotionViewer(
            robot_type=args.robot,
            motion_fps=motion_source.fps,
            transparent_robot=0,
            record_video=args.record_video,
            video_path=str(args.video_path or (GMR_ROOT / "videos" / f"{motion_source.path.stem}_{args.robot}_direct.mp4")),
        )

    qpos_list = []
    start_time = time.time()
    try:
        for frame_index, frame in enumerate(frames):
            qpos = mapper.retarget(frame, frame_index)
            qpos_list.append(qpos.copy())
            if viewer is not None:
                viewer.step(
                    root_pos=qpos[:3],
                    root_rot=qpos[3:7],
                    dof_pos=qpos[7:],
                    human_motion_data=mapper.scaled_human_data,
                    rate_limit=args.rate_limit,
                    follow_camera=True,
                )
            if not args.quiet and frame_index % 100 == 0:
                print(f"[direct] frame {frame_index + 1}/{len(frames)}")
    finally:
        if viewer is not None:
            viewer.close()

    metadata = {
        "method": METHOD_NAME,
        "robot": args.robot,
        "source_motion": str(motion_source.path),
        "source_format": motion_source.motion_format,
        "src_human": src_human,
        "source_metadata": motion_source.metadata,
        "motion_fps": motion_source.fps,
        "first_frame_seed": "GMR initial_qpos from the same motion frame 0",
        "direct_gain": args.direct_gain,
        "clip_joint_limits": args.clip_joint_limits,
        "mapped_joint_count": len(mapper.joint_mappings),
    }
    save_motion(np, save_path, qpos_list, motion_source.fps, metadata)
    elapsed = time.time() - start_time
    print(f"[direct] saved: {save_path}")
    print(f"[direct] frames: {len(qpos_list)}, robot_xml: {robot_xml}")
    print(f"[direct] elapsed: {elapsed:.2f}s")


if __name__ == "__main__":
    main()
