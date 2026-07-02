"""
Manager — quản lý video đã upload qua Studio UI (FIFO controller, né quota API).

Chức năng:
  list_videos()   — danh sách video: id, title, visibility, date, views, comments, likes%
  get_video()     — chi tiết 1 video (edit page): title, desc, kids, visibility
  edit_video()    — sửa title / description / visibility (verify sau khi save)
  delete_video()  — XÓA video (destructive — bắt buộc confirm=True từ CLI --confirm)

Mọi thao tác đọc/ghi qua session FIFO (browser yt-forever giữ login sẵn).
"""
import json
import time

from . import studio

CONTENT_PATH = "/videos/upload"


def _channel_id(session):
    r = session.evaluate("(window.ytcfg&&ytcfg.get&&ytcfg.get('CHANNEL_ID'))||''")
    return r.get("value") or ""


def _goto_content(session):
    cid = _channel_id(session)
    if not cid:
        # chưa ở trang studio -> vào studio trước rồi lấy lại
        session.goto(studio.STUDIO_URL, wait_ms=8000, name="mgr-home")
        cid = _channel_id(session)
    r = session.goto(f"{studio.STUDIO_URL}/channel/{cid}{CONTENT_PATH}",
                     wait_ms=8000, name="mgr-content")
    if "studio.youtube.com" not in r.get("url", ""):
        raise RuntimeError(f"Studio không mở được: {r.get('url','')[:100]}")
    return cid


def _click_tab(session, tab_name):
    """Chuyển tab trên Content page (Videos / Shorts / Live...). Trả True nếu click được."""
    r = session.evaluate("""((name)=>{
      const t=[...document.querySelectorAll('tp-yt-paper-tab, [role=tab]')]
        .find(x=>(x.textContent||'').trim().toLowerCase()===name.toLowerCase());
      if(!t) return 'NO_TAB';
      t.click(); return 'OK';
    })(%s)""" % json.dumps(tab_name))
    ok = r.get("value") == "OK"
    if ok:
        time.sleep(3.5)
    return ok


def _read_rows(session, limit, save):
    js = """(()=>{
      const rows=[...document.querySelectorAll('ytcp-video-row')];
      return rows.slice(0, %d).map(r=>{
        const a=r.querySelector('a#video-title, #video-title');
        const href=(a&&a.href)||'';
        const m=href.match(/video\\/([^\\/]+)\\//);
        const cells=[...r.querySelectorAll('.tablecell-visibility, .tablecell-date, .tablecell-views, .tablecell-comments, .tablecell-likes')].map(c=>(c.textContent||'').trim().replace(/\\s+/g,' '));
        const vis=r.querySelector('.tablecell-visibility, ytcp-video-visibility-cell');
        const date=r.querySelector('.tablecell-date');
        const views=r.querySelector('.tablecell-views');
        const comments=r.querySelector('.tablecell-comments');
        const likes=r.querySelector('.tablecell-likes');
        const badges=[...r.querySelectorAll('.video-badge, ytcp-video-restrictions-cell')].map(b=>(b.textContent||'').trim()).filter(Boolean);
        return {
          video_id: m?m[1]:null,
          title:(a&&a.textContent||'').trim(),
          url: m?('https://youtu.be/'+m[1]):null,
          visibility:(vis&&vis.textContent||'').trim().replace(/\\s+/g,' '),
          date:(date&&date.textContent||'').trim().replace(/\\s+/g,' '),
          views:(views&&views.textContent||'').trim(),
          comments:(comments&&comments.textContent||'').trim(),
          likes:(likes&&likes.textContent||'').trim().replace(/\\s+/g,' '),
          restrictions: badges.join('; ').slice(0,80),
          _cells: cells.slice(0,6)
        };
      });
    })()""" % limit
    r = session.evaluate(js, save=save)
    return r.get("value") or []


def list_videos(session, limit=20, tabs=("Videos", "Shorts")):
    """Đọc bảng Content ở các tab (Videos + Shorts mặc định); mỗi row = 1 video."""
    cid = _goto_content(session)
    time.sleep(2)
    all_vids = []
    seen = set()
    for tab in tabs:
        if not _click_tab(session, tab):
            continue
        for v in _read_rows(session, limit, save=f"mgr-list-{tab.lower()}"):
            vid = v.get("video_id")
            if vid and vid in seen:
                continue
            if vid:
                seen.add(vid)
            v["tab"] = tab
            all_vids.append(v)
    return {"ok": True, "channel_id": cid, "count": len(all_vids),
            "videos": all_vids[:limit]}


