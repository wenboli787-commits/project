#!/usr/bin/env bash

set -euo pipefail

output_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
video_root="$(cd "${output_dir}/.." && pwd)"
frame_dir="${output_dir}/qwd_f5_timeline_frames"
font_file="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

specs=(
  "${video_root}/ppo/111_23_gmr_qwdsvlx8.mp4|111_23 ORIGINAL"
  "${output_dir}/111_23_gmr_f5v4oslz.mp4|47_01 TO 111_23"
)

mkdir -p "${frame_dir}"
index=0
for timestamp in $(seq 1 1 9); do
  for spec in "${specs[@]}"; do
    IFS='|' read -r filename label <<<"${spec}"
    printf -v frame_name '%02d.jpg' "${index}"
    ffmpeg -loglevel error -y -ss "${timestamp}" -i "${filename}" \
      -frames:v 1 \
      -vf "scale=640:360,drawtext=fontfile=${font_file}:text='${label} | t=${timestamp}s':fontcolor=white:fontsize=28:x=16:y=16:box=1:boxcolor=black@0.72:boxborderw=9" \
      "${frame_dir}/${frame_name}"
    index=$((index + 1))
  done
done

ffmpeg -loglevel error -y -framerate 1 -i "${frame_dir}/%02d.jpg" \
  -vf "tile=2x9" -frames:v 1 "${output_dir}/qwd_f5_difference_timeline.jpg"
