"""
Analytics — crawl số liệu kênh từ Studio (dashboard + analytics), né quota API.

  channel_overview()  — subscriber, views 28 ngày, watch time, top videos
  video_stats()       — số liệu 1 video (từ analytics video page)
  report()            — báo cáo tổng hợp kênh: overview + danh sách video mới nhất
"""
import time

from . import studio


def _cid(session):
    r = session.evaluate("(window.ytcfg&&ytcfg.get&&ytcfg.get('CHANNEL_ID'))||''")
    v = r.get("value") or ""
    if not v:
        session.goto(studio.STUDIO_URL, wait_ms=8000, name="an-home")
        v = session.evaluate("(window.ytcfg&&ytcfg.get&&ytcfg.get('CHANNEL_ID'))||''").get("value") or ""
    return v


def channel_overview(session):
    """Crawl analytics overview: metric cards + tổng quan."""
    cid = _cid(session)
    r = session.goto(f"{studio.STUDIO_URL}/channel/{cid}/analytics/tab-overview/period-default",
                     wait_ms=12000, name="an-overview")
    if "analytics" not in r.get("url", ""):
        return {"ok": False, "reason": "không mở được analytics", "url": r.get("url", "")[:100]}
    time.sleep(7)  # SPA render chậm — verified 02/07: cần >5s mới có yta-key-metric-block
    js = """(()=>{
      const out={metrics:{}, realtime:{}};
      // key-metric blocks: leaf node đầu = label, leaf node cuối = value hiển thị
      document.querySelectorAll('yta-key-metric-block').forEach(b=>{
        const leaves=[...b.querySelectorAll('*')].filter(e=>e.children.length===0&&(e.textContent||'').trim());
        if(!leaves.length) return;
        const label=(leaves[0].textContent||'').trim().slice(0,40);
        // value: leaf số hoặc '—', bỏ tooltip/link text ('Learn more'...)
        const vals=leaves.map(e=>(e.textContent||'').trim())
          .filter(t=>/^[\\d,.KMB%\u2014\u2013-]+$/.test(t)&&t.length<=15);
        const value=vals.length?vals[vals.length-1]:'—';
        if(label && !(label in out.metrics)) out.metrics[label]=value;
      });
      // realtime card: subscribers + views 48h
      const act=document.querySelector('yta-latest-activity-card');
      if(act){
        const t=(act.textContent||'').replace(/\\s+/g,' ');
        const sub=t.match(/(\\d[\\d,.]*)\\s*Subscribers/);
        const vw=t.match(/(\\d[\\d,.]*)\\s*Views · Last 48/);
        if(sub) out.realtime.subscribers=sub[1];
        if(vw) out.realtime.views_48h=vw[1];
      }
      const sum=[...document.querySelectorAll('#summary, .summary, yta-channel-facts')].map(e=>(e.textContent||'').trim().replace(/\\s+/g,' ').slice(0,200));
      out.summary=sum.filter(Boolean).slice(0,3);
      return out;
    })()"""
    v = session.evaluate(js, save="an-overview")
    out = v.get("value") or {}
    out.update({"ok": True, "channel_id": cid})
    return out


def dashboard_snapshot(session):
    """Crawl dashboard: latest video performance + news."""
    cid = _cid(session)
    session.goto(f"{studio.STUDIO_URL}/channel/{cid}", wait_ms=9000, name="an-dashboard")
    time.sleep(3)
    js = """(()=>{
      const out={};
      const latest=document.querySelector('ytcd-video-snapshot-card, ytcd-card[test-id*=latest]');
      if(latest) out.latest_video=(latest.textContent||'').trim().replace(/\\s+/g,' ').slice(0,300);
      const summary=document.querySelector('ytcd-channel-facts-card, ytcd-card[test-id*=channel]');
      if(summary) out.channel_summary=(summary.textContent||'').trim().replace(/\\s+/g,' ').slice(0,300);
      return out;
    })()"""
    v = session.evaluate(js, save="an-dashboard")
    out = v.get("value") or {}
    out["ok"] = True
    return out


def video_stats(session, video_id):
    """Số liệu 1 video từ analytics video page."""
    r = session.goto(f"{studio.STUDIO_URL}/video/{video_id}/analytics/tab-overview/period-default",
                     wait_ms=12000, name=f"an-video-{video_id}")
    if "analytics" not in r.get("url", ""):
        return {"ok": False, "reason": "không mở được video analytics",
                "url": r.get("url", "")[:100]}
    time.sleep(7)  # SPA render chậm (cùng bài học channel overview)
    js = """(()=>{
      const out={metrics:{}, realtime:{}};
      document.querySelectorAll('yta-key-metric-block').forEach(b=>{
        const leaves=[...b.querySelectorAll('*')].filter(e=>e.children.length===0&&(e.textContent||'').trim());
        if(!leaves.length) return;
        const label=(leaves[0].textContent||'').trim().slice(0,40);
        const vals=leaves.map(e=>(e.textContent||'').trim())
          .filter(t=>/^[\\d,.KMB%\u2014\u2013-]+$/.test(t)&&t.length<=15);
        const value=vals.length?vals[vals.length-1]:'—';
        if(label && !(label in out.metrics)) out.metrics[label]=value;
      });
      const act=document.querySelector('yta-latest-activity-card');
      if(act){
        const t=(act.textContent||'').replace(/\\s+/g,' ');
        const vw=t.match(/(\\d[\\d,.]*)\\s*Views · Last 48/);
        if(vw) out.realtime.views_48h=vw[1];
      }
      const sum=[...document.querySelectorAll('#summary, yta-video-facts')].map(e=>(e.textContent||'').trim().replace(/\\s+/g,' ').slice(0,200));
      out.summary=sum.filter(Boolean).slice(0,3);
      return out;
    })()"""
    v = session.evaluate(js, save=f"an-video-{video_id}")
    out = v.get("value") or {}
    out.update({"ok": True, "video_id": video_id})
    return out


def report(session, manager_mod, limit=10):
    """Báo cáo tổng hợp: overview + dashboard + video list."""
    rep = {"ok": True, "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    try:
        rep["overview"] = channel_overview(session)
    except Exception as e:
        rep["overview"] = {"ok": False, "error": str(e)[:150]}
    try:
        rep["dashboard"] = dashboard_snapshot(session)
    except Exception as e:
        rep["dashboard"] = {"ok": False, "error": str(e)[:150]}
    try:
        rep["videos"] = manager_mod.list_videos(session, limit=limit)
    except Exception as e:
        rep["videos"] = {"ok": False, "error": str(e)[:150]}
    return rep
