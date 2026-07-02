"""
Smart layer — đặt tiêu đề + chọn đối tượng (audience) thông minh khi upload.

KHÔNG gọi LLM bắt buộc (chạy offline được). Heuristic + rule-based:
- smart_title: tối ưu title theo best-practice YouTube (độ dài, từ khoá đầu,
  emoji vừa phải, tránh clickbait quá đà, giữ tiếng Việt có dấu).
- smart_audience: quyết định "made for kids" (COPPA) + age-restrict từ nội dung.
- suggest_tags / suggest_visibility: gợi ý tags + chế độ hiển thị.

Mọi hàm trả dict có 'value' + 'reason' để audit minh bạch.
"""
import re

# Từ khoá báo hiệu nội dung TRẺ EM (made for kids = True)
KIDS_SIGNALS = [
    "thiếu nhi", "trẻ em", "bé học", "cho bé", "mầm non", "hoạt hình",
    "nursery", "kids", "cartoon", "abc", "đồ chơi", "kể chuyện cổ tích",
    "bài hát thiếu nhi", "tập tô màu", "học đếm", "học chữ",
]
# Từ khoá NGƯỜI LỚN / nhạy cảm (KHÔNG phải kids, có thể age-restrict)
MATURE_SIGNALS = [
    "18+", "kinh dị", "horror", "bạo lực", "máu me", "cờ bạc",
    "cá độ", "rượu", "thuốc lá", "chính trị nhạy cảm",
]

MAX_TITLE = 100          # YouTube hard limit
RECOMMENDED_TITLE = 70   # hiển thị đẹp không bị cắt


def smart_title(raw: str, keywords=None, add_emoji=True) -> dict:
    """Tối ưu title. Trả {'value','reason','warnings'}."""
    warnings = []
    title = (raw or "").strip()
    title = re.sub(r"\s+", " ", title)
    if not title:
        return {"value": "", "reason": "empty input", "warnings": ["EMPTY_TITLE"]}

    # đưa keyword chính lên đầu nếu chưa có
    if keywords:
        kw = keywords[0].strip()
        if kw and kw.lower() not in title.lower()[:40]:
            title = f"{kw} | {title}"
            warnings.append("prepended_primary_keyword")

    # cắt theo limit nhưng giữ nguyên từ
    if len(title) > MAX_TITLE:
        cut = title[:MAX_TITLE].rsplit(" ", 1)[0]
        title = cut
        warnings.append(f"truncated_to_{MAX_TITLE}")
    if len(title) > RECOMMENDED_TITLE:
        warnings.append(f"longer_than_recommended_{RECOMMENDED_TITLE}")

    # emoji vừa phải: tối đa 1, chỉ thêm nếu chưa có emoji
    if add_emoji and not re.search(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", title):
        # không tự ý thêm emoji random -> để None, chỉ flag gợi ý
        warnings.append("no_emoji_consider_adding_one")

    # clickbait quá đà
    if re.search(r"(SỐC|CHẤN ĐỘNG|KHÔNG THỂ TIN|!!!!+)", title, re.I):
        warnings.append("possible_overclickbait")

    return {"value": title, "reason": "optimized", "warnings": warnings}


def smart_audience(title="", description="", tags=None, force=None) -> dict:
    """Quyết định made_for_kids + age_restrict.
    force: 'kids' | 'notkids' | None để override thủ công."""
    blob = " ".join([title or "", description or "", " ".join(tags or [])]).lower()
    kids_hits = [s for s in KIDS_SIGNALS if s in blob]
    mature_hits = [s for s in MATURE_SIGNALS if s in blob]

    if force == "kids":
        return {"made_for_kids": True, "age_restrict": False,
                "reason": "forced kids", "signals": kids_hits}
    if force == "notkids":
        return {"made_for_kids": False, "age_restrict": bool(mature_hits),
                "reason": "forced not-kids", "signals": mature_hits}

    # mặc định AN TOÀN PHÁP LÝ: nếu không chắc -> NOT made for kids
    # (sai "kids" gây tắt comment/cá nhân hoá; nhưng made-for-kids sai luật COPPA nặng hơn -> để creator chủ động)
    made_for_kids = bool(kids_hits) and not mature_hits
    return {
        "made_for_kids": made_for_kids,
        "age_restrict": bool(mature_hits),
        "reason": "heuristic: kids signals present" if made_for_kids
                  else "default not-for-kids (no/weak kids signal)",
        "kids_signals": kids_hits,
        "mature_signals": mature_hits,
        "note": "Creator NÊN xác nhận made_for_kids — đây là khai báo pháp lý COPPA.",
    }


def suggest_visibility(schedule_iso=None, is_short=False) -> dict:
    """Gợi ý visibility. Có schedule -> private+scheduled; không -> mặc định private (an toàn)."""
    if schedule_iso:
        return {"value": "scheduled", "publish_at": schedule_iso,
                "reason": "có lịch -> đặt scheduled (private tới giờ)"}
    return {"value": "private", "reason": "mặc định private để review trước khi public"}


def suggest_tags(title="", description="", extra=None, limit=15) -> dict:
    """Gợi ý tags từ title/description (tách từ khoá, lọc stopword đơn giản)."""
    blob = f"{title} {description}".lower()
    words = re.findall(r"[a-zà-ỹ0-9]{3,}", blob)
    stop = {"và", "của", "cho", "với", "the", "and", "for", "này", "những",
            "được", "một", "các", "trong", "không", "you", "your"}
    seen, tags = set(), []
    for w in words:
        if w in stop or w in seen:
            continue
        seen.add(w)
        tags.append(w)
        if len(tags) >= limit:
            break
    for e in (extra or []):
        if e.lower() not in seen and len(tags) < limit:
            tags.append(e.lower())
    return {"value": tags, "count": len(tags), "reason": "extracted from title+desc"}
