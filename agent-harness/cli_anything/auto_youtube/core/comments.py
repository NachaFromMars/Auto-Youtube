"""
Comments — đọc + reply comment qua Studio UI (FIFO controller, né quota).

  list_comments()  — inbox comment mới nhất (author, text, video)
  reply_comment()  — reply comment theo index trong danh sách vừa đọc
"""
import json
import time

from . import studio


def _cid(session):
    r = session.evaluate("(window.ytcfg&&ytcfg.get&&ytcfg.get('CHANNEL_ID'))||''")
    v = r.get("value") or ""
    if not v:
        session.goto(studio.STUDIO_URL, wait_ms=8000, name="cm-home")
        v = session.evaluate("(window.ytcfg&&ytcfg.get&&ytcfg.get('CHANNEL_ID'))||''").get("value") or ""
    return v


def _goto_inbox(session):
    cid = _cid(session)
    r = session.goto(f"{studio.STUDIO_URL}/channel/{cid}/comments/inbox",
                     wait_ms=9000, name="cm-inbox")
    if "comments" not in r.get("url", ""):
        raise RuntimeError(f"không mở được comments: {r.get('url','')[:100]}")
    time.sleep(3)
    return cid


def list_comments(session, limit=15):
    cid = _goto_inbox(session)
    js = """(()=>{
      const items=[...document.querySelectorAll('ytcp-comment-thread, ytcp-comment')];
      return items.slice(0, %d).map((c,i)=>{
        const author=(c.querySelector('#author-text, .author-text, a#name')||{}).textContent||'';
        const text=(c.querySelector('#content-text, yt-formatted-string#content-text')||{}).textContent||'';
        const video=(c.querySelector('.video-title, #video-title, a[href*=video]')||{}).textContent||'';
        const when=(c.querySelector('.published-time-text, #published-time-text')||{}).textContent||'';
        return {index:i, author:author.trim().slice(0,40), text:text.trim().slice(0,200),
                video:video.trim().slice(0,60), when:when.trim().slice(0,30)};
      });
    })()""" % limit
    v = session.evaluate(js, save="cm-list")
    comments = v.get("value") or []
    return {"ok": True, "channel_id": cid, "count": len(comments), "comments": comments}


def reply_comment(session, index, text):
    """Reply comment thứ `index` trong inbox hiện tại."""
    _goto_inbox(session)
    # 1) click nút Reply của comment
    step1 = session.evaluate("""((i)=>{
      const items=[...document.querySelectorAll('ytcp-comment-thread, ytcp-comment')];
      const c=items[i];
      if(!c) return 'NO_COMMENT_AT_INDEX';
      const btn=[...c.querySelectorAll('ytcp-button, button, #reply-button')].find(b=>/reply|tr\u1ea3 l\u1eddi/i.test(b.textContent||''));
      if(!btn) return 'NO_REPLY_BTN';
      btn.click(); return 'REPLY_OPENED';
    })(%d)""" % index).get("value")
    if step1 != "REPLY_OPENED":
        return {"ok": False, "stage": "open", "reason": step1}
    time.sleep(2)
    # 2) gõ nội dung vào textarea đang mở
    step2 = session.evaluate("""((txt)=>{
      const boxes=[...document.querySelectorAll('#textarea, textarea, #contenteditable-root')].filter(e=>e.offsetParent!==null);
      const b=boxes[boxes.length-1];
      if(!b) return 'NO_TEXTBOX';
      b.focus();
      if(b.tagName==='TEXTAREA'){b.value=txt;}else{b.textContent=txt;}
      b.dispatchEvent(new InputEvent('input',{bubbles:true}));
      return 'TYPED';
    })(%s)""" % json.dumps(text)).get("value")
    if step2 != "TYPED":
        return {"ok": False, "stage": "type", "reason": step2}
    time.sleep(1.5)
    # 3) submit
    step3 = session.evaluate("""(()=>{
      const btns=[...document.querySelectorAll('ytcp-button, button')].filter(b=>b.offsetParent!==null);
      const s=btns.find(b=>/^(reply|comment|tr\u1ea3 l\u1eddi)$/i.test((b.textContent||'').trim())&&!b.hasAttribute('disabled'));
      if(!s) return 'NO_SUBMIT';
      s.click(); return 'SUBMITTED';
    })()""").get("value")
    time.sleep(2)
    return {"ok": step3 == "SUBMITTED",
            "steps": {"open": step1, "type": step2, "submit": step3}}
