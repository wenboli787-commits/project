# Ubuntu 22.04 多格式动作重定向完整操作文档

本文档按 **Ubuntu 22.04** 使用场景编写。后续所有仿真、动作重定向、MuJoCo viewer 打开、pkl 生成和三种方法对比，都建议在 Ubuntu 终端中完成。

当前支持三种重定向方法使用统一动作输入：

```text
1. GMR 原方法
2. Direct mapping
3. Basic IK retargeting
```

当前支持的动作文件类型：

```text
.bvh        LAFAN1 BVH
.npz        SMPL-X stageii
.npz        AMASS
.npy        Human 3D 关节点位置
.npz        Human 3D 关节点位置
```

新增和修改的主要文件：

```text
GMR/scripts/motion_to_robot.py
GMR/general_motion_retargeting/utils/motion_source.py
GMR/direct mapping/run_direct_mapping.py
GMR/Basic IK retargeting/run_basic_ik_retargeting.py
GMR/scripts/setup_multiformat_retargeting_ubuntu22_04.sh
```

## 1. Ubuntu 路径约定

如果你的工程仍放在 Windows 的 `D:` 盘，并通过 Ubuntu/WSL 访问，路径要写成 Linux 风格：

```text
Windows 路径:
D:\GMR_WORK\GMR

Ubuntu 路径:
/mnt/d/GMR_WORK/GMR
```

本文默认工程目录是：

```bash
cd /mnt/d/GMR_WORK/GMR
```

LAFAN1 BVH 默认动作目录是：

```text
/mnt/d/GMR_WORK/ubisoft-laforge-animation-dataset/lafan1/extracted
```

机器人模型目录是：

```text
/mnt/d/GMR_WORK/GMR/assets
```

如果你把工程复制到了 Ubuntu 原生目录，例如：

```text
~/GMR_WORK/GMR
```

那么所有命令里的 `/mnt/d/GMR_WORK/GMR` 换成你的实际路径即可。

## 2. 第一次环境安装

进入工程目录：

```bash
cd /mnt/d/GMR_WORK/GMR
```

先安装 Ubuntu 系统依赖。MuJoCo viewer 需要 OpenGL/GLFW 相关库：

```bash
sudo apt update
sudo apt install -y \
  build-essential \
  cmake \
  git \
  ffmpeg \
  libgl1-mesa-dev \
  libglfw3 \
  libglfw3-dev \
  libglew-dev \
  libosmesa6-dev \
  libx11-6 \
  libxext6 \
  libxrender1 \
  libxi6 \
  libxrandr2 \
  libxinerama1 \
  libxcursor1 \
  patchelf
```

然后安装 Python 环境。推荐使用 conda：

```bash
bash scripts/setup_multiformat_retargeting_ubuntu22_04.sh gmr
conda activate gmr
```

这个脚本会执行：

```text
1. 创建 Python 3.10 conda 环境；
2. pip install -e 当前 GMR 工程；
3. 安装 qpsolvers、daqp；
4. 安装 libstdcxx-ng；
5. 检查 numpy/scipy/mujoco/mink/smplx/qpsolvers/daqp 是否可导入。
```

如果你不想使用 conda，也可以用 venv，但 conda 更省心：

```bash
cd /mnt/d/GMR_WORK/GMR
python3.10 -m venv .venv_gmr
source .venv_gmr/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e .
python -m pip install "qpsolvers[daqp,proxqp]" daqp
```

## 3. 检查 Python 依赖

激活环境后运行：

```bash
python - <<'PY'
import importlib.util

for name in ["numpy", "scipy", "mujoco", "mink", "smplx", "qpsolvers", "daqp"]:
    print(f"{name:10s}", importlib.util.find_spec(name) is not None)
PY
```

正常应接近：

```text
numpy      True
scipy      True
mujoco     True
mink       True
smplx      True
qpsolvers  True
daqp       True
```

