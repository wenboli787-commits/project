# Ubuntu NPV / NPZ / BVH 火柴人可视化操作文档

本文档说明如何使用 `visualize_stick_figure.py` 把 `.npv`、`.npz`、`.bvh` 动作文件渲染成 3D 火柴人，并导出为图片、GIF 或 MP4。

## 1. 安装环境

以下命令默认在 Ubuntu 上执行。

先设置两个常用路径。你的动作文件实际放在 Windows 的 `D:\GMR_WORK\final use mode`，在 WSL/Ubuntu 里通常对应 `/mnt/d/GMR_WORK/final use mode`。

```bash
SCRIPT_DIR="/mnt/d/GMR_WORK/Stick figure skeleton"
MOTION_DIR="/mnt/d/GMR_WORK/final use mode"
```

进入脚本目录：

如果你是在 WSL/Ubuntu 中直接访问 Windows 的 `D:\GMR_WORK`，通常使用：

```bash
cd "$SCRIPT_DIR"
```

如果你已经把项目复制到了 Ubuntu 主目录，例如 `$HOME/GMR_WORK`，使用：

```bash
SCRIPT_DIR="$HOME/GMR_WORK/Stick figure skeleton"
MOTION_DIR="$HOME/GMR_WORK/final use mode"
cd "$SCRIPT_DIR"
```

不确定目录在哪里时，可以先查找：

```bash
find "$HOME" /mnt/d -type d -name "Stick figure skeleton" 2>/dev/null
find "$HOME" /mnt/d -type d -name "final use mode" 2>/dev/null
```

创建并启用 Python 环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

如果 Ubuntu 还没有 venv/pip：

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
```

如果要导出 MP4，额外安装 `ffmpeg`：

```bash
sudo apt install -y ffmpeg
```

服务器或 SSH 无桌面环境下，不要直接弹窗查看，建议始终加 `--output` 和 `--no-show`：

```bash
python visualize_stick_figure.py "$MOTION_DIR/your_motion.bvh" \
  --output outputs/preview.gif \
  --no-show
```

如果先测试你的实际 `.npz` 文件路径，运行：

```bash
python visualize_stick_figure.py "$MOTION_DIR/08_01_poses.npz" --list-keys
```

能看到 `trans`、`poses`、`betas`、`dmpls`、`mocap_framerate` 等 key，就说明路径已经正确。

## 2. 直接可视化 BVH

弹出窗口查看：

```bash
python visualize_stick_figure.py "$MOTION_DIR/your_motion.bvh"
```

导出首帧 PNG：

```bash
python visualize_stick_figure.py "$MOTION_DIR/your_motion.bvh" \
  --output outputs/your_motion_first_frame.png \
  --unit-scale 0.01 \
  --up-axis x \
  --no-show
```

导出 GIF：

```bash
python visualize_stick_figure.py "$MOTION_DIR/your_motion.bvh" \
  --output outputs/your_motion.gif \
  --max-frames 240 \
  --unit-scale 0.01 \
  --up-axis x \
  --no-show
```

常见 BVH 是厘米单位，所以经常需要 `--unit-scale 0.01`。如果小人方向不对，依次尝试 `--up-axis z`、`--up-axis y`、`--up-axis x`。

## 3. 查看 NPV / NPZ 文件内容

先列出内部数组：

```bash
python visualize_stick_figure.py "$MOTION_DIR/08_01_poses.npz" --list-keys
python visualize_stick_figure.py "$MOTION_DIR/12_04_poses.npz" --list-keys
```

输出会显示每个 key 的 `shape` 和 `dtype`。优先选择形状类似下面的数组：

- `[T, J, 3]`：T 帧、J 个关节、XYZ 坐标。
- `[J, T, 3]`：J 个关节、T 帧、XYZ 坐标。
- `[T, J*3]`：每帧展平后的关节点坐标。
- `[T, C]`：BVH channel matrix，需要 BVH hierarchy metadata 或 `--template-bvh`。

注意：你当前 `final use mode` 里的 `.npz` 文件是 `poses + trans + betas + dmpls` 这种 AMASS/SMPL 参数格式。脚本会自动识别这种格式，并用近似 SMPL24 骨架生成火柴人预览；这适合快速检查动作姿态。若要和真实 SMPL 模型完全一致，需要再接完整 SMPL 模型。

## 4. 可视化 final use mode 里的 AMASS/SMPL 文件

单个文件导出 GIF：

```bash
python visualize_stick_figure.py "$MOTION_DIR/08_01_poses.npz" \
  --output outputs/final_use_mode/08_01_poses.gif \
  --max-frames 90 \
  --stride 2 \
  --fps 20 \
  --no-show
