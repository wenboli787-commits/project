#!/usr/bin/env bash

set -euo pipefail

output_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source_video="${output_dir}/05_04_strict_90_no_terminations_i10dxzqw.mp4"
slow_video="${output_dir}/05_04_strict_90_no_terminations_slow_0.5x_i10dxzqw.mp4"
frame_dir="${output_dir}/strict90_timeline_frames"
font_file="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

ffmpeg -loglevel error -y -i "${source_video}" \
  -vf "setpts=2.0*PTS" -an -r 50 -c:v libx264 -crf 18 -preset medium \
  "${slow_video}"

mkdir -p "${frame_dir}"
index=0
for timestamp in $(seq 0.5 0.5 10.0); do
  printf -v frame_name '%02d.jpg' "${index}"
  ffmpeg -loglevel error -y -ss "${timestamp}" -i "${source_video}" \
    -frames:v 1 \
    -vf "scale=640:360,drawtext=fontfile=${font_file}:text='t=${timestamp}s':fontcolor=white:fontsize=30:x=18:y=18:box=1:boxcolor=black@0.72:boxborderw=9" \
    "${frame_dir}/${frame_name}"
  index=$((index + 1))
done

ffmpeg -loglevel error -y -framerate 1 -i "${frame_dir}/%02d.jpg" \
  -vf "tile=5x4" -frames:v 1 "${output_dir}/strict90_fall_timeline.jpg"

ffprobe -v error -show_entries format=duration:stream=r_frame_rate \
  -of default=noprint_wrappers=1 "${slow_video}"
