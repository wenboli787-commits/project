#!/usr/bin/env bash

set -euo pipefail

output_dir="/mnt/d/GMR_WORK/mjlab/outputs/wandb_policy_videos_20260801/video/comparisons/05_04_phase_sheets"
video_root="/mnt/d/GMR_WORK/mjlab/outputs/wandb_policy_videos_20260801/video/ablation"
font_file="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
run_ids=(09yrh4qp y84gf3sj 6rlspqk0 p6vbd18i 6gq87ju7 q2l4sxxn)

mkdir -p "${output_dir}"
for run_id in "${run_ids[@]}"; do
  filename=("${video_root}"/*"${run_id}".mp4)
  ffmpeg -loglevel error -y -i "${filename[0]}" \
    -vf "fps=5,crop=1000:1000:460:80,scale=240:240,drawbox=x=0:y=0:w=iw:h=28:color=black@0.8:t=fill,drawtext=fontfile=${font_file}:text='${run_id}  F%{eif\\:n*10\\:d}':fontcolor=white:fontsize=16:x=6:y=5,tile=10x5" \
    -frames:v 1 "${output_dir}/${run_id}_timeline.png"
done
