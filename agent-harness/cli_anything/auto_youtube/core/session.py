"""
Session manager — cầu nối CLI <-> Chrome thật qua CDP (Chrome DevTools Protocol).

Chrome headful sống mãi do systemd yt-forever (yt-gui-keeper.sh) với:
  --remote-debugging-port=18801  (loopback)
Ưu điểm so với FIFO controller cũ: ổn định (không crash SIGTRAP), thao tác
đồng bộ trực tiếp, headful nên KHÔNG bị Google chặn "browser not secure".

API giữ nguyên tương thích module cũ (manager/comments/analytics):
  goto, evaluate, dump_dom, snapshot, wait_ms, check_login, is_logged_in
Thêm: set_authuser() để chuyển account (multi-acc).

KHÔNG in secret. Mọi lệnh có timeout.
"""
import json
import os
import time

WS = "/root/.openclaw/workspace"
CDP_URL = os.environ.get("YT_CDP_URL", "http://127.0.0.1:18801")
CRAWL_DIR = os.path.join(WS, "Auto-Youtube/crawl-data")
SHOTS = os.path.join(WS, "youtube-cli")

# authuser hiện hành cho các thao tác goto (0 = mặc định). set_authuser() đổi.
_AUTHUSER = None


class ControllerError(RuntimeError):
    pass


def set_authuser(authuser):
    """Đặt authuser cho các lệnh goto kế tiếp (None = không chèn)."""
    global _AUTHUSER
    _AUTHUSER = None if authuser is None else int(authuser)


def _with_authuser(url):
    if _AUTHUSER is None:
        return url
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}authuser={_AUTHUSER}"


def _connect(pw):
    try:
        b = pw.chromium.connect_over_cdp(CDP_URL, timeout=15000)
    except Exception as e:
        raise ControllerError(
            f"CDP_CONNECT_FAIL ({CDP_URL}): Chrome keeper chưa chạy? "
            f"(systemctl status yt-forever) — {e}")
    if not b.contexts:
        raise ControllerError("CDP_NO_CONTEXT: chrome không có context nào")
    return b


def _yt_page(ctx):
    """Lấy 1 page YouTube/Studio đang mở, hoặc tạo mới."""
    for p in ctx.pages:
        u = (p.url or "")
        if "youtube.com" in u:
            return p, False
    return ctx.new_page(), True


def _run(fn, timeout=60.0):
    """Mở CDP, chạy fn(page)->dict, đóng. fn nhận page live."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = _connect(pw)
        ctx = b.contexts[0]
        page, created = _yt_page(ctx)
        try:
            return fn(page)
        finally:
            # KHÔNG đóng tab gốc (giữ tab YouTube sống); chỉ đóng tab tự tạo tạm
            if created:
                try:
                    page.close()
                except Exception:
                    pass


def _shot(page, name):
    os.makedirs(SHOTS, exist_ok=True)
    p = os.path.join(SHOTS, f"{name}.png")
    try:
        page.screenshot(path=p)
    except Exception:
        pass
    return p


def check_login():
    def fn(page):
        if "youtube.com" not in (page.url or ""):
            page.goto("https://www.youtube.com/", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2500)
        li = page.evaluate("()=>{try{return !!(window.ytcfg&&ytcfg.get('LOGGED_IN'))}catch(e){return false}}")
        si = page.evaluate("()=>{try{return ytcfg.get('SESSION_INDEX')}catch(e){return null}}")
        return {"ok": True, "logged_in": bool(li), "session_index": si, "url": page.url}
    return _run(fn, timeout=45)


def is_logged_in():
    try:
        return bool(check_login().get("logged_in"))
    except ControllerError:
        return False


def goto(url, wait_ms=5000, name="nav"):
    target = _with_authuser(url)

    def fn(page):
        page.goto(target, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(wait_ms)
        shot = _shot(page, name)
        txt = ""
        try:
            txt = page.locator("body").inner_text(timeout=5000)[:1500]
        except Exception:
            pass
        return {"ok": True, "url": page.url, "shot": shot, "text": txt}
    return _run(fn, timeout=max(40, wait_ms / 1000 + 30))


def evaluate(js, save=None):
    def fn(page):
        val = page.evaluate(js)
        out = {"ok": True, "url": page.url, "value": val}
        if save:
            os.makedirs(CRAWL_DIR, exist_ok=True)
            sp = os.path.join(CRAWL_DIR, f"{save}.json")
            open(sp, "w", encoding="utf-8").write(json.dumps(val, ensure_ascii=False, indent=2))
            out["saved"] = sp
        return out
    return _run(fn, timeout=45)


def dump_dom(name="dom"):
    def fn(page):
        html = page.content()
        os.makedirs(CRAWL_DIR, exist_ok=True)
        sp = os.path.join(CRAWL_DIR, f"{name}.html")
        open(sp, "w", encoding="utf-8").write(html)
        _shot(page, name)
        return {"ok": True, "url": page.url, "dom_saved": sp, "len": len(html)}
    return _run(fn, timeout=45)


def snapshot(name="snap"):
    def fn(page):
        shot = _shot(page, name)
        txt = ""
        try:
            txt = page.locator("body").inner_text(timeout=5000)[:1500]
        except Exception:
            pass
        return {"ok": True, "url": page.url, "shot": shot, "text": txt}
    return _run(fn, timeout=30)


def wait_ms(ms=3000):
    def fn(page):
        page.wait_for_timeout(ms)
        return {"ok": True, "waited": ms}
    return _run(fn, timeout=ms / 1000 + 15)
