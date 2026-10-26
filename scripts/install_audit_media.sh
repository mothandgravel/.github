#!/usr/bin/env bash
# Keep media validation real while avoiding an unbounded dependency download.
set -euo pipefail

if ! command -v ffmpeg >/dev/null || ! command -v ffprobe >/dev/null; then
  # Use Ubuntu's standard HTTPS archive; repository signatures and keys stay
  # unchanged. The hosted image's Azure mirror has caused very slow downloads.
  for ci_media_source in /etc/apt/sources.list /etc/apt/sources.list.d/ubuntu.sources /etc/apt/mirrors/ubuntu.list; do
    if [ -f "$ci_media_source" ] && grep -q 'azure.archive.ubuntu.com/ubuntu' "$ci_media_source"; then
      sudo sed -i \
        -e 's#http://azure.archive.ubuntu.com/ubuntu#https://archive.ubuntu.com/ubuntu#g' \
        -e 's#https://azure.archive.ubuntu.com/ubuntu#https://archive.ubuntu.com/ubuntu#g' \
        "$ci_media_source"
    fi
  done
  sudo timeout 300 apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 update
  sudo timeout 300 apt-get -o Acquire::Retries=2 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 install -y --no-install-recommends ffmpeg
fi

ffmpeg -version | sed -n '1p'
ffprobe -version | sed -n '1p'
