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
METHOD_NAME = "basic_ik_retargeting"

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
        description="Run unconstrained Basic IK retargeting from BVH, SMPL-X/AMASS npz, or 3D joint motion to a MuJoCo robot."
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
    parser.add_argument("--solver", default="daqp")
    parser.add_argument("--damping", type=float, default=5e-1)
    parser.add_argument("--max_iter", type=int, default=10)
    parser.add_argument(
        "--task_table",
        choices=["ik_match_table1", "ik_match_table2"],
        default="ik_match_table2",
        help="Single GMR IK table used by this basic IK baseline.",
    )
    parser.add_argument(
        "--check_paths_only",
        action="store_true",
        help="Only print and check GMR/assets/motion paths, without importing GMR dependencies.",
    )
    parser.add_argument("--quiet", action="store_true")
    return parser


def default_save_path(robot, motion_path):
    out_dir = GMR_ROOT / "outputs" / "basic_ik_retargeting"
    return out_dir / f"{motion_path.stem}_{robot}_basic_ik.pkl"


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
    import mink
    import mujoco as mj
    import numpy as np
    from scipy.spatial.transform import Rotation as R

    from general_motion_retargeting import GeneralMotionRetargeting as GMR
    from general_motion_retargeting import RobotMotionViewer
    from general_motion_retargeting.params import IK_CONFIG_DICT, ROBOT_XML_DICT

    return mink, mj, np, R, GMR, RobotMotionViewer, IK_CONFIG_DICT, ROBOT_XML_DICT


def set_configuration_qpos(mj, configuration, qpos):
    if hasattr(configuration, "update"):
        for kwargs in ({"q": qpos}, {"qpos": qpos}):
            try:
                configuration.update(**kwargs)
                return
            except TypeError:
                pass
        try:
            configuration.update(qpos)
            return
        except TypeError:
            pass
    configuration.data.qpos[:] = qpos
    mj.mj_forward(configuration.model, configuration.data)


