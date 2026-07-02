"""
Auto-Reply — tự quét inbox comment, phân loại, reply thông minh.

Pipeline:
  1. list_comments(unresponded ưu tiên) → lọc comment CHƯA reply + KHÔNG phải chủ kênh
  2. classify() — phân loại: praise / question / request / spam / negative / generic
  3. pick_reply() — chọn reply theo loại (template pool, random không lặp)
  4. reply + ghi state (đã reply comment nào → không reply trùng)

State: state/autoreply_state.json (fingerprint = author+text[:80])
An toàn:
  - KHÔNG reply spam/negative — chỉ đánh dấu để chủ kênh xem
  - Cap mặc định 20 reply/lần chạy, nghỉ 8-20s giữa các reply (human-like)
  - dry_run=True để xem plan trước
"""
import hashlib
import json
import os
import random
import time

from . import comments as cm

WS = "/root/.openclaw/workspace/Auto-Youtube"
STATE_FILE = os.path.join(WS, "state", "autoreply_state.json")

# ---- phân loại ----
PATTERNS = {
    "spam": ["http://", "https://", "sub4sub", "sub cheo", "vào kênh mình",
             "check my", "làm giàu", "kiếm tiền online", "telegram", "zalo",
             "casino", "cá cược", "18+"],
    "negative": ["dở", "tệ", "rác", "phí thời gian", "dislike", "báo cáo",
                 "lừa đảo", "ăn cắp", "reup", "trash", "worst"],
    "question": ["?", "sao ", "làm sao", "như thế nào", "ở đâu", "khi nào",
                 "bao giờ", "là gì", "how ", "what ", "where ", "why ", "when "],
    "request": ["làm video", "ra video", "phần 2", "part 2", "tiếp theo",
                "request", "yêu cầu", "mong bạn", "mong ad", "cho xin"],
    "praise": ["hay", "tuyệt", "đỉnh", "thích", "yêu", "cảm ơn", "thanks",
               "thank you", "great", "awesome", "amazing", "love", "good",
               "an lạc", "an nhiên", "bình yên", "tâm an", "nhẹ nhàng", "🙏", "❤", "😍"],
}

REPLY_POOL = {
    "praise": [
        "Cảm ơn bạn nhiều nha 🙏 Chúc bạn một ngày an lành!",
        "Rất vui vì bạn thích video 🪷 Cảm ơn bạn đã ghé xem!",
        "Cảm ơn lời động viên của bạn 🙏 Sẽ còn nhiều video hay nữa, đón xem nhé!",
        "Thương bạn 🤍 Chúc bạn luôn bình an và hạnh phúc!",
    ],
    "question": [
        "Cảm ơn câu hỏi của bạn 🙏 Mình sẽ trả lời chi tiết trong video sắp tới nhé!",
        "Câu hỏi hay quá! Bạn theo dõi kênh để không bỏ lỡ phần giải đáp nha 🪷",
    ],
    "request": [
        "Cảm ơn gợi ý của bạn 🙏 Mình ghi nhận và sẽ cân nhắc làm trong thời gian tới nhé!",
        "Ý tưởng hay đó! Mình note lại rồi, đón chờ video sắp tới nha 🪷",
    ],
    "generic": [
        "Cảm ơn bạn đã ghé xem 🙏 Chúc bạn một ngày tốt lành!",
        "Cảm ơn bạn đã ủng hộ kênh 🪷 Hẹn gặp lại ở video sau!",
    ],
}


def classify(text):
    """Phân loại comment. Ưu tiên: spam > negative > question > request > praise > generic."""
    t = (text or "").lower()
    for kind in ("spam", "negative", "question", "request", "praise"):
        if any(p in t for p in PATTERNS[kind]):
            return kind
    return "generic"


def _fingerprint(author, text):
    return hashlib.sha256(f"{author}|{(text or '')[:80]}".encode()).hexdigest()[:16]


def _load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"replied": {}, "flagged": {}}


def _save_state(st):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)


def pick_reply(kind, state, rng=None):
    """Chọn reply từ pool, tránh lặp câu vừa dùng gần nhất cho loại đó."""
    rng = rng or random
    pool = REPLY_POOL.get(kind, REPLY_POOL["generic"])
    last = state.get("last_used", {}).get(kind)
    choices = [p for p in pool if p != last] or pool
    reply = rng.choice(choices)
    state.setdefault("last_used", {})[kind] = reply
    return reply


def run(session, limit=20, max_replies=20, dry_run=False, channel_handle=None):
    """Quét inbox + auto-reply. Trả report chi tiết từng comment."""
    st = _load_state()
    listing = cm.list_comments(session, limit=limit)
    if not listing.get("ok"):
        return {"ok": False, "reason": "không đọc được inbox", "detail": listing}

    report = {"ok": True, "scanned": listing["count"], "replied": [],
              "skipped": [], "flagged": [], "dry_run": dry_run}
    n_replied = 0
    for c in listing["comments"]:
        author = c.get("author", "")
        text = c.get("text", "")
        fp = _fingerprint(author, text)
        # chủ kênh tự comment → bỏ qua (tránh self-reply loop)
        if channel_handle and channel_handle.lower() in author.lower():
            report["skipped"].append({"author": author, "reason": "own_channel"})
            continue
        if fp in st["replied"]:
            report["skipped"].append({"author": author, "reason": "already_replied"})
            continue
        kind = classify(text)
        if kind in ("spam", "negative"):
            st["flagged"][fp] = {"author": author, "text": text[:100], "kind": kind,
                                 "ts": time.strftime("%Y-%m-%d %H:%M")}
            report["flagged"].append({"author": author, "kind": kind, "text": text[:80]})
            continue
        if n_replied >= max_replies:
            report["skipped"].append({"author": author, "reason": "max_replies_reached"})
            continue
        reply_text = pick_reply(kind, st)
        entry = {"index": c["index"], "author": author, "kind": kind,
                 "comment": text[:80], "reply": reply_text}
        if dry_run:
            entry["status"] = "DRY_RUN"
            report["replied"].append(entry)
            n_replied += 1
            continue
        res = cm.reply_comment(session, c["index"], reply_text, _skip_nav=True)
        entry["status"] = "OK" if res.get("ok") else f"FAIL:{res.get('steps')}"
        if res.get("ok"):
            st["replied"][fp] = {"author": author, "kind": kind,
                                 "ts": time.strftime("%Y-%m-%d %H:%M")}
            n_replied += 1
        report["replied"].append(entry)
        # human-like gap giữa các reply
        time.sleep(random.uniform(8, 20))
    if not dry_run:
        _save_state(st)
    report["total_replied"] = n_replied
    return report
