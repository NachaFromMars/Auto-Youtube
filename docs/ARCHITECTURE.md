# Architecture — Auto-Youtube

## Tổng quan
Auto-Youtube điều khiển **UI YouTube Studio thật** qua browser đã login sẵn, thay vì gọi YouTube Data API. Lý do: Data API giới hạn ~6 video/ngày (10k units, upload tốn 1.6k). Browser automation chỉ dính giới hạn tự nhiên của YouTube (~50–100/24h) → cao hơn nhiều, và dùng được session login sẵn.

```
┌─────────────┐   FIFO    ┌──────────────────┐   CDP/Playwright   ┌─────────────┐
│  CLI (Click)│ ────────► │ yt_login_controller│ ─────────────────► │  Chromium   │
│ auto_youtube│ ◄──────── │  (systemd-kept)   │ ◄───────────────── │ yt-forever  │
└─────────────┘  log JSON └──────────────────┘                     │  profile    │
       │                                                            └─────────────┘
       │ inline Playwright (upload thật, pause controller)
       └──────────────────────────────────────────────────────────► (cùng profile)
```

## Module
| Module | Vai trò |
|---|---|
| `auto_youtube_cli.py` | Entrypoint Click, `--json`, one-shot commands |
| `core/session.py` | Bridge CLI ↔ controller qua FIFO (`.yt_ctrl_fifo`) |
| `core/limits.py` | HARD CAP 50/ngày + 8/giờ + min-gap 90s, state JSON |
| `core/smart.py` | Title optimize + audience (COPPA) + visibility + tags |
| `core/studio.py` | Selector map (fallback chains) + 10-screen audit + crawl resolver |
| `core/uploader.py` | Upload thật (Playwright inline) + HumanMode + gate rate-limit |
| `humanmode/humanmode.py` | Engine giả lập người: Bézier mouse, typo typing, scroll, pauses, guard |

## Hai chế độ điều khiển browser
1. **Qua controller (FIFO)** — điều hướng nhẹ (goto, eval, dump_dom, check_login). Controller sống 24/7 bằng systemd, giữ profile login.
2. **Inline Playwright** — upload file + form phức tạp. Trước khi mở, `pause_controller()` (systemctl stop) để tránh profile-lock, xong `resume_controller()`.

## Vòng đời upload (long + short)
```
check_can_upload (GATE 50/ngày)
  → smart_title + smart_audience
  → pause_controller
  → Studio: Create → Upload → file
  → Details: title, desc, audience(kids), tags, thumbnail, playlist
  → Elements (cards/end screen) → Checks → Visibility
  → Publish/Schedule → video_id
  → record_upload (+1 cap) → resume_controller
```

## An toàn
- Không hardcode secret; pass nhập runtime, xóa ngay; cookie/profile trong `.gitignore`.
- Gate rate-limit chạy TRƯỚC khi mở browser → không bao giờ vượt 50/ngày.
- Screenshot + log mỗi stage khi lỗi.
- Destructive (delete/private) yêu cầu `--confirm`.
- `assert_youtube_url()` chặn thao tác ngoài youtube.com.