def make_basic_ik_class(mink, mj, np, R, GMR):
    class BasicIKRetargeter(GMR):
        def __init__(
            self,
            src_human,
            tgt_robot,
            actual_human_height,
            task_table,
            solver,
            damping,
            max_iter,
            verbose,
        ):
            self.basic_task_table_name = task_table
            self.basic_max_iter = max_iter
            super().__init__(
                src_human=src_human,
                tgt_robot=tgt_robot,
                actual_human_height=actual_human_height,
                solver=solver,
                damping=damping,
                verbose=verbose,
                use_velocity_limit=False,
            )
            self.ik_limits = []
            self.return_initial_once = False

        def setup_retarget_configuration(self):
            self.configuration = mink.Configuration(self.model)
            self.basic_tasks = []
            self.basic_human_body_to_tasks = {}
            self.basic_pos_offsets = {}
            self.basic_rot_offsets = {}

            for table in (self.ik_match_table1, self.ik_match_table2):
                for _, entry in table.items():
                    body_name, _, _, pos_offset, rot_offset = entry
                    self.basic_pos_offsets.setdefault(
                        body_name, np.asarray(pos_offset) - self.ground
                    )
                    self.basic_rot_offsets.setdefault(
                        body_name, R.from_quat(rot_offset, scalar_first=True)
                    )

            selected_table = getattr(self, self.basic_task_table_name)
            for frame_name, entry in selected_table.items():
                body_name, pos_weight, rot_weight, pos_offset, rot_offset = entry
                if pos_weight == 0 and rot_weight == 0:
                    continue
                task = mink.FrameTask(
                    frame_name=frame_name,
                    frame_type="body",
                    position_cost=pos_weight,
                    orientation_cost=rot_weight,
                    lm_damping=1,
                )
                self.basic_human_body_to_tasks.setdefault(body_name, []).append(task)
                self.basic_tasks.append(task)
            if not self.basic_tasks:
                raise RuntimeError(f"No IK tasks were created from {self.basic_task_table_name}.")

        def reset_to_qpos(self, qpos):
            set_configuration_qpos(mj, self.configuration, qpos)
            self.return_initial_once = True

        def update_targets(self, human_data, offset_to_ground=False):
            human_data = self.to_numpy(human_data)
            human_data = self.scale_human_data(
                human_data,
                self.human_root_name,
                self.human_scale_table,
            )
            human_data = self.offset_basic_human_data(human_data)
            human_data = self.apply_ground_offset(human_data)
            if offset_to_ground:
                human_data = self.offset_human_data_to_ground(human_data)
            self.scaled_human_data = human_data

            for body_name, tasks in self.basic_human_body_to_tasks.items():
                pos, rot = human_data[body_name]
                target = mink.SE3.from_rotation_and_translation(mink.SO3(rot), pos)
                for task in tasks:
                    task.set_target(target)

        def offset_basic_human_data(self, human_data):
            offset_human_data = {}
            for body_name, (pos, quat) in human_data.items():
                rot_offset = self.basic_rot_offsets.get(body_name, R.identity())
                pos_offset = self.basic_pos_offsets.get(body_name, -self.ground)
                updated_quat = (
                    R.from_quat(quat, scalar_first=True) * rot_offset
                ).as_quat(scalar_first=True)
                global_pos_offset = R.from_quat(
                    updated_quat, scalar_first=True
                ).apply(pos_offset)
                offset_human_data[body_name] = [
                    pos + global_pos_offset,
                    updated_quat,
                ]
            return offset_human_data

        def retarget(self, human_data, offset_to_ground=False):
            self.update_targets(deep_copy_human_frame(human_data), offset_to_ground)
            if self.return_initial_once:
                self.return_initial_once = False
                return self.configuration.data.qpos.copy()

            current_error = self.error()
            for _ in range(self.basic_max_iter):
                dt = self.configuration.model.opt.timestep
                velocity = mink.solve_ik(
                    self.configuration,
                    self.basic_tasks,
                    dt,
                    self.solver,
                    self.damping,
                    self.ik_limits,
                )
                self.configuration.integrate_inplace(velocity, dt)
                next_error = self.error()
                if current_error - next_error <= 0.001:
                    break
                current_error = next_error

            return self.configuration.data.qpos.copy()

        def error(self):
            return np.linalg.norm(
                np.concatenate(
                    [task.compute_error(self.configuration) for task in self.basic_tasks]
                )
            )

    return BasicIKRetargeter


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
        mink,
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

    BasicIKRetargeter = make_basic_ik_class(mink, mj, np, R, GMR)
    retargeter = BasicIKRetargeter(
        src_human=src_human,
        tgt_robot=args.robot,
        actual_human_height=motion_source.actual_human_height,
        task_table=args.task_table,
        solver=args.solver,
        damping=args.damping,
        max_iter=args.max_iter,
        verbose=not args.quiet,
    )
    retargeter.reset_to_qpos(initial_qpos)
    if not args.quiet:
        print(f"[basic_ik] tasks: {len(retargeter.basic_tasks)} from {args.task_table}")
        print(f"[basic_ik] source: {motion_source.motion_format} -> {src_human}")

    viewer = None
    if not args.no_visualize:
        viewer = RobotMotionViewer(
            robot_type=args.robot,
            motion_fps=motion_source.fps,
            transparent_robot=0,
            record_video=args.record_video,
            video_path=str(args.video_path or (GMR_ROOT / "videos" / f"{motion_source.path.stem}_{args.robot}_basic_ik.mp4")),
        )

    qpos_list = []
    start_time = time.time()
    try:
        for frame_index, frame in enumerate(frames):
            qpos = retargeter.retarget(frame)
            qpos_list.append(qpos.copy())
            if viewer is not None:
                viewer.step(
                    root_pos=qpos[:3],
                    root_rot=qpos[3:7],
                    dof_pos=qpos[7:],
                    human_motion_data=retargeter.scaled_human_data,
                    rate_limit=args.rate_limit,
                    follow_camera=True,
                )
            if not args.quiet and frame_index % 100 == 0:
                print(f"[basic_ik] frame {frame_index + 1}/{len(frames)}")
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
        "task_table": args.task_table,
        "solver": args.solver,
        "damping": args.damping,
        "max_iter": args.max_iter,
        "limits": "none: no mink.ConfigurationLimit and no mink.VelocityLimit",
        "task_count": len(retargeter.basic_tasks),
    }
    save_motion(np, save_path, qpos_list, motion_source.fps, metadata)
    elapsed = time.time() - start_time
    print(f"[basic_ik] saved: {save_path}")
    print(f"[basic_ik] frames: {len(qpos_list)}, robot_xml: {robot_xml}")
    print(f"[basic_ik] elapsed: {elapsed:.2f}s")


if __name__ == "__main__":
    main()
