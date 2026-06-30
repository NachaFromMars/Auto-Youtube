"""
Uploader — thực thi upload video lên YouTube Studio bằng Playwright inline,
wire HumanMode vào MỌI thao tác. Né quota (không Data API).

Vì cần thao tác file + form phức tạp, uploader mở Playwright trên CÙNG
profile yt-forever-profile. Để tránh profile-lock với controller, gọi
pause_controller() trước và resume sau (systemctl stop/start yt-forever tạm).

HARD CAP 50/ngày qua limits.check_can_upload() — chặn TRƯỚC khi mở browser.
Destructive (delete/private) ở module khác, có confirm.
"""
import os
import time
import json
import subprocess
from datetime import datetime

from . import limits
from . import smart
from . import studio
from ..humanmode import humanmode as hm

PROFILE = "/root/.openclaw/workspace/youtube-cli/yt-forever-profile"
SHOTS = "/root/.openclaw/workspace/Auto-Youtube/screenshots"
LOGS = "/root/.openclaw/workspace/Auto-Youtube/logs"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")


def _ts():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _shot(page, name):
    os.makedirs(SHOTS, exist_ok=True)
    p = os.path.join(SHOTS, f"{name}-{_ts()}.png")
    try:
        page.screenshot(path=p)
    except Exception:
        pass
    return p


def pause_controller():
    """Dừng systemd controller tạm để uploader chiếm profile."""
    subprocess.run(["systemctl", "stop", "yt-forever.service"],
                   capture_output=True, text=True)
    time.sleep(3)
    # dọn lock còn sót
    for f in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        try:
            os.remove(os.path.join(PROFILE, f))
        except FileNotFoundError:
            pass


def resume_controller():
    """Khởi động lại controller sau upload."""
    subprocess.run(["systemctl", "start", "yt-forever.service"],
                   capture_output=True, text=True)


def _first(page, sels, timeout=8000):
    """Trả locator đầu tiên match trong danh sách fallback."""
    from playwright.sync_api import TimeoutError as PWTimeout
    for s in sels:
        try:
            loc = page.locator(s).first
            loc.wait_for(state="visible", timeout=timeout)
            return loc
        except Exception:
            continue
    return None


