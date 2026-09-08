# Basic IK Retargeting Ubuntu 使用说明

本文只保留 Basic IK 的快速入口。完整多格式说明见：

```text
GMR/MULTI_FORMAT_MOTION_RETARGETING_CN.md
```

## 1. 进入 Ubuntu 工程目录

如果工程在 Windows D 盘，通过 Ubuntu/WSL 访问：

```bash
cd /mnt/d/GMR_WORK/GMR
```

## 2. 准备环境

推荐使用统一脚本：

```bash
bash scripts/setup_multiformat_retargeting_ubuntu22_04.sh gmr
conda activate gmr
```

## 3. 检查默认 BVH 路径

```bash
python "Basic IK retargeting/run_basic_ik_retargeting.py" --check_paths_only
```

正常应看到：

```text
assets exists: True
motion exists: True
```

## 4. 只生成 pkl

```bash
python "Basic IK retargeting/run_basic_ik_retargeting.py" \
  --motion_name dance1_subject2.bvh \
  --robot unitree_g1 \
  --max_frames 100 \
  --no_visualize
```

默认输出：

```text
outputs/basic_ik_retargeting/
```

## 5. 打开 MuJoCo viewer

```bash
python "Basic IK retargeting/run_basic_ik_retargeting.py" \
  --motion_name dance1_subject2.bvh \
  --robot unitree_g1 \
  --rate_limit
```

## 6. 多格式输入

Basic IK 现在支持：

```text
BVH
SMPL-X npz
AMASS npz
Human3D npy/npz
```

示例：

```bash
python "Basic IK retargeting/run_basic_ik_retargeting.py" \
  --motion_file /path/to/motion.npz \
  --motion_format auto \
  --robot unitree_g1 \
  --max_frames 100 \
  --no_visualize
```

Human3D 示例：

```bash
python "Basic IK retargeting/run_basic_ik_retargeting.py" \
  --motion_file /path/to/human3d.npy \
  --motion_format joint_positions_npy \
  --joint_skeleton h36m_17 \
  --position_unit mm \
  --axis_order xyz \
  --robot unitree_g1 \
  --max_frames 100 \
  --no_visualize
```

Basic IK 使用 `mink.FrameTask` 跟踪目标 body，但不加关节限制、不加速度限制。它适合作为“无约束 IK baseline”，也更适合只有 3D 关节点位置的 Human3D 输入。