如果 `smplx` 是 `False`，说明 SMPL-X Python 包没有安装成功。重新执行：

```bash
python -m pip install -e .
```

如果网络无法访问 GitHub，`smplx @ git+https://github.com/vchoutas/smplx` 可能安装失败，需要先解决网络，或手动安装 smplx 包。

## 4. SMPL-X Body Model

SMPL-X/AMASS `.npz` 需要 SMPL-X body model 文件。默认读取：

```text
/mnt/d/GMR_WORK/GMR/assets/body_models
```

一般目录结构类似：

```text
assets/body_models/smplx/
```

如果你的 body model 放在其他目录，运行时加：

```bash
--smplx_body_model_path /path/to/body_models
```

如果 body model 缺失，SMPL-X/AMASS 会在加载阶段失败；BVH 和普通 3D 关节点不需要 body model。

## 5. 三种方法的统一入口

现在三种方法都可以用同一套动作参数：

| 方法 | 脚本 | 输出目录 |
|---|---|---|
| GMR 原方法 | `scripts/motion_to_robot.py` | `outputs/gmr/` |
| Direct mapping | `direct mapping/run_direct_mapping.py` | `outputs/direct_mapping/` |
| Basic IK | `Basic IK retargeting/run_basic_ik_retargeting.py` | `outputs/basic_ik_retargeting/` |

共同输入参数：

```text
--motion_file              动作文件完整路径
--motion_format            auto / bvh_lafan1 / smplx_npz / amass_npz / joint_positions_npy / joint_positions_npz
--motion_fps               目标 fps，默认 30
--start_frame              起始帧
--end_frame                结束帧
--max_frames               最多处理帧数
--actual_human_height      手动指定人体身高，单位米
--save_path                指定输出 pkl 路径
--no_visualize             只生成 pkl，不打开 MuJoCo viewer
--rate_limit               打开 viewer 时按动作 fps 限速播放
--record_video             录制视频
--video_path               指定视频路径
--check_paths_only         只检查路径，不导入完整仿真依赖
```

普通 Human 3D 关节点额外常用：

```text
--joint_array_key          npz 里关节点数组的 key
--joint_skeleton           auto / smplx_22 / h36m_17
--joint_names              逗号分隔的关节名
--joint_names_file         每行一个关节名的 txt
--position_unit            auto / m / cm / mm
--position_scale           额外缩放
--axis_order               坐标轴重排，例如 xyz、xzy、x,z,-y
```

## 6. 推荐运行流程

无论是哪种动作文件，都按这个顺序跑。

第一步，只检查路径：

```bash
python scripts/motion_to_robot.py \
  --motion_file /path/to/motion_file \
  --motion_format auto \
  --check_paths_only
```

看到下面两行都是 `True`，说明路径没错：

```text
assets exists: True
motion exists: True
```

第二步，短跑 30 帧，不打开 viewer：

```bash
python scripts/motion_to_robot.py \
  --motion_file /path/to/motion_file \
  --motion_format auto \
  --robot unitree_g1 \
  --max_frames 30 \
  --no_visualize
```

第三步，Direct mapping 短跑：

```bash
python "direct mapping/run_direct_mapping.py" \
  --motion_file /path/to/motion_file \
  --motion_format auto \
  --robot unitree_g1 \
  --max_frames 30 \
  --no_visualize
```

第四步，Basic IK 短跑：

```bash
python "Basic IK retargeting/run_basic_ik_retargeting.py" \
  --motion_file /path/to/motion_file \
  --motion_format auto \
  --robot unitree_g1 \
  --max_frames 30 \
  --no_visualize
```

第五步，短跑都成功后，再去掉 `--no_visualize` 打开 MuJoCo viewer：

```bash
python scripts/motion_to_robot.py \
  --motion_file /path/to/motion_file \
  --motion_format auto \
  --robot unitree_g1 \
  --rate_limit
```

