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


def _fill_schedule(page, schedule_iso):
    """Điền schedule trên Visibility step. schedule_iso: 'YYYY-MM-DDTHH:MM' (giờ VN;
    Studio hiển thị theo timezone account).

    DOM verified live 02/07/2026 (video sDTHTxLdLPM):
    - Schedule là section COLLAPSED → phải click #second-container-expand-button trước
    - Expand xong: #datepicker-trigger (date dropdown) + input value 'HH:MM' (time)
    - Time: click input → dropdown tp-yt-paper-item chứa giờ 15' → pick; fallback gõ
    """
    from datetime import datetime as _dt
    try:
        dt = _dt.fromisoformat(schedule_iso.replace("Z", ""))
    except ValueError:
        return {"ok": False, "reason": f"schedule_iso không hợp lệ: {schedule_iso}"}
    time_str = dt.strftime("%H:%M")
    # dạng Studio EN: '3 Jul 2026'
    date_variants = [dt.strftime("%d %b %Y").lstrip("0"), dt.strftime("%b %d, %Y"),
                     dt.strftime("%d/%m/%Y")]
    out = {}
    # 0) expand Schedule section (bắt buộc — bug học live 02/07)
    try:
        exp = page.locator("#second-container-expand-button").first
        exp.wait_for(state="visible", timeout=8000)
        exp.click()
        page.wait_for_timeout(2000)
        out["expand"] = "EXPANDED"
    except Exception as e:
        out["expand"] = f"FAIL:{str(e)[:60]}"
    # 1) date — mặc định Studio pre-fill ngày mai; chỉ sửa nếu khác target
    try:
        trig = page.locator("#datepicker-trigger").first
        trig.wait_for(state="visible", timeout=8000)
        current = (trig.text_content() or "").strip()
        want = date_variants[0]
        if want.lower() not in current.lower():
            trig.click()
            page.wait_for_timeout(1500)
            di = page.locator("tp-yt-paper-dialog input, ytcp-date-picker input").first
            di.wait_for(state="visible", timeout=6000)
            di.click()
            page.keyboard.press("Control+A")
            filled = False
            for fmt in date_variants:
                try:
                    di.fill(fmt)
                    page.keyboard.press("Enter")
                    out["date"] = f"FILLED:{fmt}"
                    filled = True
                    break
                except Exception:
                    continue
            if not filled:
                out["date"] = "FILL_FAILED"
            page.wait_for_timeout(1000)
        else:
            out["date"] = f"ALREADY:{current}"
    except Exception as e:
        out["date"] = f"FAIL:{str(e)[:80]}"
    # 2) time — input hiển thị value HH:MM (verified: không có id riêng)
    try:
        picked = page.evaluate("""((t)=>{
          const inp=[...document.querySelectorAll('input')]
            .find(i=>i.offsetParent!==null&&/^\\d\\d:\\d\\d$/.test(i.value||''));
          if(!inp) return 'NO_TIME_INPUT';
          inp.focus(); inp.click();
          return 'FOCUSED';
        })(0)""")
        page.wait_for_timeout(1500)
        picked = page.evaluate("""((t)=>{
          const items=[...document.querySelectorAll('tp-yt-paper-item')].filter(e=>e.offsetParent!==null);
          const hit=items.find(i=>(i.textContent||'').trim()===t);
          if(hit){hit.click(); return 'PICKED:'+t;}
          const inp=[...document.querySelectorAll('input')]
            .find(i=>i.offsetParent!==null&&/^\\d\\d:\\d\\d$/.test(i.value||''));
          if(!inp) return 'NO_INPUT';
          inp.value=t;
          inp.dispatchEvent(new InputEvent('input',{bubbles:true}));
          inp.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true}));
          inp.blur();
          return 'TYPED:'+t;
        })(%s)""" % json.dumps(time_str))
        out["time"] = picked
    except Exception as e:
        out["time"] = f"FAIL:{str(e)[:80]}"
    return out


