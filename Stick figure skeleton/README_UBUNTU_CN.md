# Stick figure skeleton 可视化工具

这个目录提供一个独立 Python 脚本，用来把 `.bvh`、`.npv`、`.npz`、`.npy` 动作文件画成 3D stick figure skeleton 小人。它不依赖 MuJoCo，可作为 Ubuntu 仿真前后的动作数据检查工具。

## 目录内容

- `visualize_stick_figure.py`：主程序，负责读取动作文件、生成关节点位置、渲染小人。
- `requirements.txt`：Python 依赖。
- `README_UBUNTU_CN.md`：当前操作文档和代码解释。

## Ubuntu 环境安装

先设置两个常用路径。路径中有空格时必须加引号。你的动作文件实际放在 Windows 的 `D:\GMR_WORK\final use mode`，在 WSL/Ubuntu 里通常对应 `/mnt/d/GMR_WORK/final use mode`。

如果你是在 WSL/Ubuntu 中直接访问 Windows 的 `D:\GMR_WORK`，通常使用：

```bash
SCRIPT_DIR="/mnt/d/GMR_WORK/Stick figure skeleton"
MOTION_DIR="/mnt/d/GMR_WORK/final use mode"
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

然后安装环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

如果需要导出 MP4，再安装 `ffmpeg`：

```bash
sudo apt update
sudo apt install -y ffmpeg
```

如果只导出 GIF，不一定需要 `ffmpeg`，`pillow` 已经在 `requirements.txt` 里。

## 快速使用

### 1. 可视化 BVH

```bash
python visualize_stick_figure.py "$MOTION_DIR/your_motion.bvh"
```

有桌面环境时会弹出 matplotlib 窗口。服务器或无显示器环境建议直接导出：

```bash
python visualize_stick_figure.py "$MOTION_DIR/your_motion.bvh" \
  --output outputs/your_motion.gif \
  --max-frames 240 \
  --unit-scale 0.01 \
  --up-axis x \
  --no-show
```

说明：

- `--unit-scale 0.01`：很多 BVH 是厘米单位，转成米显示时使用 0.01。如果你的 BVH 本来就是米，保持默认 `1.0`。
- `--up-axis x`：指定输入数据哪个轴是竖直方向。若小人躺着，依次尝试 `--up-axis y` 或 `--up-axis z`。
- `--max-frames 240`：只导出前 240 帧，避免 GIF/MP4 文件过大。

导出首帧 PNG：

```bash
python visualize_stick_figure.py "$MOTION_DIR/your_motion.bvh" \
  --output outputs/your_motion_first_frame.png \
  --unit-scale 0.01 \
  --up-axis x \
  --no-show
```

### 2. 查看 NPV/NPZ 内部有哪些数组

```bash
python visualize_stick_figure.py "$MOTION_DIR/08_01_poses.npz" --list-keys
```

`.npv` 不是 NumPy 官方固定扩展名，本脚本按 NumPy payload 兼容读取：只要文件内容实际是 `np.save` 或 `np.savez` 保存出的数组/压缩包，就可以直接传入。

```bash
python visualize_stick_figure.py "$MOTION_DIR/your_motion.npv" --list-keys
```

输出会列出每个 key 的 `shape` 和 `dtype`。找到关节点坐标数组后，用 `--key` 指定：

```bash
python visualize_stick_figure.py "$MOTION_DIR/your_positions.npz" \
  --key positions \
  --skeleton smpl24 \
  --output outputs/your_positions.mp4 \
  --no-show
```

注意：你当前 `final use mode` 目录里的 `.npz` 文件包含 `trans`、`poses`、`betas`、`dmpls`、`mocap_framerate` 等 key，属于 AMASS/SMPL 参数格式。脚本会自动识别这种格式，并用近似 SMPL24 骨架生成火柴人预览；这适合快速检查动作姿态。若要和真实 SMPL 模型完全一致，需要再接完整 SMPL 模型。

直接把你的文件导出成 GIF：

```bash
python visualize_stick_figure.py "$MOTION_DIR/08_01_poses.npz" \
  --output outputs/final_use_mode/08_01_poses.gif \
  --max-frames 90 \
  --stride 2 \
  --fps 20 \
  --no-show