def get_video(session, video_id):
    """Đọc chi tiết video từ edit page."""
    r = session.goto(f"{studio.STUDIO_URL}/video/{video_id}/edit",
                     wait_ms=9000, name=f"mgr-get-{video_id}")
    if f"/video/{video_id}" not in r.get("url", ""):
        return {"ok": False, "reason": "không mở được edit page", "url": r.get("url", "")[:100]}
    time.sleep(2)
    js = """(()=>{
      const t=document.querySelector('#title-textarea #textbox, ytcp-social-suggestions-textbox#title-textarea #textbox');
      const d=document.querySelector('#description-textarea #textbox, #description-wrapper #textbox');
      const kids=[...document.querySelectorAll('tp-yt-paper-radio-button')]
        .filter(b=>(b.getAttribute('name')||'').includes('MFK'))
        .map(b=>({name:b.getAttribute('name'),checked:b.hasAttribute('checked')||b.getAttribute('aria-checked')==='true'}));
      const visEl=[...document.querySelectorAll('*')].find(e=>e.children.length===0&&/^(Public|Private|Unlisted|Scheduled)$/.test((e.textContent||'').trim()));
      const draft=!!document.querySelector('ytcp-banner')&&/draft/i.test(document.body.textContent.slice(0,3000));
      return {
        title:(t&&t.textContent||'').trim(),
        description:(d&&d.textContent||'').trim().slice(0,500),
        kids,
        visibility: visEl?(visEl.textContent||'').trim():null,
        is_draft: draft
      };
    })()"""
    v = session.evaluate(js, save=f"mgr-get-{video_id}")
    out = v.get("value") or {}
    out.update({"ok": True, "video_id": video_id,
                "url": f"https://youtu.be/{video_id}"})
    return out


def _set_textbox(session, selector_list, new_text):
    """Set nội dung 1 contenteditable textbox qua JS + fire input event."""
    js = """((sels, txt)=>{
      for(const s of sels){
        const e=document.querySelector(s);
        if(e){
          e.focus();
          e.textContent=txt;
          e.dispatchEvent(new InputEvent('input',{bubbles:true}));
          e.blur();
          return 'SET:'+s;
        }
      }
      return 'NOT_FOUND';
    })(%s, %s)""" % (json.dumps(selector_list), json.dumps(new_text))
    return session.evaluate(js).get("value")


def edit_video(session, video_id, title=None, description=None, visibility=None):
    """Sửa metadata video đã up. Trả dict changes + verify."""
    r = session.goto(f"{studio.STUDIO_URL}/video/{video_id}/edit",
                     wait_ms=9000, name=f"mgr-edit-{video_id}")
    if f"/video/{video_id}" not in r.get("url", ""):
        return {"ok": False, "reason": "không mở được edit page", "url": r.get("url", "")[:100]}
    time.sleep(2)
    changes = {}

    if title is not None:
        res = _set_textbox(session, [
            "#title-textarea #textbox",
            "ytcp-social-suggestions-textbox#title-textarea #textbox"], title)
        changes["title"] = res
        time.sleep(1)

    if description is not None:
        res = _set_textbox(session, [
            "#description-textarea #textbox",
            "#description-wrapper #textbox"], description)
        changes["description"] = res
        time.sleep(1)

    if visibility is not None:
        vname = {"public": "PUBLIC", "unlisted": "UNLISTED",
                 "private": "PRIVATE"}.get(visibility.lower())
        if not vname:
            return {"ok": False, "reason": f"visibility không hợp lệ: {visibility}"}
        # mở visibility widget (sidebar edit page) rồi chọn radio
        js = """(()=>{
          // 1) tìm trigger chứa text Public/Private/Unlisted trong sidebar
          const trig=[...document.querySelectorAll('ytcp-video-metadata-visibility, ytcp-text-dropdown-trigger, ytcp-dropdown-trigger')]
            .find(e=>/(Public|Private|Unlisted|Scheduled)/.test(e.textContent||''));
          if(trig){trig.click(); return 'VIS_OPENED';}
          return 'NO_VIS_TRIGGER';
        })()"""
        opened = session.evaluate(js).get("value")
        time.sleep(2)
        picked = session.evaluate("""((n)=>{
          const b=document.querySelector(`tp-yt-paper-radio-button[name='${n}']`);
          if(!b) return 'NO_RADIO';
          b.click(); return 'PICKED';
        })(%s)""" % json.dumps(vname)).get("value")
        time.sleep(1)
        # dialog visibility có nút save/done riêng
        dsave = session.evaluate("""(()=>{
          const d=document.querySelector('#save-button, ytcp-button#save-button, #done-button');
          if(d&&!d.hasAttribute('disabled')){d.click(); return 'DIALOG_SAVED';}
          return 'NO_DIALOG_SAVE';
        })()""").get("value")
        changes["visibility"] = {"opened": opened, "picked": picked, "dialog_save": dsave}
        time.sleep(2)

    # save trang chính
    saved = session.evaluate("""(()=>{
      const s=document.querySelector('#save, ytcp-button#save');
      if(!s) return 'NO_SAVE_BTN';
      if(s.hasAttribute('disabled')) return 'SAVE_DISABLED(no changes?)';
      s.click(); return 'SAVED';
    })()""").get("value")
    time.sleep(3)
    verify = get_video(session, video_id)
    return {"ok": True, "video_id": video_id, "changes": changes,
            "save": saved, "after": verify}


