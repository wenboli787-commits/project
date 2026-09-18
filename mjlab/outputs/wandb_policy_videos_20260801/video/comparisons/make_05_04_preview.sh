#!/usr/bin/env bash

set -euo pipefail

output_dir="/mnt/d/GMR_WORK/mjlab/outputs/wandb_policy_videos_20260801/video/comparisons"
video_root="/mnt/d/GMR_WORK/mjlab/outputs/wandb_policy_videos_20260801/video/ablation"
frame_dir="${output_dir}/05_04_preview_frames"
font_file="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

specs=(
  "09yrh4qp|NO GLOBAL ROOT"
  "y84gf3sj|NO BODY POSE"
  "6rlspqk0|NO VELOCITY"
  "p6vbd18i|NO ACTION RATE"
  "6gq87ju7|NO JOINT LIMIT"
  "q2l4sxxn|NO SELF COLLISION"
)

mkdir -p "${frame_dir}"
for frame_number in 150 250 350 450; do
  index=0
  for spec in "${specs[@]}"; do
    run_id="${spec%%|*}"
    label="${spec#*|}"
    filename=("${video_root}"/*"${run_id}".mp4)
    printf -v frame_name '%02d.png' "${index}"
    ffmpeg -loglevel error -y -i "${filename[0]}" \
      -vf "select=eq(n\,${frame_number}),scale=480:270,drawtext=fontfile=${font_file}:text='${label} | ${run_id} | F${frame_number}':fontcolor=white:fontsize=19:x=12:y=12:box=1:boxcolor=black@0.75:boxborderw=7" \
      -frames:v 1 "${frame_dir}/${frame_name}"
    index=$((index + 1))
  done
  ffmpeg -loglevel error -y -framerate 1 -i "${frame_dir}/%02d.png" \
    -vf "tile=3x2" -frames:v 1 "${output_dir}/05_04_preview_frame${frame_number}.png"
done
