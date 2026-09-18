# GMR 到 mjlab RLTracking 本次运行汇总

运行目录：

```text
D:\GMR_WORK\GMR\outputs\gmr_to_mjlab_physics_20260702_103742
```

## 输入

GMR 动作输入目录：

```text
D:\GMR_WORK\final use mode
```

共处理 9 个动作：

```text
08_01, 08_04, 08_05, 09_01, 09_12, 10_01, 13_01, 13_11, 13_17
```

## GMR 阶段结果

输出位置：

```text
gmr\pkl
gmr\videos
gmr\logs
manifests\gmr_batch_summary.csv
```

结果：9/9 成功，全部状态为 `ok`。

## mjlab CSV 阶段结果

输出位置：

```text
mjlab\csv
manifests\mjlab_csv_manifest.csv
```

结果：9/9 成功，全部 CSV 为 36 列 mjlab G1 motion 格式。

## mjlab RLTracking 阶段结果

配置：

```text
task: Mjlab-Tracking-Flat-Unitree-G1
num_envs: 128
max_iterations: 20
save_interval: 10
video: True
video_interval: 200
video_length: 120
wandb: online
```

本地输出：

```text
mjlab\rsl_rl_logs\g1_tracking
logs\mjlab_train_stdout
manifests\mjlab_rltracking_wandb_runs.csv
manifests\mjlab_wandb_run_links.csv
manifests\wandb_run_file_check.csv
```

WandB API 校验：

```text
9/9 run online 可见
9/9 run 包含 model_19.pt
9/9 run 包含 ONNX
9/9 run 包含 media 文件
```

## WandB run 链接

| Motion | WandB run |
| --- | --- |
| 08_01_gmr | https://wandb.ai/wenboli787-university-of-glasgow/mjlab/runs/1xcllm6k |
| 08_04_gmr | https://wandb.ai/wenboli787-university-of-glasgow/mjlab/runs/lxswcpsh |
| 08_05_gmr | https://wandb.ai/wenboli787-university-of-glasgow/mjlab/runs/2xgl98lt |
| 09_01_gmr | https://wandb.ai/wenboli787-university-of-glasgow/mjlab/runs/ee30975w |
| 09_12_gmr | https://wandb.ai/wenboli787-university-of-glasgow/mjlab/runs/4aid49n6 |
| 10_01_gmr | https://wandb.ai/wenboli787-university-of-glasgow/mjlab/runs/uqw1ku19 |
| 13_01_gmr | https://wandb.ai/wenboli787-university-of-glasgow/mjlab/runs/l1munm0r |
| 13_11_gmr | https://wandb.ai/wenboli787-university-of-glasgow/mjlab/runs/3kanfjie |
| 13_17_gmr | https://wandb.ai/wenboli787-university-of-glasgow/mjlab/runs/tkzxjh16 |

## 文件统计

本次目录内关键文件数量：

```text
9  GMR PKL
9  GMR replay MP4
9  mjlab CSV
9  mjlab ONNX
27 mjlab checkpoints
36 MP4 total
```
