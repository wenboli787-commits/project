#!/usr/bin/env bash

set -euo pipefail

output_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
video_root="$(cd "${output_dir}/.." && pwd)"
frame_dir="${output_dir}/qwd_f5_frame_250"
font_file="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
frame_number=250

specs=(
  "${video_root}/ppo/111_23_gmr_qwdsvlx8.mp4|ORIGINAL 111_23 | qwdsvlx8"
  "${output_dir}/111_23_gmr_f5v4oslz.mp4|47_01 TO 111_23 | f5v4oslz"
)

mkdir -p "${frame_dir}"
index=0
for spec in "${specs[@]}"; do
  filename="${spec%%|*}"
  label="${spec#*|}"
  printf -v frame_name '%02d.jpg' "${index}"
  ffmpeg -loglevel error -y -i "${filename}" \
    -vf "select=eq(n\,${frame_number}),scale=960:540,drawtext=fontfile=${font_file}:text='${label} | FRAME ${frame_number} | t=5.0s':fontcolor=white:fontsize=28:x=24:y=24:box=1:boxcolor=black@0.74:boxborderw=11" \
    -frames:v 1 "${frame_dir}/${frame_name}"
  index=$((index + 1))
done

ffmpeg -loglevel error -y -framerate 1 -i "${frame_dir}/%02d.jpg" \
  -vf "tile=2x1" -frames:v 1 \
  "${output_dir}/qwdsvlx8_vs_f5v4oslz_frame_250.jpg"
