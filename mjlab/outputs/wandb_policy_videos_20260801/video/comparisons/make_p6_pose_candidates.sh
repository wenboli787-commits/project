#!/usr/bin/env bash

set -euo pipefail

output_dir="/mnt/d/GMR_WORK/mjlab/outputs/wandb_policy_videos_20260801/video/comparisons"
video_root="/mnt/d/GMR_WORK/mjlab/outputs/wandb_policy_videos_20260801/video/ablation"
frame_dir="${output_dir}/p6_pose_candidates"
font_file="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
specs=(
  "09yrh4qp|150|TARGET"
  "p6vbd18i|105|CANDIDATE"
  "p6vbd18i|115|CANDIDATE"
  "p6vbd18i|123|CANDIDATE"
  "p6vbd18i|131|CANDIDATE"
  "p6vbd18i|144|CANDIDATE"
  "p6vbd18i|155|CANDIDATE"
  "p6vbd18i|163|CANDIDATE"
  "p6vbd18i|173|CANDIDATE"
)

mkdir -p "${frame_dir}"
index=0
for spec in "${specs[@]}"; do
  run_id="${spec%%|*}"
  remainder="${spec#*|}"
  frame_number="${remainder%%|*}"
  role="${remainder#*|}"
  filename=("${video_root}"/*"${run_id}".mp4)
  printf -v frame_name '%02d.png' "${index}"
  ffmpeg -loglevel error -y -i "${filename[0]}" \
    -vf "select=eq(n\,${frame_number}),crop=1000:1000:460:80,scale=500:500,drawbox=x=0:y=0:w=iw:h=62:color=black@0.82:t=fill,drawtext=fontfile=${font_file}:text='${role}  ${run_id}  F${frame_number}':fontcolor=white:fontsize=25:x=12:y=16" \
    -frames:v 1 "${frame_dir}/${frame_name}"
  index=$((index + 1))
done

ffmpeg -loglevel error -y -framerate 1 -i "${frame_dir}/%02d.png" \
  -vf "tile=3x3" -frames:v 1 "${output_dir}/p6_pose_candidates.png"
