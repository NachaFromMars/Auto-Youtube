#!/usr/bin/env python3
"""Đổi RIÊNG handle. Usage: set_handle.py <CID> <authuser> <new_handle_no_@>"""
import sys, json
from playwright.sync_api import sync_playwright

CID = sys.argv[1]; AU = sys.argv[2]; H = sys.argv[3].lstrip("@")
SHOT = "/root/.openclaw/workspace/youtube-cli"
def log(**d): print(json.dumps(d, ensure_ascii=False), flush=True)

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp("http://127.0.0.1:18801", timeout=15000)
    ctx = b.contexts[0]; pg = ctx.new_page()
    url = f"https://studio.youtube.com/channel/{CID}/editing/profile?hl=en&authuser={AU}"
    pg.goto(url, wait_until="domcontentloaded", timeout=50000)
    pg.wait_for_timeout(9000)

    inp = pg.locator("input[type='text']").first
    inp.wait_for(state="visible", timeout=10000)
    before = inp.input_value()
    inp.click()
    pg.keyboard.press("Control+A"); pg.keyboard.press("Delete")
    pg.wait_for_timeout(500)
    pg.keyboard.type(H, delay=90)
    log(step="typed", before=before, new=H)
    pg.wait_for_timeout(5000)  # availability check

    # đọc thông báo availability nếu có
    avail = pg.evaluate("""()=>{
      const t=document.body.innerText;
      const m=t.match(/(handle is available|not available|already taken|Handles can|can'?t use|đã được|không khả dụng)/i);
      return m?m[0]:'(no msg)';
    }""")
    log(step="availability", msg=avail)
    try: pg.screenshot(path=f"{SHOT}/handle-{AU}-typed.png")
    except Exception: pass

    pub = "NO_BTN"
    for _ in range(5):
        st = pg.evaluate("""()=>{const b=document.querySelector('#publish-button');
          if(!b)return 'NO_BTN'; return (b.hasAttribute('disabled')||b.getAttribute('aria-disabled')==='true')?'DISABLED':'ENABLED';}""")
        if st == "ENABLED":
            pg.locator("#publish-button").first.click()
            pub = "PUBLISHED"; pg.wait_for_timeout(6000); break
        pub = st; pg.wait_for_timeout(2500)
    log(step="publish", result=pub)
    pg.wait_for_timeout(3000)

    pg.goto(url, wait_until="domcontentloaded", timeout=40000)
    pg.wait_for_timeout(7000)
    cur = pg.locator("input[type='text']").first.input_value()
    log(step="verify", current_handle=cur, ok=(cur.lower() == H.lower()), published=(pub == "PUBLISHED"))
    pg.close()
