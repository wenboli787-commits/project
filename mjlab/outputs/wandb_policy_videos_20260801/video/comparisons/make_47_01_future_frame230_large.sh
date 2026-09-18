#!/usr/bin/env bash

set -euo pipefail

output_dir="/mnt/d/GMR_WORK/mjlab/outputs/wandb_policy_videos_20260801/video/comparisons"
video_root="/mnt/d/GMR_WORK/mjlab/outputs/wandb_policy_videos_20260801/video/future frames"
frame_dir="${output_dir}/47_01_future_frame350"
font_file="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
frame_number=350
time_seconds="$(awk -v frame="${frame_number}" 'BEGIN { printf "%.2f", frame / 50 }')"

specs=(
  "gj3mxfhz|HISTORY H4"
  "d4047a92|FUTURE F2"
  "p8e2ur8w|FUTURE F4"
  "mq50cknd|FUTURE F6"
)

mkdir -p "${frame_dir}"
index=0
for spec in "${specs[@]}"; do
  run_id="${spec%%|*}"
  label="${spec#*|}"
  filename=("${video_root}"/*"${run_id}".mp4)
  printf -v frame_name '%02d.png' "${index}"
  ffmpeg -loglevel error -y -i "${filename[0]}" \
    -vf "select=eq(n\,${frame_number}),crop=1000:1000:460:80,scale=760:760,drawbox=x=0:y=0:w=iw:h=118:color=black@0.82:t=fill,drawtext=fontfile=${font_file}:text='47_01  ${label}':fontcolor=white:fontsize=38:x=26:y=16,drawtext=fontfile=${font_file}:text='${run_id}   FRAME ${frame_number}   ${time_seconds} s':fontcolor=white:fontsize=27:x=26:y=70" \
    -frames:v 1 "${frame_dir}/${frame_name}"
  index=$((index + 1))
done

ffmpeg -loglevel error -y -framerate 1 -i "${frame_dir}/%02d.png" \
  -vf "tile=2x2" -frames:v 1 \
  "${output_dir}/47_01_future_green_pose_aligned.png"