## 7. BVH 使用方法

BVH 推荐用 LAFAN1 数据，例如：

```text
/mnt/d/GMR_WORK/ubisoft-laforge-animation-dataset/lafan1/extracted/walk1_subject1.bvh
```

GMR 原方法：

```bash
python scripts/motion_to_robot.py \
  --motion_file /mnt/d/GMR_WORK/ubisoft-laforge-animation-dataset/lafan1/extracted/walk1_subject1.bvh \
  --motion_format auto \
  --robot unitree_g1 \
  --max_frames 300 \
  --no_visualize
```

Direct mapping：

```bash
python "direct mapping/run_direct_mapping.py" \
  --motion_file /mnt/d/GMR_WORK/ubisoft-laforge-animation-dataset/lafan1/extracted/walk1_subject1.bvh \
  --motion_format auto \
  --robot unitree_g1 \
  --max_frames 300 \
  --no_visualize
```

Basic IK：

```bash
python "Basic IK retargeting/run_basic_ik_retargeting.py" \
  --motion_file /mnt/d/GMR_WORK/ubisoft-laforge-animation-dataset/lafan1/extracted/walk1_subject1.bvh \
  --motion_format auto \
  --robot unitree_g1 \
  --max_frames 300 \
  --no_visualize
```

也可以继续使用原来的默认目录方式：

```bash
python scripts/motion_to_robot.py \
  --motion_name walk1_subject1.bvh \
  --robot unitree_g1 \
  --no_visualize
```

## 8. SMPL-X Stageii npz 使用方法

SMPL-X stageii 文件通常包含：

```text
gender
pose_body
betas
root_orient
trans
mocap_frame_rate
```

先检查 npz 的 key：

```bash
python - <<'PY'
import numpy as np

path = "/mnt/d/GMR_WORK/GMR/data/smplx_sample/synthetic_smplx_wave_stageii.npz"
data = np.load(path, allow_pickle=True)
print(data.files)
for key in data.files:
    arr = data[key]
    print(key, getattr(arr, "shape", None), getattr(arr, "dtype", None))
PY
```

GMR 原方法：

```bash
python scripts/motion_to_robot.py \
  --motion_file /mnt/d/GMR_WORK/GMR/data/smplx_sample/synthetic_smplx_wave_stageii.npz \
  --motion_format smplx_npz \
  --robot unitree_g1 \
  --motion_fps 30 \
  --max_frames 120 \
  --no_visualize
```

Direct mapping：

```bash
python "direct mapping/run_direct_mapping.py" \
  --motion_file /mnt/d/GMR_WORK/GMR/data/smplx_sample/synthetic_smplx_wave_stageii.npz \
  --motion_format smplx_npz \
  --robot unitree_g1 \
  --motion_fps 30 \
  --max_frames 120 \
  --no_visualize
```

Basic IK：

```bash
python "Basic IK retargeting/run_basic_ik_retargeting.py" \
  --motion_file /mnt/d/GMR_WORK/GMR/data/smplx_sample/synthetic_smplx_wave_stageii.npz \
  --motion_format smplx_npz \
  --robot unitree_g1 \
  --motion_fps 30 \
  --max_frames 120 \
  --no_visualize
```

## 9. AMASS npz 使用方法

AMASS 常见字段：

```text
poses
trans 或 transl
betas
gender
mocap_framerate 或 mocap_frame_rate
```

代码会把 AMASS 的：

```text
poses[:, :3]     -> root_orient
poses[:, 3:66]   -> pose_body
trans/transl     -> trans
```

转换成 SMPL-X loader 可用的结构。

GMR 原方法：

```bash
python scripts/motion_to_robot.py \
  --motion_file /path/to/amass_motion.npz \
  --motion_format amass_npz \
  --robot unitree_g1 \
  --motion_fps 30 \
  --max_frames 120 \
  --no_visualize
```

Direct mapping：

