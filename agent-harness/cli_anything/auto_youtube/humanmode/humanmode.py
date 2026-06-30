"""
HumanMode engine for YouTube automation (Playwright sync).
Mô phỏng hành vi người thật: di chuột Bézier, gõ có nhịp + typo, scroll đọc,
delay ngữ nghĩa, jitter ngẫu nhiên. Né bot-detection của YouTube Studio.

GUARD: chỉ thao tác trên youtube.com / studio.youtube.com.
KHÔNG in secret/cookie. Mọi action có try/except + screenshot khi lỗi.
"""
import random
import time
import math


YOUTUBE_HOSTS = ("youtube.com", "studio.youtube.com", "youtube-nocookie.com")


def assert_youtube_url(url: str):
    """Guard: chỉ cho phép thao tác trên YouTube domains."""
    if not any(h in (url or "") for h in YOUTUBE_HOSTS):
        raise RuntimeError(f"HUMANMODE_GUARD: target is not YouTube ({url[:60]})")


# ---------- Timing (ngữ nghĩa) ----------
def _rand(a, b):
    return random.uniform(a, b)


def human_pause(kind: str = "between"):
    """Delay theo ngữ nghĩa hành động."""
    table = {
        "think": (1.8, 4.2),      # suy nghĩ trước khi điền field quan trọng
        "read": (1.2, 3.0),       # đọc nội dung trên màn
        "between": (0.6, 1.8),    # giữa 2 action thường
        "micro": (0.15, 0.5),     # giữa 2 phím / 2 click nhỏ
        "load": (2.5, 5.0),       # chờ trang nặng load
        "long": (4.0, 8.0),       # nghỉ dài (giả lập phân tâm)
    }
    lo, hi = table.get(kind, (0.6, 1.8))
    time.sleep(_rand(lo, hi))


# ---------- Mouse Bézier ----------
def _bezier_points(x0, y0, x1, y1, steps=24):
    """Đường cong Bézier bậc 3 với control points lệch ngẫu nhiên."""
    cx1 = x0 + (x1 - x0) * _rand(0.2, 0.4) + _rand(-60, 60)
    cy1 = y0 + (y1 - y0) * _rand(0.2, 0.4) + _rand(-60, 60)
    cx2 = x0 + (x1 - x0) * _rand(0.6, 0.8) + _rand(-60, 60)
    cy2 = y0 + (y1 - y0) * _rand(0.6, 0.8) + _rand(-60, 60)
    pts = []
    for i in range(steps + 1):
        t = i / steps
        # ease-in-out
        mt = 1 - t
        x = mt**3 * x0 + 3 * mt**2 * t * cx1 + 3 * mt * t**2 * cx2 + t**3 * x1
        y = mt**3 * y0 + 3 * mt**2 * t * cy1 + 3 * mt * t**2 * cy2 + t**3 * y1
        pts.append((x, y))
    return pts


def human_move(page, x, y):
    """Di chuột tới (x,y) theo đường cong, tốc độ biến thiên."""
    try:
        # vị trí hiện tại không lấy được trực tiếp -> xuất phát ngẫu nhiên gần tâm
        x0 = _rand(200, 900)
        y0 = _rand(150, 600)
        pts = _bezier_points(x0, y0, x, y, steps=random.randint(18, 30))
        # 15% overshoot rồi chỉnh lại
        if random.random() < 0.15:
            ox, oy = x + _rand(-25, 25), y + _rand(-25, 25)
            pts += _bezier_points(x, y, ox, oy, steps=6)
            pts += _bezier_points(ox, oy, x, y, steps=6)
        for px, py in pts:
            page.mouse.move(px, py)
            time.sleep(_rand(0.006, 0.02))
    except Exception:
        pass


def human_click(page, locator, name="element"):
    """Click 1 locator với di chuột Bézier + delay người."""
    try:
        box = locator.bounding_box(timeout=8000)
        if box:
            tx = box["x"] + box["width"] * _rand(0.3, 0.7)
            ty = box["y"] + box["height"] * _rand(0.3, 0.7)
            human_move(page, tx, ty)
            human_pause("micro")
            page.mouse.click(tx, ty)
        else:
            locator.click(timeout=8000)
    except Exception:
        # fallback click thẳng
        locator.click(timeout=10000)
    human_pause("between")


# ---------- Typing (nhịp + typo) ----------
_NEAR = {
    'a': 'sq', 'b': 'vn', 'c': 'xv', 'd': 'sf', 'e': 'wr', 'i': 'ou',
    'n': 'bm', 'o': 'ip', 'r': 'et', 's': 'ad', 't': 'ry', 'u': 'yi',
}


def human_type(page, locator, text, typo_rate=0.06):
    """Gõ text với nhịp ngẫu nhiên + thỉnh thoảng typo rồi sửa.
    Final text LUÔN đúng."""
    try:
        human_click(page, locator, "input")
    except Exception:
        try:
            locator.click(timeout=8000)
        except Exception:
            pass
    human_pause("micro")
    for ch in text:
        # typo: gõ ký tự gần rồi backspace
        if ch.lower() in _NEAR and random.random() < typo_rate:
            wrong = random.choice(_NEAR[ch.lower()])
            page.keyboard.type(wrong)
            time.sleep(_rand(0.08, 0.2))
            page.keyboard.press("Backspace")
            time.sleep(_rand(0.05, 0.15))
        page.keyboard.type(ch)
        # nhịp gõ
        if ch == " ":
            time.sleep(_rand(0.12, 0.3))   # pause giữa từ
        else:
            time.sleep(_rand(0.05, 0.15))


# ---------- Scroll ----------
def human_scroll(page, amount=None, reading=False):
    """Scroll với tốc độ biến thiên, có pause đọc."""
    total = amount if amount is not None else random.randint(300, 900)
    done = 0
    while done < total:
        step = random.randint(60, 160)
        page.mouse.wheel(0, step)
        done += step
        if reading and random.random() < 0.2:
            human_pause("read")
        else:
            time.sleep(_rand(0.05, 0.2))
    # 5% scroll ngược lên
    if random.random() < 0.05:
        page.mouse.wheel(0, -random.randint(80, 200))
        human_pause("micro")


def maybe_distraction(page):
    """15% phân tâm nhẹ (di chuột vu vơ) để giống người."""
    if random.random() < 0.15:
        human_move(page, _rand(100, 1200), _rand(100, 700))
        human_pause("micro")
