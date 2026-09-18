#!/usr/bin/env bash

set -euo pipefail

output_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
frame_dir="${output_dir}/comparison_frame_350"
font_file="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
frame_number=350

specs=(
  "47_01_gmr_history_H4_gj3mxfhz.mp4|HISTORY H4"
  "47_01_gmr_future_F2_d4047a92.mp4|FUTURE F2"
  "47_01_gmr_future_F4_p8e2ur8w.mp4|FUTURE F4"
  "47_01_gmr_future_F6_mq50cknd.mp4|FUTURE F6"
)

mkdir -p "${frame_dir}"
index=0
for spec in "${specs[@]}"; do
  IFS='|' read -r filename label <<<"${spec}"
  printf -v frame_name '%02d.jpg' "${index}"
  ffmpeg -loglevel error -y -i "${output_dir}/${filename}" \
    -vf "select=eq(n\,${frame_number}),scale=960:540,drawtext=fontfile=${font_file}:text='${label} | FRAME ${frame_number} | t=7.0s':fontcolor=white:fontsize=38:x=24:y=24:box=1:boxcolor=black@0.74:boxborderw=12" \
    -frames:v 1 "${frame_dir}/${frame_name}"
  index=$((index + 1))
done

ffmpeg -loglevel error -y -framerate 1 -i "${frame_dir}/%02d.jpg" \
  -vf "tile=2x2" -frames:v 1 \
  "${output_dir}/future_history_comparison_frame_350.jpg"
