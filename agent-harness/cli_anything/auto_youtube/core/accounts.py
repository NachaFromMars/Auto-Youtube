"""
Multi-account registry + rotation cho Auto-Youtube.

Mô hình: TẤT CẢ account đăng nhập trong CÙNG 1 browser profile
(yt-forever-profile). YouTube phân biệt account bằng chỉ số ?authuser=N.
Chuyển account = điều hướng URL kèm authuser tương ứng (ổn định hơn nhiều
so với multi-profile riêng lẻ, không phải login lại).

Registry: state/accounts.json
  {
    "accounts": [
      {
        "id": "minhfrommars",
        "email": "minhfrommars@gmail.com",
        "authuser": 0,            # chỉ số authuser trong browser
        "channel_id": "UC...",   # điền sau khi verify
        "channel_name": "",
        "proxy": null,           # {"server":"http://host:port","username":..,"password":..} hoặc null
        "enabled": true,
        "note": ""
      },
      ...
    ],
    "rotation": {"strategy": "round_robin", "cursor": 0}
  }

Rate limit MỖI ACCOUNT lưu riêng: state/rate_<id>.json (module limits xử lý).
Cap toàn cục 50/ngày/acc vẫn giữ; xoay acc để TĂNG TỔNG volume an toàn.
"""
import json
import os
from datetime import datetime, timezone, timedelta

VN_TZ = timezone(timedelta(hours=7))
STATE_DIR = "/root/.openclaw/workspace/Auto-Youtube/state"
ACC_FILE = os.path.join(STATE_DIR, "accounts.json")


class AccountError(RuntimeError):
    pass


def _now_vn():
    return datetime.now(VN_TZ)


def _default_registry():
    return {"accounts": [], "rotation": {"strategy": "round_robin", "cursor": 0}}


def load_registry():
    if os.path.exists(ACC_FILE):
        try:
            d = json.load(open(ACC_FILE, encoding="utf-8"))
            d.setdefault("accounts", [])
            d.setdefault("rotation", {"strategy": "round_robin", "cursor": 0})
            return d
        except Exception:
            pass
    return _default_registry()


def save_registry(reg):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = ACC_FILE + ".tmp"
    json.dump(reg, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    os.replace(tmp, ACC_FILE)
    return reg


def _validate_proxy(proxy):
    if proxy is None:
        return None
    if not isinstance(proxy, dict) or "server" not in proxy:
        raise AccountError("proxy phải là dict có 'server' (vd http://host:port hoặc socks5://host:port)")
    out = {"server": str(proxy["server"]).strip()}
    if proxy.get("username"):
        out["username"] = str(proxy["username"])
    if proxy.get("password"):
        out["password"] = str(proxy["password"])
    return out


def add_account(id, email, authuser, channel_id="", channel_name="",
                proxy=None, note="", enabled=True):
    reg = load_registry()
    if any(a["id"] == id for a in reg["accounts"]):
        raise AccountError(f"account id '{id}' đã tồn tại")
    if any(a.get("authuser") == int(authuser) for a in reg["accounts"]):
        raise AccountError(f"authuser={authuser} đã dùng bởi account khác")
    acc = {
        "id": id,
        "email": email,
        "authuser": int(authuser),
        "channel_id": channel_id,
        "channel_name": channel_name,
        "proxy": _validate_proxy(proxy),
        "enabled": bool(enabled),
        "note": note,
    }
    reg["accounts"].append(acc)
    save_registry(reg)
    return acc


def update_account(id, **fields):
    reg = load_registry()
    for a in reg["accounts"]:
        if a["id"] == id:
            if "proxy" in fields:
                fields["proxy"] = _validate_proxy(fields["proxy"])
            if "authuser" in fields:
                fields["authuser"] = int(fields["authuser"])
            a.update({k: v for k, v in fields.items() if v is not None or k in ("proxy", "note")})
            save_registry(reg)
            return a
    raise AccountError(f"không tìm thấy account id '{id}'")


def remove_account(id):
    reg = load_registry()
    n0 = len(reg["accounts"])
    reg["accounts"] = [a for a in reg["accounts"] if a["id"] != id]
    if len(reg["accounts"]) == n0:
        raise AccountError(f"không tìm thấy account id '{id}'")
    save_registry(reg)
    return True


def get_account(id):
    reg = load_registry()
    for a in reg["accounts"]:
        if a["id"] == id:
            return a
    raise AccountError(f"không tìm thấy account id '{id}'")


def list_accounts():
    return load_registry()["accounts"]


def set_proxy(id, proxy):
    """proxy=None để gỡ; dict để gán."""
    return update_account(id, proxy=_validate_proxy(proxy))


def _acc_can_upload(acc):
    """Import trễ để tránh vòng lặp; trả (ok, info) theo rate riêng của acc."""
    from . import limits
    ok, reason, info = limits.check_can_upload(account_id=acc["id"])
    info = dict(info)
    info["reason"] = reason
    return ok, info


def pick_next(strategy=None, only_enabled=True):
    """Chọn account kế tiếp theo chiến lược, BỎ QUA acc đã đạt cap ngày.
    Trả (account_dict, info) hoặc raise AccountError nếu không còn acc khả dụng."""
    reg = load_registry()
    accs = [a for a in reg["accounts"] if (a.get("enabled", True) or not only_enabled)]
    if not accs:
        raise AccountError("REGISTRY_EMPTY: chưa có account nào (dùng add-account)")

    strat = strategy or reg["rotation"].get("strategy", "round_robin")
    order = list(range(len(accs)))
    if strat == "round_robin":
        cur = reg["rotation"].get("cursor", 0) % len(accs)
        order = order[cur:] + order[:cur]
    elif strat == "least_used":
        from . import limits
        order.sort(key=lambda i: limits.status(account_id=accs[i]["id"])["uploaded_today"])

    for i in order:
        acc = accs[i]
        ok, info = _acc_can_upload(acc)
        if ok:
            # advance cursor sau khi chọn (round robin)
            if strat == "round_robin":
                reg["rotation"]["cursor"] = (i + 1) % len(accs)
                save_registry(reg)
            return acc, info
    raise AccountError("ALL_ACCOUNTS_AT_CAP: mọi account đã đạt giới hạn hôm nay")


def authuser_url(base_url, authuser):
    """Chèn ?authuser=N vào URL để thao tác đúng account."""
    sep = "&" if "?" in base_url else "?"
    return f"{base_url}{sep}authuser={int(authuser)}"


def summary():
    from . import limits
    reg = load_registry()
    out = []
    for a in reg["accounts"]:
        st = limits.status(account_id=a["id"])
        out.append({
            "id": a["id"], "email": a["email"], "authuser": a["authuser"],
            "channel_name": a.get("channel_name", ""),
            "enabled": a.get("enabled", True),
            "proxy": (a["proxy"]["server"] if a.get("proxy") else None),
            "uploaded_today": st["uploaded_today"],
            "remaining_today": st["remaining_today"],
        })
    return {"accounts": out, "rotation": reg["rotation"],
            "day_vn": _now_vn().strftime("%Y-%m-%d")}
