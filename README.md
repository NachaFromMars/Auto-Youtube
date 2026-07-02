# Auto-Youtube 🎬

CLI automation YouTube **agent-native** chuẩn CLI-Anything.
Core = **Playwright + yt-forever-profile + HumanMode**. **Né quota Data API** (thao tác UI Studio thật như người). **HARD CAP 50 video/ngày**.

## Triết lý
- KHÔNG dùng YouTube Data API v3 → KHÔNG dính quota 10k units (~6 vid/ngày).
- Điều khiển UI YouTube Studio thật qua browser đã login sẵn (profile sống 24/7 bằng systemd).
- Mọi thao tác bọc **HumanMode** (di chuột Bézier, gõ có nhịp+typo, scroll đọc, delay ngữ nghĩa) → né bot-detection.
- Giới hạn cứng **50 video/ngày** (an toàn dưới ngưỡng tự nhiên ~50-100/24h của YouTube).

## Kiến trúc
```
auto_youtube/
├── auto_youtube_cli.py     # CLI entrypoint (Click, --json, one-shot)
├── core/
│   ├── session.py          # cầu nối CLI <-> controller qua FIFO
│   ├── limits.py           # HARD CAP 50/ngày + min-gap + per-hour
│   ├── smart.py            # đặt title + chọn audience thông minh
│   ├── studio.py           # selector map + crawl/audit flow Studio
│   └── uploader.py         # upload thật (Playwright inline + HumanMode)
└── humanmode/
    └── humanmode.py        # engine giả lập người (Bézier, typo, scroll)
```

## Hạ tầng login vĩnh viễn
- systemd service `yt-forever` (enabled+active) giữ profile login 24/7.
- Tự hồi sinh qua reboot/gateway restart. `systemctl status yt-forever`.
- Điều khiển browser qua FIFO `.yt_ctrl_fifo`.

## Commands
```bash
cd Auto-Youtube/agent-harness/cli_anything
python3 -m auto_youtube.auto_youtube_cli <command> [--json]

status            # login + rate limit
login-check       # profile còn login?
limit-status      # đã upload / còn lại hôm nay
smart-plan        # xem trước title/audience/visibility/tags (KHÔNG upload)
audit-studio      # crawl + audit toàn bộ flow Studio (cần qua verification)
upload            # upload 1 video (HumanMode, gate 50/ngày)
list-videos       # liệt kê video kênh
```

### upload
```bash
python3 -m auto_youtube.auto_youtube_cli upload \
  --file video.mp4 --title "Tiêu đề" --description "Mô tả" \
  --tags "tag1,tag2" --kids auto --visibility private \
  --schedule "2026-07-01T18:00:00" --short --dry-run
```
- `--kids auto|yes|no` — auto = smart_audience quyết định (COPPA).
- `--visibility private|unlisted|public`; có `--schedule` → scheduled.
- `--dry-run` — chỉ in plan, KHÔNG upload.

## An toàn
- KHÔNG hardcode secret/cookie/token. Pass nhập runtime, xóa ngay.
- Gate rate-limit chặn TRƯỚC khi mở browser.
- Destructive (delete/private) yêu cầu `--confirm` (module riêng).
- Screenshot + log mỗi stage khi lỗi (`Auto-Youtube/screenshots`, `logs`).

## ⚠️ Blocker hiện tại
Account `minhfrommars@gmail.com` vào Studio bị Google chặn **selfie video verification** (login từ IP VPS lạ). Cần qua verify 1 lần thì toàn bộ upload/audit chạy được. Mọi command không-Studio (status, smart-plan, dry-run) đã hoạt động.
