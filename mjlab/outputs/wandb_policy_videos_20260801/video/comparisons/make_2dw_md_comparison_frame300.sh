#!/usr/bin/env bash

set -euo pipefail

output_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
video_root="$(cd "${output_dir}/.." && pwd)"
frame_dir="${output_dir}/2dw_md_frame_300"
font_file="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
frame_number=300

specs=(
  "${video_root}/ppo/124_11_gmr_2dwjau88.mp4|ORIGINAL 124_11 | 2dwjau88"
  "${video_root}/policy transform/124_11_gmr_mdwpqq1y.mp4|47_01 TO 124_11 | mdwpqq1y"
)

mkdir -p "${frame_dir}"
index=0
for spec in "${specs[@]}"; do
  filename="${spec%%|*}"
  label="${spec#*|}"
  printf -v frame_name '%02d.png' "${index}"
  ffmpeg -loglevel error -y -i "${filename}" \
    -vf "select=eq(n\,${frame_number}),scale=960:540,drawtext=fontfile=${font_file}:text='${label} | FRAME ${frame_number} | t=6.0s':fontcolor=white:fontsize=28:x=24:y=24:box=1:boxcolor=black@0.74:boxborderw=11" \
    -frames:v 1 "${frame_dir}/${frame_name}"
  index=$((index + 1))
done

ffmpeg -loglevel error -y -framerate 1 -i "${frame_dir}/%02d.png" \
  -vf "tile=2x1" -frames:v 1 \
  "${output_dir}/2dwjau88_vs_mdwpqq1y_frame300.png"