```bash
python "direct mapping/run_direct_mapping.py" \
  --motion_file /path/to/amass_motion.npz \
  --motion_format amass_npz \
  --robot unitree_g1 \
  --motion_fps 30 \
  --max_frames 120 \
  --no_visualize
```

Basic IK：

```bash
python "Basic IK retargeting/run_basic_ik_retargeting.py" \
  --motion_file /path/to/amass_motion.npz \
  --motion_format amass_npz \
  --robot unitree_g1 \
  --motion_fps 30 \
  --max_frames 120 \
  --no_visualize
```

如果 `--motion_format auto` 识别不符合预期，就手动写 `--motion_format amass_npz`。

## 10. Human 3D npy 使用方法

普通 Human 3D `.npy` 通常只有关节点 3D 坐标，没有真实关节旋转。代码会用骨段方向估算 quaternion，所以它能跑通，但效果通常不如 BVH/SMPL-X/AMASS 稳。

支持数组形状：

```text
(frames, joints, 3)
(frames, 3, joints)
(joints, frames, 3)
(joints, 3)
(frames, joints * 3)
```

如果是 Human3.6M 17 关节顺序：

```bash
python scripts/motion_to_robot.py \
  --motion_file /path/to/human3d.npy \
  --motion_format joint_positions_npy \
  --joint_skeleton h36m_17 \
  --position_unit mm \
  --axis_order xyz \
  --actual_human_height 1.75 \
  --robot unitree_g1 \
  --max_frames 120 \
  --no_visualize
```

Direct mapping：

```bash
python "direct mapping/run_direct_mapping.py" \
  --motion_file /path/to/human3d.npy \
  --motion_format joint_positions_npy \
  --joint_skeleton h36m_17 \
  --position_unit mm \
  --axis_order xyz \
  --actual_human_height 1.75 \
  --robot unitree_g1 \
  --max_frames 120 \
  --no_visualize
```

Basic IK：

```bash
python "Basic IK retargeting/run_basic_ik_retargeting.py" \
  --motion_file /path/to/human3d.npy \
  --motion_format joint_positions_npy \
  --joint_skeleton h36m_17 \
  --position_unit mm \
  --axis_order xyz \
  --actual_human_height 1.75 \
  --robot unitree_g1 \
  --max_frames 120 \
  --no_visualize
```

## 11. Human 3D npz 使用方法

Human 3D `.npz` 需要找出关节点数组的 key。代码会自动尝试这些 key：

```text
positions
joints
joint_positions
keypoints3d
keypoints_3d
poses_3d
pose_3d
joints3d
pred_joints
```

先查看 npz 内容：

```bash
python - <<'PY'
import numpy as np

path = "/path/to/human3d.npz"
data = np.load(path, allow_pickle=True)
print(data.files)
for key in data.files:
    arr = data[key]
    print(key, getattr(arr, "shape", None), getattr(arr, "dtype", None))
PY
```

如果关节点数组 key 是 `keypoints3d`：

```bash
python "Basic IK retargeting/run_basic_ik_retargeting.py" \
  --motion_file /path/to/human3d.npz \
  --motion_format joint_positions_npz \
  --joint_array_key keypoints3d \
  --joint_skeleton h36m_17 \
  --position_unit mm \
  --axis_order xyz \
  --robot unitree_g1 \
  --max_frames 120 \
  --no_visualize
```

如果你的关节顺序不是 Human3.6M 17，也不是 SMPL-X 22，需要提供关节名。

直接在命令里写：

```bash
--joint_names pelvis,right_hip,right_knee,right_foot,left_hip,left_knee,left_foot,spine1,spine3,neck,head,left_shoulder,left_elbow,left_wrist,right_shoulder,right_elbow,right_wrist
```

或者写入文本文件：

