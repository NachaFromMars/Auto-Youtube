"""
Rate limiter + daily quota guard cho Auto-Youtube.
HARD LIMIT: 50 video/ngày (anh Nấng chỉ thị 30/06/2026).
Lưu state JSON, reset theo ngày (giờ VN GMT+7).
"""
import json
import os
from datetime import datetime, timezone, timedelta

VN_TZ = timezone(timedelta(hours=7))
STATE_DIR = "/root/.openclaw/workspace/Auto-Youtube/state"
STATE_FILE = os.path.join(STATE_DIR, "rate_state.json")

MAX_UPLOADS_PER_DAY = 50          # HARD CAP — không bao giờ vượt
# Giới hạn mềm chống bot-detection (rải đều trong ngày)
MAX_UPLOADS_PER_HOUR = 8
MIN_GAP_SECONDS = 90              # tối thiểu giữa 2 upload


def _today_vn():
    return datetime.now(VN_TZ).strftime("%Y-%m-%d")


def _now_ts():
    return datetime.now(VN_TZ).timestamp()


def _load():
    if os.path.exists(STATE_FILE):
        try:
            return json.load(open(STATE_FILE))
        except Exception:
            pass
    return {"day": _today_vn(), "uploads": [], "count": 0}


def _save(st):
    os.makedirs(STATE_DIR, exist_ok=True)
    json.dump(st, open(STATE_FILE, "w"), ensure_ascii=False, indent=2)


def _rollover(st):
    if st.get("day") != _today_vn():
        st = {"day": _today_vn(), "uploads": [], "count": 0}
    return st


def check_can_upload():
    """Trả (ok: bool, reason: str, info: dict). KHÔNG ghi state."""
    st = _rollover(_load())
    now = _now_ts()
    count = st["count"]
    ups = st["uploads"]

    if count >= MAX_UPLOADS_PER_DAY:
        return False, f"DAILY_CAP_REACHED ({count}/{MAX_UPLOADS_PER_DAY})", {
            "count": count, "max": MAX_UPLOADS_PER_DAY, "remaining": 0}

    # per-hour
    one_hour_ago = now - 3600
    last_hour = [t for t in ups if t >= one_hour_ago]
    if len(last_hour) >= MAX_UPLOADS_PER_HOUR:
        return False, f"HOURLY_CAP ({len(last_hour)}/{MAX_UPLOADS_PER_HOUR}); chờ rải đều", {
            "count": count, "last_hour": len(last_hour)}

    # min gap
    if ups:
        gap = now - max(ups)
        if gap < MIN_GAP_SECONDS:
            return False, f"TOO_SOON (cần chờ {int(MIN_GAP_SECONDS-gap)}s)", {
                "count": count, "wait_seconds": int(MIN_GAP_SECONDS - gap)}

    return True, "OK", {"count": count, "max": MAX_UPLOADS_PER_DAY,
                        "remaining": MAX_UPLOADS_PER_DAY - count}


def record_upload(video_id=None, title=None):
    """Ghi nhận 1 upload thành công."""
    st = _rollover(_load())
    st["uploads"].append(_now_ts())
    st["count"] = st.get("count", 0) + 1
    st.setdefault("log", []).append({
        "ts": datetime.now(VN_TZ).isoformat(),
        "video_id": video_id, "title": (title or "")[:120]})
    # giữ log gọn
    st["log"] = st["log"][-200:]
    _save(st)
    return st["count"]


def status():
    st = _rollover(_load())
    now = _now_ts()
    last_hour = len([t for t in st["uploads"] if t >= now - 3600])
    return {
        "day_vn": st["day"],
        "uploaded_today": st["count"],
        "daily_cap": MAX_UPLOADS_PER_DAY,
        "remaining_today": max(0, MAX_UPLOADS_PER_DAY - st["count"]),
        "uploaded_last_hour": last_hour,
        "hourly_cap": MAX_UPLOADS_PER_HOUR,
    }
