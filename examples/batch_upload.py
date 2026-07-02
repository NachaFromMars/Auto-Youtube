#!/usr/bin/env python3
"""Ví dụ: upload hàng loạt từ 1 danh sách, tự dừng khi chạm cap 50/ngày.
Mỗi video tôn trọng min-gap + per-hour limit (rate limiter tự lo)."""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "agent-harness", "cli_anything"))
from auto_youtube.core import uploader, limits  # noqa: E402

# Danh sách video cần upload: (path, title, description, tags)
QUEUE = [
    ("/path/video1.mp4", "Tiêu đề 1", "Mô tả 1", ["tag1"]),
    ("/path/video2.mp4", "Tiêu đề 2", "Mô tả 2", ["tag2"]),
    # ...
]

for path, title, desc, tags in QUEUE:
    ok, reason, info = limits.check_can_upload()
    if not ok:
        print(f"[STOP] {reason} — đã upload {info.get('count')}/50 hôm nay")
        break
    print(f"[UPLOAD] {title} (còn {info.get('remaining')} hôm nay)")
    res = uploader.upload(path, title, description=desc, tags=tags,
                          visibility="private")
    print("  ->", res.get("stage"), res.get("video_id") or res.get("reason"))
    time.sleep(5)  # rate limiter còn enforce min-gap riêng
