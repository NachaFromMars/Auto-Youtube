#!/usr/bin/env python3
"""Đổi TÊN kênh + HANDLE trên Studio profile page qua CDP.
Usage: rename_channel.py <CID> <authuser> "<new name>" "<new_handle_no_@>"

DOM verified live 03/07:
- Handle = input[type=text] đầu tiên (label 'Handle'), giá trị không có '@'
- Name   = div#textbox[contenteditable] (label 'Name')
- Publish = #publish-button (disabled đến khi có thay đổi hợp lệ)
"""
import sys, json
from playwright.sync_api import sync_playwright

CID = sys.argv[1]
AU = sys.argv[2]
NEW_NAME = sys.argv[3]
NEW_HANDLE = sys.argv[4].lstrip("@")
SHOT = "/root/.openclaw/workspace/youtube-cli"

def log(**d): print(json.dumps(d, ensure_ascii=False), flush=True)

with sync_playwright() as pw:
    b = pw.chromium.connect_over_cdp("http://127.0.0.1:18801", timeout=15000)
    ctx = b.contexts[0]
    pg = ctx.new_page()
    url = f"https://studio.youtube.com/channel/{CID}/editing/profile?hl=en&authuser={AU}"
    pg.goto(url, wait_until="domcontentloaded", timeout=50000)
    pg.wait_for_timeout(9000)
    log(step="loaded", url=pg.url[:70])

    # ---- NAME (div#textbox contenteditable) ----
    name_done = False
    try:
        name_box = pg.locator("div#textbox[contenteditable='true']").first
        name_box.wait_for(state="visible", timeout=10000)
        name_box.click()
        pg.keyboard.press("Control+A")
        pg.keyboard.press("Delete")
        pg.wait_for_timeout(400)
        pg.keyboard.type(NEW_NAME, delay=45)
        name_done = True
        log(step="name_typed", value=NEW_NAME)
    except Exception as e:
        log(step="name_err", error=str(e)[:120])

    pg.wait_for_timeout(1500)

    # ---- HANDLE (input[type=text] đầu tiên) ----
    handle_done = False
    try:
        handle_inp = pg.locator("input[type='text']").first
        handle_inp.wait_for(state="visible", timeout=8000)
        handle_inp.click()
        pg.keyboard.press("Control+A")
        pg.keyboard.press("Delete")
        pg.wait_for_timeout(400)
        pg.keyboard.type(NEW_HANDLE, delay=55)
        handle_done = True
        pg.wait_for_timeout(3000)  # chờ YouTube check availability
        log(step="handle_typed", value=NEW_HANDLE)
    except Exception as e:
        log(step="handle_err", error=str(e)[:120])

    pg.wait_for_timeout(2000)
    try: pg.screenshot(path=f"{SHOT}/rename-{AU}-before-publish.png")
    except Exception: pass

    # ---- PUBLISH ----
    pub_res = "NO_BTN"
    try:
        for _ in range(4):
            state = pg.evaluate("""()=>{
              const b=document.querySelector('#publish-button');
              if(!b) return 'NO_BTN';
              const dis=b.hasAttribute('disabled')||b.getAttribute('aria-disabled')==='true';
              return dis?'DISABLED':'ENABLED';
            }""")
            if state == "ENABLED":
                pg.locator("#publish-button").first.click()
                pub_res = "PUBLISHED"
                pg.wait_for_timeout(6000)
                break
            pub_res = state
            pg.wait_for_timeout(2500)
        log(step="publish", result=pub_res)
    except Exception as e:
        log(step="publish_err", error=str(e)[:120])

    pg.wait_for_timeout(3000)
    try: pg.screenshot(path=f"{SHOT}/rename-{AU}-after-publish.png")
    except Exception: pass

    # ---- VERIFY (reload) ----
    try:
        pg.goto(url, wait_until="domcontentloaded", timeout=40000)
        pg.wait_for_timeout(7000)
        cur = pg.evaluate("""()=>{
          const h=document.querySelector("input[type='text']");
          const n=document.querySelector("div#textbox[contenteditable='true']");
          return {handle:h?h.value:'', name:n?(n.textContent||'').trim():''};
        }""")
        log(step="verify", current_name=cur.get("name"), current_handle=cur.get("handle"),
            name_ok=(cur.get("name") == NEW_NAME),
            handle_ok=(NEW_HANDLE.lower() in (cur.get("handle") or "").lower()),
            published=(pub_res == "PUBLISHED"))
    except Exception as e:
        log(step="verify_err", error=str(e)[:120])

    pg.close()
