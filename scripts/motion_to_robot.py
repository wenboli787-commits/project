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
METHOD_NAME = "gmr"

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
        description="Run GMR retargeting from BVH, SMPL-X/AMASS npz, or 3D joint motion to a MuJoCo robot."
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
    parser.add_argument(
        "--check_paths_only",
        action="store_true",
        help="Only print and check GMR/assets/motion paths, without importing GMR dependencies.",
    )
    parser.add_argument("--quiet", action="store_true")
    return parser


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


def default_save_path(robot, motion_path):
    out_dir = GMR_ROOT / "outputs" / "gmr"
    return out_dir / f"{motion_path.stem}_{robot}_gmr.pkl"


def deep_copy_human_frame(frame):
    return copy.deepcopy(frame)


def load_runtime_modules():
    import numpy as np

    from general_motion_retargeting import GeneralMotionRetargeting as GMR
    from general_motion_retargeting import RobotMotionViewer
    from general_motion_retargeting.params import IK_CONFIG_DICT, ROBOT_XML_DICT

    return np, GMR, RobotMotionViewer, IK_CONFIG_DICT, ROBOT_XML_DICT


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

    np, GMR, RobotMotionViewer, IK_CONFIG_DICT, ROBOT_XML_DICT = load_runtime_modules()

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

    retargeter = GMR(
        src_human=src_human,
        tgt_robot=args.robot,
        actual_human_height=motion_source.actual_human_height,
        verbose=not args.quiet,
    )

    viewer = None
    if not args.no_visualize:
        viewer = RobotMotionViewer(
            robot_type=args.robot,
            motion_fps=motion_source.fps,
            transparent_robot=0,
            record_video=args.record_video,
            video_path=str(
                args.video_path
                or (GMR_ROOT / "videos" / f"{motion_source.path.stem}_{args.robot}_gmr.mp4")
            ),
        )

    qpos_list = []
    start_time = time.time()
    try:
        for frame_index, frame in enumerate(frames):
            qpos = retargeter.retarget(deep_copy_human_frame(frame))
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
                print(f"[gmr] frame {frame_index + 1}/{len(frames)}")
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
    }
    save_motion(np, save_path, qpos_list, motion_source.fps, metadata)
    elapsed = time.time() - start_time
    print(f"[gmr] saved: {save_path}")
    print(f"[gmr] frames: {len(qpos_list)}, robot_xml: {robot_xml}")
    print(f"[gmr] elapsed: {elapsed:.2f}s")


if __name__ == "__main__":
    main()