```

单个文件导出首帧 PNG：

```bash
python visualize_stick_figure.py "$MOTION_DIR/08_01_poses.npz" \
  --output outputs/final_use_mode/08_01_poses.png \
  --max-frames 1 \
  --no-show
```

批量导出当前目录下所有 `.npz`：

```bash
mkdir -p outputs/final_use_mode
for file in "$MOTION_DIR"/*.npz; do
  stem="$(basename "$file" .npz)"
  python visualize_stick_figure.py "$file" \
    --output "outputs/final_use_mode/${stem}.gif" \
    --max-frames 90 \
    --stride 2 \
    --fps 20 \
    --no-show
done
```

## 5. 可视化普通 NPV / NPZ 关节点坐标

如果文件里有 `positions`、`joint_positions`、`global_positions`、`keypoints3d` 等常见 key，脚本通常能自动识别：

```bash
python visualize_stick_figure.py "$MOTION_DIR/your_positions.npz" \
  --skeleton smpl24 \
  --output outputs/your_positions.gif \
  --no-show
```

手动指定 key：

```bash
python visualize_stick_figure.py "$MOTION_DIR/your_positions.npz" \
  --key positions \
  --array-layout tjc \
  --skeleton smpl24 \
  --output outputs/your_positions.gif \
  --no-show
```

常用骨架预设：

- `--skeleton lafan22`
- `--skeleton smpl24`
- `--skeleton coco17`
- `--skeleton chain`，只按 index 串起来，适合临时检查数据是否能显示。

如果 `.npv/.npz` 里已经保存了 `parents`、`joint_parents`、`kinematic_tree` 等父节点信息，可以不传 `--skeleton`。

## 6. 可视化 BVH channel matrix

如果 `.npv/.npz` 保存的是 BVH 原始 motion matrix，而不是 3D 关节点坐标，需要骨架信息。

如果文件里包含 `hierarchy` 和 `motion`，直接运行：

```bash
python visualize_stick_figure.py "$MOTION_DIR/your_motion_with_bvh_metadata.npz" \
  --output outputs/your_motion.gif \
  --unit-scale 0.01 \
  --up-axis x \
  --no-show
```

如果文件没有 `hierarchy`，提供模板 BVH：

```bash
python visualize_stick_figure.py "$MOTION_DIR/your_raw_motion.npv" \
  --template-bvh "$MOTION_DIR/template.bvh" \
  --output outputs/your_raw_motion.gif \
  --unit-scale 0.01 \
  --up-axis x \
  --no-show
```

模板 BVH 必须和 motion matrix 的 channel 数一致。

## 7. 常用命令模板

导出 PNG：

```bash
python visualize_stick_figure.py "$MOTION_DIR/08_01_poses.npz" \
  --output outputs/preview.png \
  --no-show
```

导出 GIF：

```bash
python visualize_stick_figure.py "$MOTION_DIR/08_01_poses.npz" \
  --output outputs/preview.gif \
  --max-frames 240 \
  --fps 30 \
  --no-show
```

导出 MP4：

```bash
python visualize_stick_figure.py "$MOTION_DIR/08_01_poses.npz" \
  --output outputs/preview.mp4 \
  --max-frames 600 \
  --fps 30 \
  --no-show
```

截取帧范围：

```bash
python visualize_stick_figure.py "$MOTION_DIR/08_01_poses.npz" \
  --start 100 \
  --end 400 \
  --stride 2 \
  --output outputs/clip.gif \
  --no-show
```

## 8. 故障排查

小人躺着或轴向不对：尝试 `--up-axis x/y/z`。

小人太大或太小：调整 `--unit-scale`，厘米转米通常用 `0.01`。

NPV/NPZ 不知道选哪个数组：先运行 `--list-keys`，再用 `--key` 指定。

提示没有 skeleton edges：为关节点坐标数据传 `--skeleton smpl24`、`--skeleton lafan22` 或手动传 `--parents`。

提示 BVH channel 数不匹配：检查 `--template-bvh` 是否和该 motion matrix 来自同一套 BVH 骨架。

## 9. Windows 备注

如果只是把文件拷到 Windows 上临时检查，也可以用 PowerShell 运行；但你的仿真流程在 Ubuntu 上时，以上 Ubuntu 命令就是主线流程。