```bash
cat > /tmp/joint_names.txt <<'EOF'
pelvis
right_hip
right_knee
right_foot
left_hip
left_knee
left_foot
spine1
spine3
neck
head
left_shoulder
left_elbow
left_wrist
right_shoulder
right_elbow
right_wrist
EOF
```

运行时加：

```bash
--joint_names_file /tmp/joint_names.txt
```

## 12. 坐标轴和单位

MuJoCo/GMR 使用 z-up 坐标。很多 Human 3D 数据可能是 y-up、相机坐标或 root-relative 坐标。

单位参数：

```text
--position_unit auto    自动判断 m/cm/mm
--position_unit m       数据单位是米
--position_unit cm      数据单位是厘米
--position_unit mm      数据单位是毫米
```

坐标轴参数：

```text
--axis_order xyz        不变，输出 [x, y, z]
--axis_order xzy        输出 [x, z, y]
--axis_order x,z,-y     输出 [x, z, -y]
--axis_order x,-z,y     输出 [x, -z, y]
```

如果 viewer 中机器人躺倒、倒立、左右反了，优先调整 `--axis_order`。

如果动作非常小或非常大，优先调整：

```text
--position_unit
--position_scale
--actual_human_height
```

## 13. 三种方法同文件对比

下面以一个动作文件变量为例：

```bash
MOTION=/mnt/d/GMR_WORK/ubisoft-laforge-animation-dataset/lafan1/extracted/walk1_subject1.bvh
ROBOT=unitree_g1
```

GMR：

```bash
python scripts/motion_to_robot.py \
  --motion_file "$MOTION" \
  --motion_format auto \
  --robot "$ROBOT" \
  --max_frames 300 \
  --no_visualize \
  --save_path outputs/gmr/walk1_subject1_unitree_g1_gmr.pkl
```

Direct mapping：

```bash
python "direct mapping/run_direct_mapping.py" \
  --motion_file "$MOTION" \
  --motion_format auto \
  --robot "$ROBOT" \
  --max_frames 300 \
  --no_visualize \
  --save_path outputs/direct_mapping/walk1_subject1_unitree_g1_direct_mapping.pkl
```

Basic IK：

```bash
python "Basic IK retargeting/run_basic_ik_retargeting.py" \
  --motion_file "$MOTION" \
  --motion_format auto \
  --robot "$ROBOT" \
  --max_frames 300 \
  --no_visualize \
  --save_path outputs/basic_ik_retargeting/walk1_subject1_unitree_g1_basic_ik.pkl
```

播放生成的 pkl：

```bash
python scripts/vis_robot_motion.py \
  --robot "$ROBOT" \
  --robot_motion_path outputs/gmr/walk1_subject1_unitree_g1_gmr.pkl
```

```bash
python scripts/vis_robot_motion.py \
  --robot "$ROBOT" \
  --robot_motion_path outputs/direct_mapping/walk1_subject1_unitree_g1_direct_mapping.pkl
```

```bash
python scripts/vis_robot_motion.py \
  --robot "$ROBOT" \
  --robot_motion_path outputs/basic_ik_retargeting/walk1_subject1_unitree_g1_basic_ik.pkl
```

## 14. 输出文件说明

默认输出目录：

```text
GMR 原方法:
outputs/gmr/

Direct mapping:
outputs/direct_mapping/

Basic IK:
outputs/basic_ik_retargeting/
```

输出 pkl 内部结构：

```text
fps
root_pos
root_rot
dof_pos
local_body_pos
link_body_list
metadata
```

`metadata` 会记录：

```text
method
robot
source_motion
source_format
src_human
source_metadata
motion_fps
```

这能帮助你之后确认某个结果来自 BVH、SMPL-X、AMASS 还是 Human3D。

## 15. 为什么三种方法初始姿态一致

Direct mapping 和 Basic IK 都会先用 GMR 对同一个动作文件的第 0 帧求：

```text
initial_qpos
```

然后：