```

批量导出：

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

### 3. 可视化 NPV/NPY/NPZ 关节点坐标

脚本支持这些常见数组形状：

- `[T, J, 3]`：T 帧、J 个关节、XYZ 坐标，最推荐。
- `[J, T, 3]`：用 `--array-layout jtc` 明确指定。
- `[T, 3, J]`：用 `--array-layout tcj` 明确指定。
- `[T, J*3]`：用 `--array-layout flat` 或自动识别。
- `[J, 3]`：静态单帧姿态，用 `--array-layout static-jc`。

例子：

```bash
python visualize_stick_figure.py "$MOTION_DIR/your_joints.npy" \
  --array-layout tjc \
  --skeleton smpl24 \
  --output outputs/your_joints.gif \
  --no-show
```

`.npv` 用法相同：

```bash
python visualize_stick_figure.py "$MOTION_DIR/your_joints.npv" \
  --array-layout tjc \
  --skeleton smpl24 \
  --output outputs/your_joints.gif \
  --no-show
```

如果文件里已经有 `parents`、`joint_parents`、`kinematic_tree` 等骨架连接信息，脚本会自动读取。否则可以用预设骨架：

```bash
--skeleton lafan22
--skeleton smpl24
--skeleton coco17
```

也可以手动指定父节点数组：

```bash
python visualize_stick_figure.py "$MOTION_DIR/your_joints.npy" \
  --parents "-1,0,1,2,3,0,5,6,7,0,9,10,11,12,11,14,15,16,11,18,19,20" \
  --output outputs/custom.gif \
  --no-show
```

父节点数组含义：第 `i` 个数字是第 `i` 个关节的父节点 index，根节点写 `-1`。

### 4. 可视化原始 BVH motion matrix

如果 `.npv`、`.npy` 或 `.npz` 里存的是 BVH 原始通道矩阵，而不是 `[T,J,3]` 坐标，它本身没有骨架层级，必须提供模板 BVH：

```bash
python visualize_stick_figure.py "$MOTION_DIR/your_raw_motion.npy" \
  --template-bvh "$MOTION_DIR/template.bvh" \
  --output outputs/raw_motion.gif \
  --unit-scale 0.01 \
  --up-axis x \
  --no-show
```

如果 `.npz` 是由带 BVH metadata 的转换脚本保存的，并包含 `hierarchy` 和 `motion`，一般不需要 `--template-bvh`：

```bash
python visualize_stick_figure.py "$MOTION_DIR/your_motion_with_bvh_metadata.npz" \
  --output outputs/from_npz.gif \
  --unit-scale 0.01 \
  --up-axis x \
  --no-show
```

## 常用参数

```bash
python visualize_stick_figure.py "$MOTION_DIR/08_01_poses.npz" \
  --output outputs/out.gif \
  --unit-scale 1.0 \
  --up-axis z \
  --start 0 \
  --end 600 \
  --stride 2 \
  --max-frames 300 \
  --fps 30 \
  --no-show
```

- `INPUT`：`.bvh`、`.npv`、`.npy`、`.npz`。
- `--output`：输出路径。支持 `.png`、`.gif`、`.mp4`。
- `--key`：从 `.npz` 或 dict-like `.npy` 里选择数组。
- `--list-keys`：列出 `.npv`、`.npz` 或 dict-like `.npy` 内部 key。
- `--template-bvh`：为原始 BVH channel matrix 提供骨架模板。
- `--array-layout`：手动指定 NPY/NPZ 坐标数组布局。
- `--parents`：手动指定父节点 index。
- `--skeleton`：使用内置骨架连接预设。
- `--unit-scale`：单位缩放。
- `--up-axis`：输入数据的竖直轴。
- `--start` / `--end` / `--stride` / `--max-frames`：截取和降采样帧。
- `--fps`：导出 GIF/MP4 的帧率。
- `--follow-root` / `--no-follow-root`：是否让相机跟随根节点。

## 数据格式建议

最稳妥的 `.npy` 格式：

```python
import numpy as np

# positions.shape == [frames, joints, 3]
np.save("motion.npy", positions)
```

最稳妥的 `.npz` 格式：

```python
import numpy as np

