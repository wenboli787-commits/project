# Direct Mapping Ubuntu 使用说明

本文只保留 Direct mapping 的快速入口。完整多格式说明见：

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
python "direct mapping/run_direct_mapping.py" --check_paths_only
```

正常应看到：

```text
assets exists: True
motion exists: True
```

## 4. 只生成 pkl

```bash
python "direct mapping/run_direct_mapping.py" \
  --motion_name dance1_subject2.bvh \
  --robot unitree_g1 \
  --max_frames 100 \
  --no_visualize
```

默认输出：

```text
outputs/direct_mapping/
```

## 5. 打开 MuJoCo viewer

```bash
python "direct mapping/run_direct_mapping.py" \
  --motion_name dance1_subject2.bvh \
  --robot unitree_g1 \
  --rate_limit
```

## 6. 多格式输入

Direct mapping 现在支持：

```text
BVH
SMPL-X npz
AMASS npz
Human3D npy/npz
```

示例：

```bash
python "direct mapping/run_direct_mapping.py" \
  --motion_file /path/to/motion.npz \
  --motion_format auto \
  --robot unitree_g1 \
  --max_frames 100 \
  --no_visualize
```

Human3D 示例：

```bash
python "direct mapping/run_direct_mapping.py" \
  --motion_file /path/to/human3d.npy \
  --motion_format joint_positions_npy \
  --joint_skeleton h36m_17 \
  --position_unit mm \
  --axis_order xyz \
  --robot unitree_g1 \
  --max_frames 100 \
  --no_visualize
```

Direct mapping 不求 IK，它把人体局部旋转变化投影到机器人 hinge joint 轴上。因此普通 Human3D 只有位置、没有真实旋转时，效果通常比 BVH/SMPL-X/AMASS 更不稳定。