```text
Direct mapping 从 initial_qpos 开始做关节增量映射；
Basic IK 从 initial_qpos 开始做无约束 IK；
GMR 原方法自身第 0 帧也是 GMR 求解结果。
```

因此同一个 `--motion_file` 下，三种方法的第一帧机器人姿态保持一致，便于对比后续差异。

## 16. 常见报错和解决

### 16.1 `Motion file not found`

说明 Ubuntu 路径写错。Windows 路径不能直接用于 Ubuntu：

```text
错误:
D:\GMR_WORK\xxx

正确:
/mnt/d/GMR_WORK/xxx
```

### 16.2 `Robot 'xxx' is not supported for source 'smplx'`

说明 `general_motion_retargeting/params.py` 中没有该机器人对应的 IK config。换支持的机器人，或添加新的 `smplx_to_*.json`。

### 16.3 `missing required human bodies`

说明动作文件转换出来的关节点不够，缺少当前 IK config 需要的点。例如 `unitree_g1` 的 SMPL-X 配置通常需要：

```text
pelvis
left_hip
right_hip
left_knee
right_knee
left_foot
right_foot
spine3
left_shoulder
right_shoulder
left_elbow
right_elbow
left_wrist
right_wrist
```

解决方式：

```text
1. 使用 --joint_skeleton h36m_17 或 smplx_22；
2. 使用 --joint_names 或 --joint_names_file 指定正确关节名；
3. 把数据先转换成 SMPL-X/AMASS/BVH；
4. 换一个包含更多人体关节点的数据源。
```

### 16.4 MuJoCo viewer 打不开

如果报 OpenGL、GLFW、display 相关错误，先安装系统依赖：

```bash
sudo apt install -y libgl1-mesa-dev libglfw3 libglfw3-dev libglew-dev libosmesa6-dev
```

如果是在无显示服务器的远程 Ubuntu 上，只生成 pkl：

```bash
--no_visualize
```

如果必须远程看 viewer，需要配置 X11 forwarding、VNC、NoMachine 或 WSLg。

### 16.5 SMPL-X/AMASS 加载失败

优先检查：

```text
1. smplx Python 包是否安装；
2. assets/body_models 是否存在；
3. gender 是否是 male/female/neutral；
4. npz 是否有 pose_body/root_orient/trans 或 poses/trans。
```

### 16.6 Human3D 动作效果很怪

优先检查：

```text
1. 单位是不是 mm/cm/m；
2. 坐标轴是不是 y-up，需要 --axis_order x,z,-y；
3. 关节顺序是不是 h36m_17 或 smplx_22；
4. 数据是不是 root-relative，没有全局位移；
5. 是否缺少脚、手腕、肩膀等关键点。
```

Human3D 只有位置，没有真实关节旋转，所以 Direct mapping 通常比 Basic IK 更敏感。

## 17. 推荐实验顺序

建议你按这个顺序做实验：

```text
1. 先用 LAFAN1 BVH 跑三种方法，确认环境和 viewer 没问题；
2. 再用 SMPL-X stageii npz 跑三种方法，确认 body model 没问题；
3. 再用 AMASS npz 跑三种方法，确认 AMASS 字段兼容；
4. 最后尝试 Human3D npy/npz，并重点调单位、坐标轴和关节名。
```

每个动作文件都先短跑：

```bash
--max_frames 30 --no_visualize
```

确认成功后再完整运行并打开 viewer。

## 18. 最小验收命令

在 Ubuntu 中执行：

```bash
cd /mnt/d/GMR_WORK/GMR
conda activate gmr
```

BVH 路径检查：

```bash
python scripts/motion_to_robot.py \
  --motion_name dance1_subject2.bvh \
  --check_paths_only
```

BVH 三种方法短跑：

```bash
python scripts/motion_to_robot.py \
  --motion_name dance1_subject2.bvh \
  --robot unitree_g1 \
  --max_frames 30 \
  --no_visualize
```