def _first(page, sels, timeout=8000, state="visible"):
    """Trả locator đầu tiên match trong danh sách fallback.
    state="attached" cho element ẩn (vd input[type=file] của YouTube)."""
    from playwright.sync_api import TimeoutError as PWTimeout
    for s in sels:
        try:
            loc = page.locator(s).first
            loc.wait_for(state=state, timeout=timeout)
            return loc
        except Exception:
            continue
    return None


def _resolve_account(account_id):
    """Trả (acc_dict|None). Nếu account_id cho trước -> lấy từ registry;
    nếu None -> không dùng multi-acc (legacy, authuser mặc định)."""
    if not account_id:
        return None
    from . import accounts
    return accounts.get_account(account_id)


def upload(video_path, title, description="", tags=None, made_for_kids=None,
           visibility="private", schedule_iso=None, is_short=False,
           playlist=None, thumbnail=None, dry_run=False, account_id=None):
    """Upload 1 video. Trả dict kết quả. Wire HumanMode toàn bộ.

    made_for_kids: None -> smart quyết định; True/False -> ép.
    visibility: private|unlisted|public|scheduled.
    account_id: None -> account mặc định (legacy). Khác -> switch authuser + rate riêng + proxy riêng.
    """
    acc = _resolve_account(account_id)
    # ---- GATE: rate limit TRƯỚC (theo account nếu có) ----
    ok, reason, info = limits.check_can_upload(account_id=account_id)
    if not ok:
        return {"ok": False, "stage": "rate_limit", "reason": reason,
                "info": info, "account_id": account_id}

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
    if acc:
        plan["account_id"] = acc["id"]
        plan["authuser"] = acc["authuser"]
        plan["proxy"] = (acc["proxy"]["server"] if acc.get("proxy") else None)
    if dry_run:
        return {"ok": True, "stage": "dry_run", "plan": plan,
                "rate": info, "note": "dry-run: KHÔNG upload thật"}

    # ---- Thực thi (qua CDP: dùng Chrome keeper đang sống, KHÔNG tắt tab YouTube) ----
    os.makedirs(LOGS, exist_ok=True)
    result = {"ok": False, "plan": plan, "stage": "init"}
    CDP_URL = os.environ.get("YT_CDP_URL", "http://127.0.0.1:18801")
    if acc and acc.get("proxy"):
        # Proxy phải set lúc launch browser; CDP browser hiện tại không đổi proxy runtime
        # → ghi chú để keeper launch với proxy cho acc này (xử lý ở tầng keeper).
        result["proxy_note"] = ("proxy được cấu hình cho acc; để áp dụng thật cần keeper "
                                "launch chrome với --proxy-server tương ứng (xem docs multi-proxy)")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            try:
                browser = pw.chromium.connect_over_cdp(CDP_URL, timeout=15000)
            except Exception as e:
                result.update({"stage": "cdp", "reason": f"CDP_CONNECT_FAIL: {e}",
                               "hint": "systemctl status yt-forever"})
                return result
            bctx = browser.contexts[0]
            page = bctx.new_page()   # tab mới cho upload; tab YouTube gốc giữ nguyên
            # Ép UI tiếng Anh (hl=en) để selector nhất quán + switch authuser nếu multi-acc
            start_url = getattr(studio, "STUDIO_URL_EN", studio.STUDIO_URL + "/?hl=en")
            if acc:
                sep = "&" if "?" in start_url else "?"
                start_url = f"{start_url}{sep}authuser={acc['authuser']}"
            page.goto(start_url, wait_until="domcontentloaded", timeout=60000)
            hm.human_pause("load")
            page.wait_for_timeout(3000)  # cho Studio SPA render nav Create
            ctx = page   # alias: ctx.close() bên dưới đóng TAB, không đóng cả browser

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
            fi = _first(page, studio.SELECTORS["file_input"], timeout=12000, state="attached")
            if not fi:
                result.update({"stage": "file_input", "reason": "không thấy input file",
                               "shot": _shot(page, "no-file-input")})
                ctx.close(); return result
            fi.set_input_files(video_path)
            hm.human_pause("load"); page.wait_for_timeout(6000)

            # 2b) Thumbnail (long video; Shorts chỉ đổi được qua mobile app)
            if thumbnail and os.path.exists(thumbnail) and not is_short:
                try:
                    ti = page.locator(
                        "#file-loader input[type='file'], ytcp-thumbnail-uploader input[type='file']").first
                    ti.wait_for(state="attached", timeout=15000)
                    ti.set_input_files(thumbnail)
                    hm.human_pause("between")
                except Exception:
                    _shot(page, "thumbnail-skip")

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

            # Audience (made for kids) — BẮT BUỘC chọn + VERIFY checked
            # (bug học 02/07: click không ăn -> video rơi vào draft vì thiếu câu trả lời)
            key = "kids_yes" if mfk else "kids_no"
            radio_name = "VIDEO_MADE_FOR_KIDS_MFK" if mfk else "VIDEO_MADE_FOR_KIDS_NOT_MFK"
            kb = _first(page, studio.SELECTORS[key], timeout=10000)
            if kb:
                hm.human_click(page, kb, "audience")
                hm.human_pause("between")
            # verify + retry bằng JS click nếu chưa checked
            for _ in range(3):
                checked = page.evaluate(
                    "(n)=>{const b=document.querySelector(`tp-yt-paper-radio-button[name='${n}']`);"
                    "return b?(b.hasAttribute('checked')||b.getAttribute('aria-checked')==='true'):null;}",
                    radio_name)
                if checked:
                    break
                page.evaluate(
                    "(n)=>{const b=document.querySelector(`tp-yt-paper-radio-button[name='${n}']`);"
                    "if(b)b.click();}", radio_name)
                page.wait_for_timeout(1500)
            else:
                result.update({"stage": "audience", "reason": "không set được made-for-kids radio",
                               "shot": _shot(page, "audience-fail")})
                ctx.close(); return result

            _shot(page, "details-filled")

            # 4-5) Next x3 (Details -> Elements -> Checks -> Visibility)
            for i in range(3):
                nb = _first(page, studio.SELECTORS["next_button"], timeout=12000)
                if nb:
                    hm.human_click(page, nb, f"next-{i}")
                    hm.human_pause("between")

            # 6) Visibility
            if vis == "scheduled" and schedule_iso:
                # verified live 02/07: KHÔNG có radio SCHEDULE — Schedule là section
                # collapse; _fill_schedule tự expand + điền date/time
                sched_res = _fill_schedule(page, schedule_iso)
                result["schedule_fill"] = sched_res
                if isinstance(sched_res, dict) and str(sched_res.get("time", "")).startswith(("PICKED", "TYPED")) is False:
                    _shot(page, "schedule-warn")
            else:
                vkey = {"public": "vis_public", "unlisted": "vis_unlisted"}.get(vis, "vis_private")
                vname = {"public": "PUBLIC", "unlisted": "UNLISTED"}.get(vis, "PRIVATE")
                vb = _first(page, studio.SELECTORS[vkey], timeout=8000)
                if vb:
                    hm.human_click(page, vb, f"vis-{vis}")
                # verify + retry (cùng bài học audience radio)
                for _ in range(3):
                    vchecked = page.evaluate(
                        "(n)=>{const b=document.querySelector(`tp-yt-paper-radio-button[name='${n}']`);"
                        "return b?(b.hasAttribute('checked')||b.getAttribute('aria-checked')==='true'):null;}",
                        vname)
                    if vchecked:
                        break
                    page.evaluate(
                        "(n)=>{const b=document.querySelector(`tp-yt-paper-radio-button[name='${n}']`);"
                        "if(b)b.click();}", vname)
                    page.wait_for_timeout(1500)
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

            limits.record_upload(video_id=vid, title=final_title, account_id=account_id)
            result.update({"ok": True, "stage": "published", "video_id": vid,
                           "account_id": account_id,
                           "rate_after": limits.status(account_id=account_id)})
            return result
    except Exception as e:
        result.update({"stage": "exception", "reason": str(e)[:300]})
        return result
