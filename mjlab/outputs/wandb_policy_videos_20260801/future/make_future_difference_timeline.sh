#!/usr/bin/env bash

set -euo pipefail

output_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
frame_dir="${output_dir}/difference_timeline_frames"
font_file="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

specs=(
  "47_01_gmr_history_H4_gj3mxfhz.mp4|HISTORY H4"
  "47_01_gmr_future_F2_d4047a92.mp4|FUTURE F2"
  "47_01_gmr_future_F4_p8e2ur8w.mp4|FUTURE F4"
  "47_01_gmr_future_F6_mq50cknd.mp4|FUTURE F6"
)

mkdir -p "${frame_dir}"
index=0
for timestamp in $(seq 1 1 9); do
  for spec in "${specs[@]}"; do
    IFS='|' read -r filename label <<<"${spec}"
    printf -v frame_name '%02d.jpg' "${index}"
    ffmpeg -loglevel error -y -ss "${timestamp}" -i "${output_dir}/${filename}" \
      -frames:v 1 \
      -vf "scale=480:270,drawtext=fontfile=${font_file}:text='${label} | t=${timestamp}s':fontcolor=white:fontsize=25:x=14:y=14:box=1:boxcolor=black@0.72:boxborderw=8" \
      "${frame_dir}/${frame_name}"
    index=$((index + 1))
  done
done

ffmpeg -loglevel error -y -framerate 1 -i "${frame_dir}/%02d.jpg" \
  -vf "tile=4x9" -frames:v 1 "${output_dir}/future_difference_timeline.jpg"
