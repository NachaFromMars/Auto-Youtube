"""
Optimizer — tối ưu trước khi upload (pure Python, không cần browser).

  best_time()      — giờ vàng đăng bài theo loại nội dung + ngày trong tuần (giờ VN)
  optimize_seo()   — gói tối ưu title/description/tags/hashtags một phát
  next_slot()      — slot đăng tiếp theo (ISO) dựa trên giờ vàng + rate limit
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import smart

VN = ZoneInfo("Asia/Ho_Chi_Minh")

# Giờ vàng (giờ VN) theo nghiên cứu chung về audience Việt + YouTube CTR:
# - Shorts: sáng đi làm / trưa nghỉ / tối lướt
# - Long: tối sau ăn cơm là prime; cuối tuần thêm khung trưa
GOLDEN_HOURS = {
    "short": {
        "weekday": [7, 12, 20],
        "weekend": [9, 12, 20, 22],
    },
    "long": {
        "weekday": [19, 20, 21],
        "weekend": [11, 19, 20, 21],
    },
}

HASHTAG_MAP = {
    "thiền": ["#thiền", "#meditation", "#tĩnhtâm"],
    "meditation": ["#meditation", "#mindfulness", "#relax"],
    "nhạc": ["#music", "#nhac", "#relaxingmusic"],
    "phật": ["#phậtpháp", "#buddhism", "#antâm"],
    "trading": ["#trading", "#crypto", "#investing"],
    "học": ["#hoctap", "#education", "#kienthuc"],
    "game": ["#gaming", "#gameplay", "#gamer"],
    "nấu": ["#nauan", "#cooking", "#amthuc"],
    "du lịch": ["#dulich", "#travel", "#vietnam"],
    "review": ["#review", "#danhgia"],
}


def best_time(kind="long", when=None):
    """Trả các khung giờ vàng (giờ VN) cho hôm nay/ngày chỉ định."""
    now = when or datetime.now(VN)
    day_type = "weekend" if now.weekday() >= 5 else "weekday"
    hours = GOLDEN_HOURS.get(kind, GOLDEN_HOURS["long"])[day_type]
    return {"kind": kind, "date": now.strftime("%Y-%m-%d"), "day_type": day_type,
            "golden_hours_vn": hours,
            "note": "Giờ VN. Shorts: sáng/trưa/tối lướt; Long: prime-time tối."}


def next_slot(kind="long", after=None, min_gap_hours=2):
    """Slot ISO tiếp theo còn trống theo giờ vàng, cách `after` >= min_gap_hours."""
    now = after or datetime.now(VN)
    for day_offset in range(0, 7):
        d = (now + timedelta(days=day_offset)).replace(minute=0, second=0, microsecond=0)
        day_type = "weekend" if d.weekday() >= 5 else "weekday"
        for h in GOLDEN_HOURS.get(kind, GOLDEN_HOURS["long"])[day_type]:
            slot = d.replace(hour=h)
            if slot > now + timedelta(hours=min_gap_hours):
                return {"kind": kind, "slot_vn": slot.strftime("%Y-%m-%dT%H:%M:%S"),
                        "human": slot.strftime("%a %d/%m %H:%M (VN)")}
    return {"kind": kind, "slot_vn": None}


def suggest_hashtags(title="", description="", limit=5):
    text = f"{title} {description}".lower()
    tags = []
    for kw, hts in HASHTAG_MAP.items():
        if kw in text:
            for h in hts:
                if h not in tags:
                    tags.append(h)
    return tags[:limit]


def optimize_seo(title, description="", tags=None, is_short=False):
    """Gói tối ưu 1 phát: title + desc (hashtag chèn cuối) + tags + giờ vàng."""
    tag_list = list(tags or [])
    st = smart.smart_title(title, keywords=tag_list)
    hashtags = suggest_hashtags(title, description)
    if is_short and "#shorts" not in [h.lower() for h in hashtags]:
        hashtags.insert(0, "#Shorts")
    desc = description.rstrip()
    existing = desc.lower()
    add = [h for h in hashtags if h.lower() not in existing]
    if add:
        desc = (desc + "\n\n" + " ".join(add)).strip()
    tg = smart.suggest_tags(title, description, extra=tag_list)
    kind = "short" if is_short else "long"
    return {
        "title": st,
        "description": desc,
        "hashtags": hashtags,
        "tags": tg,
        "best_time": best_time(kind),
        "next_slot": next_slot(kind),
    }