def upload(video_path, title, description="", tags=None, made_for_kids=None,
           visibility="private", schedule_iso=None, is_short=False,
           playlist=None, thumbnail=None, dry_run=False):
    """Upload 1 video. Trả dict kết quả. Wire HumanMode toàn bộ.

    made_for_kids: None -> smart quyết định; True/False -> ép.
    visibility: private|unlisted|public|scheduled.
    """
    # ---- GATE: rate limit TRƯỚC ----
    ok, reason, info = limits.check_can_upload()
    if not ok:
        return {"ok": False, "stage": "rate_limit", "reason": reason, "info": info}

    if not os.path.exists(video_path):
        return {"ok": False, "stage": "input", "reason": f"FILE_NOT_FOUND: {video_path}"}

    # ---- Smart layer ----
    st = smart.smart_title(title, keywords=tags)
    final_title = st["value"]
    aud = smart.smart_audience(final_title, description, tags,
                               force=("kids" if made_for_kids is True else
                                      "notkids" if made_for_kids is False else None))
    mfk = aud["made_for_kids"]
    vis = visibility if not schedule_iso else "scheduled"

    plan = {
        "video": video_path, "title": final_title, "title_warnings": st["warnings"],
        "made_for_kids": mfk, "audience_reason": aud["reason"],
        "visibility": vis, "schedule": schedule_iso, "is_short": is_short,
        "tags": tags or [], "playlist": playlist, "thumbnail": thumbnail,
    }
    if dry_run:
        return {"ok": True, "stage": "dry_run", "plan": plan,
                "rate": info, "note": "dry-run: KHÔNG upload thật"}

    # ---- Thực thi ----
    os.makedirs(LOGS, exist_ok=True)
    result = {"ok": False, "plan": plan, "stage": "init"}
    pause_controller()
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                PROFILE, headless=False, user_agent=UA,
                args=["--no-sandbox", "--disable-dev-shm-usage",
                      "--disable-blink-features=AutomationControlled"],
                viewport={"width": 1366, "height": 900})
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(studio.STUDIO_URL, wait_until="domcontentloaded", timeout=60000)
            hm.human_pause("load")

            if "studio.youtube.com" not in page.url:
                result.update({"stage": "blocked", "reason": "Studio chưa mở (verification?)",
                               "url": page.url[:120], "shot": _shot(page, "blocked")})
                ctx.close()
                return result
            hm.assert_youtube_url(page.url)

            # 1) CREATE -> Upload
            btn = _first(page, studio.SELECTORS["create_button"])
            if not btn:
                result.update({"stage": "create_btn", "reason": "không thấy nút Create",
                               "shot": _shot(page, "no-create")})
                ctx.close(); return result
            hm.human_click(page, btn, "create"); hm.human_pause("between")
            um = _first(page, studio.SELECTORS["upload_menu"])
            if um:
                hm.human_click(page, um, "upload-menu")
            hm.human_pause("load")

            # 2) chọn file
            fi = _first(page, studio.SELECTORS["file_input"], timeout=12000)
            if not fi:
                result.update({"stage": "file_input", "reason": "không thấy input file",
                               "shot": _shot(page, "no-file-input")})
                ctx.close(); return result
            fi.set_input_files(video_path)
            hm.human_pause("load"); page.wait_for_timeout(6000)

            # 3) Title
            tb = _first(page, studio.SELECTORS["title_box"], timeout=20000)
            if tb:
                try:
                    tb.click(); page.keyboard.press("Control+A"); page.keyboard.press("Delete")
                except Exception:
                    pass
                hm.human_type(page, tb, final_title)
                hm.human_pause("think")
            # Description
            if description:
                db = _first(page, studio.SELECTORS["desc_box"])
                if db:
                    hm.human_type(page, db, description)
                    hm.human_pause("between")

            # Audience (made for kids) — BẮT BUỘC chọn
            key = "kids_yes" if mfk else "kids_no"
            kb = _first(page, studio.SELECTORS[key], timeout=10000)
            if kb:
                hm.human_click(page, kb, "audience")
                hm.human_pause("between")

            _shot(page, "details-filled")

            # 4-5) Next x3 (Details -> Elements -> Checks -> Visibility)
            for i in range(3):
                nb = _first(page, studio.SELECTORS["next_button"], timeout=12000)
                if nb:
                    hm.human_click(page, nb, f"next-{i}")
                    hm.human_pause("between")

            # 6) Visibility
            if vis == "scheduled" and schedule_iso:
                sr = _first(page, studio.SELECTORS["schedule_radio"], timeout=8000)
                if sr:
                    hm.human_click(page, sr, "schedule")
                    # (datepicker fill chi tiết sẽ hoàn thiện khi crawl live)
            else:
                vkey = {"public": "vis_public", "unlisted": "vis_unlisted"}.get(vis, "vis_private")
                vb = _first(page, studio.SELECTORS[vkey], timeout=8000)
                if vb:
                    hm.human_click(page, vb, f"vis-{vis}")
            hm.human_pause("think")
            _shot(page, "visibility-set")

            # 7) Done/Publish
            done = _first(page, studio.SELECTORS["done_button"], timeout=12000)
            if done:
                hm.human_click(page, done, "done")
                hm.human_pause("load"); page.wait_for_timeout(8000)

            # lấy video id
            vid = None
            try:
                link = _first(page, studio.SELECTORS["video_url_link"], timeout=8000)
                if link:
                    href = link.get_attribute("href") or ""
                    vid = href.rstrip("/").split("/")[-1] or None
            except Exception:
                pass

            _shot(page, "published")
            ctx.close()

            limits.record_upload(video_id=vid, title=final_title)
            result.update({"ok": True, "stage": "published", "video_id": vid,
                           "rate_after": limits.status()})
            return result
    except Exception as e:
        result.update({"stage": "exception", "reason": str(e)[:300]})
        return result
    finally:
        resume_controller()
