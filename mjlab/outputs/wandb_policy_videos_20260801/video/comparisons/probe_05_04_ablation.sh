#!/usr/bin/env bash

set -euo pipefail

video_root="/mnt/d/GMR_WORK/mjlab/outputs/wandb_policy_videos_20260801/video/ablation"
run_ids=(09yrh4qp y84gf3sj 6rlspqk0 p6vbd18i 6gq87ju7 q2l4sxxn)

for run_id in "${run_ids[@]}"; do
  filename=("${video_root}"/*"${run_id}".mp4)
  printf '%s ' "$(basename "${filename[0]}")"
  ffprobe -v error -select_streams v:0 \
    -show_entries stream=width,height,r_frame_rate,nb_frames \
    -show_entries format=duration -of compact=p=0:nk=1 "${filename[0]}"
done
