"""
Session manager — cầu nối CLI <-> yt_login_controller.py qua FIFO.
Gửi action JSON vào FIFO, đọc kết quả từ keeper log (dòng mới nhất sau khi gửi).

KHÔNG in secret. Mọi lệnh có timeout + log.
Controller actions hỗ trợ: goto, snapshot, eval, dump_dom, wait,
click_text, click_role, fill, press, check_login.
"""
import json
import os
import time

WS = "/root/.openclaw/workspace"
FIFO = os.path.join(WS, ".yt_ctrl_fifo")
LOG = os.path.join(WS, "youtube-cli/yt-forever-keeper.log")


class ControllerError(RuntimeError):
    pass


def _log_lines():
    try:
        with open(LOG, "r", encoding="utf-8", errors="replace") as f:
            return f.readlines()
    except FileNotFoundError:
        return []


def send(action: dict, wait_extra: float = 0.0, timeout: float = 60.0) -> dict:
    """Gửi 1 action vào FIFO, chờ controller xuất 1 dòng JSON kết quả mới.
    Trả dict kết quả (đã parse). Raise ControllerError nếu timeout/không hợp lệ."""
    if not os.path.exists(FIFO):
        raise ControllerError("FIFO_MISSING: controller chưa chạy? (systemctl status yt-forever)")
    before = len(_log_lines())
    payload = json.dumps(action, ensure_ascii=False)
    # ghi vào FIFO (non-blocking write end do holder giữ read mở)
    with open(FIFO, "w") as f:
        f.write(payload + "\n")
    # poll log cho dòng JSON mới
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        time.sleep(0.4)
        lines = _log_lines()
        for ln in lines[before:]:
            ln = ln.strip()
            if ln.startswith("{") and ln.endswith("}"):
                try:
                    last = json.loads(ln)
                except Exception:
                    continue
        if last is not None:
            break
    if wait_extra:
        time.sleep(wait_extra)
    if last is None:
        raise ControllerError(f"TIMEOUT chờ controller phản hồi action={action.get('action')}")
    return last


def check_login() -> dict:
    return send({"action": "check_login"}, timeout=20)


def is_logged_in() -> bool:
    try:
        return bool(check_login().get("logged_in"))
    except ControllerError:
        return False


def goto(url: str, wait_ms: int = 5000, name: str = "nav") -> dict:
    return send({"action": "goto", "url": url, "wait": wait_ms, "name": name},
                timeout=max(40, wait_ms / 1000 + 25))


def evaluate(js: str, save: str = None) -> dict:
    a = {"action": "eval", "js": js}
    if save:
        a["save"] = save
    return send(a, timeout=40)


def dump_dom(name: str = "dom") -> dict:
    return send({"action": "dump_dom", "name": name}, timeout=40)


def snapshot(name: str = "snap") -> dict:
    return send({"action": "snapshot", "name": name}, timeout=30)


def wait_ms(ms: int = 3000) -> dict:
    return send({"action": "wait", "ms": ms}, timeout=ms / 1000 + 15)
