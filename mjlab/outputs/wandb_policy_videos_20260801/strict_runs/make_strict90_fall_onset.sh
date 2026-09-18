#!/usr/bin/env bash

set -euo pipefail

output_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_video="${output_dir}/05_04_strict_90_no_terminations_i10dxzqw.mp4"
frame_dir="${output_dir}/strict90_fall_onset_frames"
font_file="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

mkdir -p "${frame_dir}"
index=0
for timestamp in $(seq 0.0 0.1 0.9); do
  printf -v frame_name '%02d.jpg' "${index}"
  frame_number="$(awk -v t="${timestamp}" 'BEGIN { printf "%d", t * 50 }')"
  ffmpeg -loglevel error -y -ss "${timestamp}" -i "${source_video}" \
    -frames:v 1 \
    -vf "scale=640:360,drawtext=fontfile=${font_file}:text='frame ${frame_number}  t=${timestamp}s':fontcolor=white:fontsize=28:x=18:y=18:box=1:boxcolor=black@0.72:boxborderw=9" \
    "${frame_dir}/${frame_name}"
  index=$((index + 1))
done

ffmpeg -loglevel error -y -framerate 1 -i "${frame_dir}/%02d.jpg" \
  -vf "tile=5x2" -frames:v 1 "${output_dir}/strict90_fall_onset.jpg"
