#!/usr/bin/env bash

set -euo pipefail

output_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
frame_dir="${output_dir}/qa_frames_batch2"
run_ids=(3ah12ywt f5v4oslz rkggyjt6 k0k3zj03 mdwpqq1y 8x2t09lj pzmtv0g9 mszqi6jy)

mkdir -p "${frame_dir}"
for run_id in "${run_ids[@]}"; do
  videos=("${output_dir}"/*_"${run_id}".mp4)
  video="${videos[0]}"
  name="$(basename "${video}" .mp4)"
  ffmpeg -loglevel error -y -ss 5 -i "${video}" -frames:v 1 \
    "${frame_dir}/${name}.jpg"
done

ffmpeg -loglevel error -y -pattern_type glob -i "${frame_dir}/*.jpg" \
  -vf "scale=480:270,tile=4x2" -frames:v 1 \
  "${output_dir}/contact_sheet_batch2.jpg"