np.savez_compressed(
    "motion.npz",
    positions=positions,          # [T, J, 3]
    parents=parents,              # [J], root is -1
    joint_names=joint_names,      # optional [J]
    fps=30,
)
```

如果没有 `parents`，脚本只能根据关节数量猜测骨架连接；猜不到时会退化成 index chain，形状可以显示但不一定像人体。

## 代码逻辑解释

### 1. BVH 读取

`read_bvh()` 会把 BVH 分成两部分：

- `HIERARCHY`：关节层级、每个关节的 `OFFSET`、每个关节有哪些 channel。
- `MOTION`：每一帧的 channel 数值。

`parse_bvh_hierarchy()` 会生成 `BvhSkeleton`，里面保存：

- `joint.name`：关节名。
- `joint.parent`：父关节 index。
- `joint.offset`：相对父关节的静态偏移。
- `joint.channels`：例如 `Xposition Yposition Zposition Zrotation Yrotation Xrotation`。
- `joint.channel_start`：该关节在每帧 motion 向量里的起始列。

### 2. BVH 正向运动学

`bvh_to_positions()` 会逐帧逐关节计算全局位置：

1. 读取当前关节的 `OFFSET` 作为局部平移。
2. 读取 `position` channel，更新局部平移。
3. 读取 `rotation` channel，按 BVH 文件里的顺序累乘旋转矩阵。
4. 如果是根节点，局部变换就是全局变换。
5. 如果不是根节点，用父节点全局旋转和平移把当前关节变换到世界坐标。

最后得到：

```python
positions.shape == [frames, joints, 3]
```

这个数组就是 stick figure 渲染真正需要的数据。

### 3. NPY/NPZ 读取

`load_array_sequence()` 会先选择一个数组：

- 如果用户传了 `--key`，优先读取该 key。
- 否则按 `positions`、`joint_positions`、`global_positions`、`keypoints3d`、`motion`、`data`、`arr_0` 等常见名字自动查找。

然后 `normalize_positions()` 将不同布局统一成：

```python
[frames, joints, 3]
```

如果 `.npz` 或 dict-like `.npy` 里有 `parents`、`joint_parents`、`kinematic_tree`，脚本会自动作为骨架连接；否则使用 `--skeleton` 预设或 `--parents`。

### 4. 渲染

`render_motion()` 使用 matplotlib 3D：

- 每个关节画一个红点。
- 每条骨骼边画一条蓝线。
- `parents_to_edges()` 把父节点数组转换成线段列表。
- `FuncAnimation` 负责逐帧更新点和线。

输出逻辑：

- `.png`：保存当前第一帧。
- `.gif`：使用 `PillowWriter`。
- `.mp4`：使用 `FFMpegWriter`，需要系统安装 `ffmpeg`。

## 常见问题

### 小人躺着或方向不对

改变竖直轴：

```bash
--up-axis x
--up-axis y
--up-axis z
```

### 小人太大或太小

改变单位缩放：

```bash
--unit-scale 0.01
--unit-scale 1.0
--unit-scale 100.0
```

### 服务器上无法弹窗

无显示器或 SSH 环境必须导出文件：

```bash
python visualize_stick_figure.py motion.bvh --output outputs/motion.gif --no-show
```

### NPZ 不知道应该选哪个 key

先列出 key：

```bash
python visualize_stick_figure.py motion.npz --list-keys
```

再用：

```bash
python visualize_stick_figure.py motion.npz --key positions --output outputs/motion.gif --no-show
```

### NPY 是 `[T, 66]`，结果显示不对

`[T, 66]` 可能有两种含义：

1. 22 个关节的 XYZ 坐标，应该按 `[T, J*3]` reshape。
2. BVH 原始 channel matrix，需要 BVH 层级才能正向运动学。

如果它来自 BVH 的原始 motion channel，请使用：

```bash
python visualize_stick_figure.py raw_motion.npy --template-bvh template.bvh --output outputs/raw.gif --no-show
```

## 推荐工作流

1. BVH 原始动作先直接可视化，确认骨架和方向：

```bash
python visualize_stick_figure.py input.bvh --output outputs/input.gif --unit-scale 0.01 --up-axis x --no-show
```

2. 仿真/重定向中间结果保存为 `[T,J,3]` 的 `.npz`：

```python
np.savez_compressed("debug_motion.npz", positions=positions, parents=parents, fps=30)
```

3. 每次算法改动后生成 GIF/MP4，对比小人是否抖动、漂移、左右脚是否错位。
