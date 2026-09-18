#!/usr/bin/env bash

set -euo pipefail

root_dir="/mnt/d/GMR_WORK/mjlab/outputs/wandb_policy_videos_20260801"
output_dir="${root_dir}/video/comparisons"
frame_dir="${output_dir}/f4_alignment_candidates"
font_file="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
ppo_video="${root_dir}/video/ppo/135_04_gmr_0uclfphn.mp4"
f4_video="${root_dir}/video/future frames/135_04_gmr_future_F4_0h5k9qzz.mp4"

mkdir -p "${frame_dir}"
ffmpeg -loglevel error -y -i "${ppo_video}" \
  -vf "select=eq(n\,250),crop=1000:1000:460:80,scale=360:360,drawbox=x=0:y=0:w=iw:h=48:color=black@0.82:t=fill,drawtext=fontfile=${font_file}:text='TARGET PPO F250':fontcolor=white:fontsize=22:x=10:y=11" \
  -frames:v 1 "${frame_dir}/00.png"

index=1
for frame_number in $(seq 310 2 350); do
  printf -v frame_name '%02d.png' "${index}"
  ffmpeg -loglevel error -y -i "${f4_video}" \
    -vf "select=eq(n\,${frame_number}),crop=1000:1000:460:80,scale=360:360,drawbox=x=0:y=0:w=iw:h=48:color=black@0.82:t=fill,drawtext=fontfile=${font_file}:text='F4 FRAME ${frame_number}':fontcolor=white:fontsize=22:x=10:y=11" \
    -frames:v 1 "${frame_dir}/${frame_name}"
  index=$((index + 1))
done

ffmpeg -loglevel error -y -framerate 1 -i "${frame_dir}/%02d.png" \
  -vf "tile=6x4" -frames:v 1 "${output_dir}/f4_alignment_candidates.png"