```bash
python "direct mapping/run_direct_mapping.py" \
  --motion_name dance1_subject2.bvh \
  --robot unitree_g1 \
  --max_frames 30 \
  --no_visualize
```

```bash
python "Basic IK retargeting/run_basic_ik_retargeting.py" \
  --motion_name dance1_subject2.bvh \
  --robot unitree_g1 \
  --max_frames 30 \
  --no_visualize
```

SMPL-X 路径检查：

```bash
python scripts/motion_to_robot.py \
  --motion_file /mnt/d/GMR_WORK/GMR/data/smplx_sample/synthetic_smplx_wave_stageii.npz \
  --motion_format auto \
  --check_paths_only
```

SMPL-X 短跑：

```bash
python scripts/motion_to_robot.py \
  --motion_file /mnt/d/GMR_WORK/GMR/data/smplx_sample/synthetic_smplx_wave_stageii.npz \
  --motion_format auto \
  --robot unitree_g1 \
  --max_frames 30 \
  --no_visualize
```

如果以上都成功，说明 Ubuntu 环境、动作读取、机器人模型和重定向链路都基本可用。

## 19. 一键后台验证所有格式

如果你想一次性确认本文档中几种动作格式都能完成 retargeting，可以运行：

```bash
cd /mnt/d/GMR_WORK/GMR
conda activate gmr
python scripts/verify_multiformat_retargeting.py
```

也可以使用 bash 包装脚本：

```bash
bash scripts/verify_multiformat_retargeting_ubuntu22_04.sh
```

这个脚本会验证 5 类动作输入：

```text
1. BVH: data/lafan1_sample/push1_subject2.bvh
2. SMPL-X npz: data/smplx_sample/synthetic_smplx_wave_stageii.npz
3. AMASS npz: 自动生成 data/multiformat_verify/synthetic_amass_verify.npz
4. Human3D npy: 自动生成 data/multiformat_verify/synthetic_h36m17_verify.npy
5. Human3D npz: 自动生成 data/multiformat_verify/synthetic_h36m17_verify.npz
```

每类动作都会跑三种方法：

```text
GMR
Direct mapping
Basic IK
```

也就是总共会跑：

```text
5 种输入格式 × 3 种方法 = 15 个无可视化短测
```

脚本默认参数：

```text
ROBOT=unitree_g1
MAX_FRAMES=5
```

如果要改机器人或帧数：

```bash
python scripts/verify_multiformat_retargeting.py \
  --robot unitree_g1 \
  --max_frames 10
```

后台运行：

```bash
mkdir -p outputs/multiformat_verify
nohup python scripts/verify_multiformat_retargeting.py \
  > outputs/multiformat_verify/verify_all.log 2>&1 &
```

查看后台进度：

```bash
tail -f outputs/multiformat_verify/verify_all.log
```

查看是否还在运行：

```bash
ps -ef | grep verify_multiformat | grep -v grep
```

验证结果输出：

```text
outputs/multiformat_verify/
outputs/multiformat_verify/logs/
```

每个成功的 pkl 文件都会类似：

```text
outputs/multiformat_verify/bvh_lafan1_unitree_g1_gmr.pkl
outputs/multiformat_verify/bvh_lafan1_unitree_g1_direct_mapping.pkl
outputs/multiformat_verify/bvh_lafan1_unitree_g1_basic_ik.pkl
...
```

如果脚本最后输出：

```text
All multiformat retargeting checks completed successfully.
```

说明 BVH、SMPL-X npz、AMASS npz、Human3D npy、Human3D npz 都已经在 Ubuntu 下完成过机器人 retargeting，并且生成了可播放的 robot motion pkl。

如果失败，先看总日志：

```bash
cat outputs/multiformat_verify/verify_all.log
```

再看具体方法和格式的日志：

```bash
ls outputs/multiformat_verify/logs
cat outputs/multiformat_verify/logs/human3d_npy_basic_ik.log
```
