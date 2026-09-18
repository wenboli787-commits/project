#!/usr/bin/env bash

set -euo pipefail

output_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "${output_dir}/qa_frames"

for video in "${output_dir}"/*.mp4; do
  name="$(basename "${video}" .mp4)"
  ffmpeg -loglevel error -y -ss 5 -i "${video}" -frames:v 1 \
    "${output_dir}/qa_frames/${name}.jpg"
done

ffmpeg -loglevel error -y -pattern_type glob \
  -i "${output_dir}/qa_frames/*.jpg" \
  -vf "scale=480:270,tile=5x2" -frames:v 1 \
  "${output_dir}/contact_sheet.jpg"
