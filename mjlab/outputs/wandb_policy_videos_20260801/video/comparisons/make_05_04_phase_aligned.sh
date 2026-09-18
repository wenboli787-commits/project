#!/usr/bin/env bash

set -euo pipefail

output_dir="/mnt/d/GMR_WORK/mjlab/outputs/wandb_policy_videos_20260801/video/comparisons"
video_root="/mnt/d/GMR_WORK/mjlab/outputs/wandb_policy_videos_20260801/video/ablation"
frame_dir="${output_dir}/05_04_phase_aligned_frames"
font_file="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

specs=(
  "09yrh4qp|150|05_04  NO GLOBAL ROOT"
  "y84gf3sj|363|05_04  NO BODY POSE"
  "6rlspqk0|388|05_04  NO VELOCITY"
  "p6vbd18i|173|05_04  NO ACTION RATE"
  "6gq87ju7|432|05_04  NO JOINT LIMIT"
  "q2l4sxxn|105|05_04  NO SELF COLLISION"
)

mkdir -p "${frame_dir}"
index=0
for spec in "${specs[@]}"; do
  run_id="${spec%%|*}"
  remainder="${spec#*|}"
  frame_number="${remainder%%|*}"
  label="${remainder#*|}"
  time_seconds="$(awk -v frame="${frame_number}" 'BEGIN { printf "%.2f", frame / 50 }')"
  filename=("${video_root}"/*"${run_id}".mp4)
  printf -v frame_name '%02d.png' "${index}"
  ffmpeg -loglevel error -y -i "${filename[0]}" \
    -vf "select=eq(n\,${frame_number}),crop=1000:1000:460:80,scale=700:700,drawbox=x=0:y=0:w=iw:h=112:color=black@0.82:t=fill,drawtext=fontfile=${font_file}:text='${label}':fontcolor=white:fontsize=34:x=24:y=16,drawtext=fontfile=${font_file}:text='${run_id}   FRAME ${frame_number}   ${time_seconds} s':fontcolor=white:fontsize=24:x=24:y=65" \
    -frames:v 1 "${frame_dir}/${frame_name}"
  index=$((index + 1))
done

ffmpeg -loglevel error -y -framerate 1 -i "${frame_dir}/%02d.png" \
  -vf "tile=3x2" -frames:v 1 \
  "${output_dir}/05_04_ablation_green_pose_aligned.png"
