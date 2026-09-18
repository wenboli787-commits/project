#!/usr/bin/env bash

set -euo pipefail

root_dir="/mnt/d/GMR_WORK/mjlab/outputs/wandb_policy_videos_20260801"
output_dir="${root_dir}/video/comparisons/transform_pair_phase_sheets"
font_file="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
specs=(
  "p5jxr34o|${root_dir}/cache/g1_tracking/wandb_checkpoints/p5jxr34o/videos/play/rl-video-step-0.mp4"
  "3ah12ywt|${root_dir}/video/policy transform/05_04_gmr_3ah12ywt.mp4"
  "qwdsvlx8|${root_dir}/cache/g1_tracking/wandb_checkpoints/qwdsvlx8/videos/play/rl-video-step-0.mp4"
  "f5v4oslz|${root_dir}/video/policy transform/111_23_gmr_f5v4oslz.mp4"
)

mkdir -p "${output_dir}"
for spec in "${specs[@]}"; do
  run_id="${spec%%|*}"
  filename="${spec#*|}"
  ffmpeg -loglevel error -y -i "${filename}" \
    -vf "fps=5,crop=1000:1000:460:80,scale=240:240,drawbox=x=0:y=0:w=iw:h=28:color=black@0.8:t=fill,drawtext=fontfile=${font_file}:text='${run_id}  F%{eif\\:n*10\\:d}':fontcolor=white:fontsize=16:x=6:y=5,tile=10x5" \
    -frames:v 1 "${output_dir}/${run_id}_timeline.png"
done
