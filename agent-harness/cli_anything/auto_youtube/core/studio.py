"""
Studio flow — upload + quản lý video qua YouTube Studio UI (browser automation).
MỌI thao tác bọc HumanMode. KHÔNG gọi Data API (né quota).

Vì controller chạy ở process riêng (FIFO), studio flow ở đây dùng 2 chế độ:
  A) Qua session.send (FIFO controller) — cho các bước điều hướng đơn giản.
  B) Inline Playwright (khi cần upload file + thao tác phức tạp HumanMode) —
     mở trên CÙNG profile yt-forever-profile nhưng phải dừng controller tạm
     để tránh tranh chấp profile lock (single-instance).

Flow upload chuẩn YouTube Studio 2026 (đã map, sẽ self-audit khi vào được):
  1. studio.youtube.com -> nút CREATE (#create-icon) -> "Upload videos"
  2. Dialog: chọn file (input[type=file]) -> chờ xử lý
  3. Details: Title (#textbox title), Description (#textbox desc),
     Thumbnail, Playlists, Audience (made for kids radio), Age-restriction (Show more)
  4. Video elements (cards/end screen) -> Next
  5. Checks (copyright) -> Next
  6. Visibility: Private/Unlisted/Public/Schedule (datepicker)
  7. Publish/Save/Schedule -> lấy video_id

SELECTOR MAP — tham khảo adasq/youtube-studio + DOM thật. Mỗi key có nhiều
fallback selector; resolver thử lần lượt. crawl_studio_flow() sẽ cập nhật map này.
"""

STUDIO_URL = "https://studio.youtube.com"
# Ép UI tiếng Anh để selector nhất quán giữa các account (tránh "Tạo" vs "Create").
STUDIO_URL_EN = "https://studio.youtube.com/?hl=en"

# Selector map (fallback list). Cập nhật sau khi crawl live.
SELECTORS = {
    "create_button": ["#create-icon", "ytcp-button#create-icon",
                      "[aria-label*='Create']", "[aria-label*='Tạo']",
                      "ytcp-button[aria-label*='Create']", "ytcp-button[aria-label*='Tạo']",
                      "#create-icon button"],
    "upload_menu": ["#text-item-0", "tp-yt-paper-item:has-text('Upload')",
                   "tp-yt-paper-item:has-text('Tải')", "[test-id='upload-beta']"],
    "file_input": ["input[type='file']"],
    "title_box": ["#title-textarea #textbox", "ytcp-social-suggestions-textbox#title-textarea #textbox",
                 "#title-wrapper #textbox"],
    "desc_box": ["#description-textarea #textbox", "#description-wrapper #textbox"],
    "kids_yes": ["tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_MFK']",
                "#audience #made-for-kids-group [name*='MFK']"],
    "kids_no": ["tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']",
               "#audience [name*='NOT_MFK']"],
    "show_more": ["#toggle-button", "ytcp-button#toggle-button:has-text('Show more')"],
    "next_button": ["#next-button", "ytcp-button#next-button"],
    "vis_private": ["tp-yt-paper-radio-button[name='PRIVATE']", "[name='PRIVATE']"],
    "vis_unlisted": ["tp-yt-paper-radio-button[name='UNLISTED']", "[name='UNLISTED']"],
    "vis_public": ["tp-yt-paper-radio-button[name='PUBLIC']", "[name='PUBLIC']"],
    "schedule_radio": ["#schedule-radio-button", "[name='SCHEDULE']"],
    "done_button": ["#done-button", "ytcp-button#done-button"],
    "video_url_link": ["a.ytcp-video-info", "#share-url", ".video-url-fadeable a"],
}

# Các màn Studio cần crawl để audit ĐỦ chức năng
STUDIO_SCREENS = {
    "content": "/channel/{cid}/videos/upload",        # danh sách video
    "dashboard": "/channel/{cid}",
    "analytics": "/channel/{cid}/analytics",
    "playlists": "/channel/{cid}/playlists",
    "comments": "/channel/{cid}/comments",
    "subtitles": "/channel/{cid}/translations",
    "copyright": "/channel/{cid}/copyright",
    "monetization": "/channel/{cid}/monetization",
    "customization": "/channel/{cid}/editing/channel",
    "audience": "/channel/{cid}/audience",
}


def build_resolver_js():
    """JS chạy trong page: nhận map -> trả selector nào tồn tại (audit live)."""
    return """
    (sel_map) => {
      const out = {};
      for (const [key, sels] of Object.entries(sel_map)) {
        let found = null, count = 0;
        for (const s of sels) {
          try {
            const els = document.querySelectorAll(s);
            if (els && els.length) { found = s; count = els.length; break; }
          } catch(e){}
        }
        out[key] = { found, count };
      }
      return out;
    }
    """


def crawl_studio_flow(session, audit_save="studio-flow-audit"):
    """Mở Studio, audit từng selector + dump DOM mỗi màn. CHỈ chạy khi đã qua login.
    Trả dict audit để xác nhận crawl ĐỦ. KHÔNG upload gì."""
    report = {"screens": {}, "selectors": {}, "logged_in_studio": False}

    # 1) vào Studio
    r = session.goto(STUDIO_URL, wait_ms=9000, name="audit-studio-home")
    url = r.get("url", "")
    # nếu redirect ra accounts.google -> chưa qua verification
    if "studio.youtube.com" not in url:
        report["blocked"] = True
        report["blocked_url"] = url[:120]
        report["reason"] = "Studio chưa mở được (verification/redirect). Cần qua selfie verify trước."
        return report
    report["logged_in_studio"] = True

    # 2) resolve selectors trên màn hiện tại
    import json as _json
    js = f"({build_resolver_js()})({_json.dumps(SELECTORS)})"
    sr = session.evaluate(js, save=audit_save + "-selectors")
    report["selectors"] = sr.get("value", {})

    # 3) crawl từng màn quản lý (audit đủ chức năng)
    cid_r = session.evaluate("(window.ytcfg&&ytcfg.get&&ytcfg.get('CHANNEL_ID'))||''")
    cid = cid_r.get("value") or ""
    report["channel_id"] = cid
    for name, path in STUDIO_SCREENS.items():
        try:
            target = STUDIO_URL + path.format(cid=cid)
            rr = session.goto(target, wait_ms=6000, name=f"audit-{name}")
            session.dump_dom(f"{audit_save}-{name}")
            report["screens"][name] = {"url": rr.get("url", "")[:120], "ok": True}
        except Exception as e:
            report["screens"][name] = {"ok": False, "error": str(e)[:120]}
    return report
