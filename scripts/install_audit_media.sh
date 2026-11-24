#!/usr/bin/env bash
# Keep media validation real while avoiding an unbounded dependency download.
set -euo pipefail

if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then
  # Use Ubuntu's standard HTTPS archive; repository signatures and keys stay
  # unchanged. Azure and EC2 runner mirrors have timed out downloading FFmpeg.
  ci_media_mirror='https?://(azure|[a-z0-9-]+\.ec2)\.archive\.ubuntu\.com/ubuntu'
  for ci_media_source in \
    /etc/apt/sources.list \
    /etc/apt/sources.list.d/ubuntu.sources \
    /etc/apt/mirrors/ubuntu.list \
    /etc/apt/apt-mirrors.txt; do
    if [ -f "$ci_media_source" ] && grep -Eq "$ci_media_mirror" "$ci_media_source"; then
      sudo sed -Ei "s#${ci_media_mirror}#https://archive.ubuntu.com/ubuntu#g" "$ci_media_source"
    fi
  done
  sudo timeout 300 apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 update
  sudo timeout 300 apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 install -y --no-install-recommends ffmpeg
fi

ffmpeg -version | sed -n '1p'
ffprobe -version | sed -n '1p'