def delete_video(session, video_id, confirm=False):
    """XÓA video vĩnh viễn. destructive — chỉ chạy khi confirm=True.

    Flow VERIFIED LIVE 02/07/2026 (xóa thật sDTHTxLdLPM):
    edit page → #overflow-menu-button (Options) → item 'Delete' →
    dialog: tick checkbox → nút 'Delete forever' → redirect về content page.
    (Row hover-menu trên content page KHÔNG render nút qua JS — đã thử, fail.)
    """
    if not confirm:
        return {"ok": False, "reason": "DESTRUCTIVE: cần --confirm để xóa video",
                "video_id": video_id}
    r = session.goto(f"{studio.STUDIO_URL}/video/{video_id}/edit",
                     wait_ms=10000, name=f"del-{video_id}")
    if f"/video/{video_id}" not in r.get("url", ""):
        return {"ok": False, "video_id": video_id,
                "reason": "không mở được edit page (video không tồn tại?)",
                "url": r.get("url", "")[:100]}
    time.sleep(3)
    step1 = session.evaluate("""(()=>{
      const b=document.querySelector('#overflow-menu-button');
      if(!b) return 'NO_OVERFLOW';
      b.click(); return 'MENU_OPENED';
    })()""").get("value")
    time.sleep(2)
    step2 = session.evaluate("""(()=>{
      const items=[...document.querySelectorAll('tp-yt-paper-item')].filter(e=>e.offsetParent!==null);
      const del=items.find(i=>/^\\s*Delete\\s*$/i.test((i.textContent||'').trim()));
      if(!del) return 'NO_DELETE_ITEM:'+items.map(i=>(i.textContent||'').trim().slice(0,20)).join('|').slice(0,100);
      del.click(); return 'DELETE_CLICKED';
    })()""").get("value")
    time.sleep(3)
    step3 = session.evaluate("""(()=>{
      const cb=[...document.querySelectorAll('ytcp-checkbox-lit, tp-yt-paper-checkbox, input[type=checkbox]')].filter(e=>e.offsetParent!==null);
      if(cb.length){cb[0].click(); return 'CHECKBOX_TICKED';}
      return 'NO_CHECKBOX';
    })()""").get("value")
    time.sleep(1.5)
    step4 = session.evaluate("""(()=>{
      const btns=[...document.querySelectorAll('ytcp-button, button')].filter(b=>b.offsetParent!==null);
      const d=btns.find(b=>/delete forever/i.test((b.textContent||'').trim())&&!b.hasAttribute('disabled'));
      if(!d) return 'NO_CONFIRM_BTN';
      d.click(); return 'DELETED';
    })()""").get("value")
    time.sleep(6)
    # verify: redirect khỏi edit page = xóa thành công
    href = session.evaluate("location.href").get("value") or ""
    gone = f"/video/{video_id}" not in href
    return {"ok": step4 == "DELETED" and gone, "video_id": video_id,
            "verified_gone": gone,
            "steps": {"menu": step1, "item": step2, "checkbox": step3, "confirm": step4}}
