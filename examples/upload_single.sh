#!/usr/bin/env bash
# Ví dụ: upload 1 video long với smart audience + schedule.
set -euo pipefail
cd "$(dirname "$0")/../agent-harness/cli_anything"

# 1) Xem plan trước (KHÔNG upload)
python3 -m auto_youtube.auto_youtube_cli smart-plan \
  --title "Thiền định cho người mới bắt đầu" \
  --description "Hướng dẫn thiền cơ bản 10 phút mỗi ngày" \
  --tags "thiền,meditation,mindfulness"

# 2) Dry-run upload (kiểm tra gate + smart layer)
python3 -m auto_youtube.auto_youtube_cli upload \
  --file ./video.mp4 \
  --title "Thiền định cho người mới bắt đầu" \
  --description "Hướng dẫn thiền cơ bản" \
  --tags "thiền,meditation" \
  --kids no \
  --visibility private \
  --dry-run

# 3) Upload thật (bỏ --dry-run). Cần Studio đã qua verification.
# python3 -m auto_youtube.auto_youtube_cli upload \
#   --file ./video.mp4 --title "..." --visibility public
