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


def _goto_inbox(session, include_responded=True):
    """Mở inbox. Mặc định Studio gắn chip 'Response status: Unresponded' —
    verified live 02/07: chip này ẩn cả comment chủ kênh → gỡ chip để thấy hết."""
    cid = _cid(session)
    r = session.goto(f"{studio.STUDIO_URL}/channel/{cid}/comments/inbox",
                     wait_ms=9000, name="cm-inbox")
    if "comments" not in r.get("url", ""):
        raise RuntimeError(f"không mở được comments: {r.get('url','')[:100]}")
    time.sleep(5)
    if include_responded:
        session.evaluate("""(()=>{
          const chips=[...document.querySelectorAll('ytcp-chip, ytcp-filter-chip, [class*=chip]')]
            .filter(e=>e.offsetParent!==null&&/unresponded/i.test(e.textContent||''));
          if(!chips.length) return 'NO_CHIP';
          const x=chips[0].querySelector('ytcp-icon-button, button, tp-yt-iron-icon[icon*=close]');
          if(x){x.click(); return 'CHIP_REMOVED';}
          chips[0].click(); return 'CHIP_CLICKED';
        })()""")
        time.sleep(4)
    return cid


def list_comments(session, limit=15, unresponded_only=False):
    cid = _goto_inbox(session, include_responded=not unresponded_only)
    js = """(()=>{
      const items=[...document.querySelectorAll('ytcp-comment-thread')];
      return items.slice(0, %d).map((c,i)=>{
        const author=(c.querySelector('#author-text, .author-text, a#name')||{}).textContent||'';
        const text=(c.querySelector('#content-text, yt-formatted-string#content-text')||{}).textContent||'';
        const video=(c.querySelector('.video-title, #video-title, a[href*=video]')||{}).textContent||'';
        const when=(c.querySelector('.published-time-text, #published-time-text')||{}).textContent||'';
        const nReplies=(c.querySelector('#replies-count, [class*=replies]')||{}).textContent||'';
        return {index:i, author:author.trim().slice(0,40), text:text.trim().slice(0,200),
                video:video.trim().slice(0,60), when:when.trim().slice(0,30),
                replies:(nReplies||'').trim().slice(0,20)};
      });
    })()""" % limit
    v = session.evaluate(js, save="cm-list")
    comments = v.get("value") or []
    return {"ok": True, "channel_id": cid, "count": len(comments), "comments": comments}


def reply_comment(session, index, text, _skip_nav=False):
    """Reply comment thứ `index` trong inbox hiện tại."""
    if not _skip_nav:
        _goto_inbox(session)
    # 1) click nút Reply của comment
    step1 = session.evaluate("""((i)=>{
      const items=[...document.querySelectorAll('ytcp-comment-thread')];
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
    # 3) submit — verified live 02/07: nút submit là 'Reply' ĐỨNG SAU nút 'Cancel'
    # trong reply box đang mở (nút 'Reply' đầu thread chỉ MỞ box, không submit)
    step3 = session.evaluate("""(()=>{
      const btns=[...document.querySelectorAll('ytcp-button, button')].filter(b=>b.offsetParent!==null);
      const cancelIdx=btns.findIndex(b=>/^cancel$/i.test((b.textContent||'').trim()));
      let submit=null;
      if(cancelIdx>=0){ submit=btns.slice(cancelIdx+1).find(b=>/^(reply|tr\u1ea3 l\u1eddi)$/i.test((b.textContent||'').trim())); }
      if(!submit){ submit=[...btns].reverse().find(b=>/^(reply|tr\u1ea3 l\u1eddi)$/i.test((b.textContent||'').trim())&&!b.hasAttribute('disabled')); }
      if(!submit) return 'NO_SUBMIT';
      if(submit.hasAttribute('disabled')) return 'SUBMIT_DISABLED';
      submit.click(); return 'SUBMITTED';
    })()""").get("value")
    time.sleep(3)
    # verify: reply mới xuất hiện trong thread
    verified = session.evaluate("""((frag)=>{
      const t=[...document.querySelectorAll('ytcp-comment-thread')];
      return t.some(x=>(x.textContent||'').includes(frag));
    })(%s)""" % json.dumps(text[:40])).get("value")
    return {"ok": step3 == "SUBMITTED" and bool(verified), "verified": bool(verified),
            "steps": {"open": step1, "type": step2, "submit": step3}}
