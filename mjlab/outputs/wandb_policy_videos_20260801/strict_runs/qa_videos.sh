#!/usr/bin/env bash

set -euo pipefail

output_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
frame_dir="${output_dir}/qa_frames"

mkdir -p "${frame_dir}"
for video in "${output_dir}"/*.mp4; do
  name="$(basename "${video}" .mp4)"
  ffmpeg -loglevel error -y -ss 5 -i "${video}" -frames:v 1 \
    "${frame_dir}/${name}.jpg"
done

ffmpeg -loglevel error -y -pattern_type glob -i "${frame_dir}/*.jpg" \
  -vf "scale=480:270,tile=5x2" -frames:v 1 \
  "${output_dir}/contact_sheet.jpg"
