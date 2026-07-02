"""Tests cho multi-account registry + rotation + proxy + per-account limits."""
import os
import sys
import importlib
import tempfile
import pytest

CLI_DIR = os.path.join(os.path.dirname(__file__), "..", "agent-harness", "cli_anything")
sys.path.insert(0, os.path.abspath(CLI_DIR))


@pytest.fixture()
def fresh_state(tmp_path, monkeypatch):
    """Redirect STATE_DIR + files sang tmp để test cô lập."""
    from auto_youtube.core import accounts as acc
    from auto_youtube.core import limits as lim
    d = str(tmp_path)
    monkeypatch.setattr(acc, "STATE_DIR", d)
    monkeypatch.setattr(acc, "ACC_FILE", os.path.join(d, "accounts.json"))
    monkeypatch.setattr(lim, "STATE_DIR", d)
    monkeypatch.setattr(lim, "STATE_FILE", os.path.join(d, "rate_state.json"))
    return acc, lim


def test_add_and_list(fresh_state):
    acc, _ = fresh_state
    acc.add_account("a1", "a1@gmail.com", 0, channel_id="UC1")
    acc.add_account("a2", "a2@gmail.com", 1, channel_id="UC2")
    ids = [a["id"] for a in acc.list_accounts()]
    assert ids == ["a1", "a2"]


def test_duplicate_id_rejected(fresh_state):
    acc, _ = fresh_state
    acc.add_account("a1", "a1@gmail.com", 0)
    with pytest.raises(acc.AccountError):
        acc.add_account("a1", "x@gmail.com", 5)


def test_duplicate_authuser_rejected(fresh_state):
    acc, _ = fresh_state
    acc.add_account("a1", "a1@gmail.com", 0)
    with pytest.raises(acc.AccountError):
        acc.add_account("a2", "a2@gmail.com", 0)


def test_proxy_validate(fresh_state):
    acc, _ = fresh_state
    acc.add_account("a1", "a1@gmail.com", 0)
    a = acc.set_proxy("a1", {"server": "socks5://1.2.3.4:1080", "username": "u", "password": "p"})
    assert a["proxy"]["server"] == "socks5://1.2.3.4:1080"
    assert a["proxy"]["username"] == "u"
    # gỡ proxy
    a = acc.set_proxy("a1", None)
    assert a["proxy"] is None


def test_proxy_invalid(fresh_state):
    acc, _ = fresh_state
    acc.add_account("a1", "a1@gmail.com", 0)
    with pytest.raises(acc.AccountError):
        acc.set_proxy("a1", {"no_server": "x"})


def test_round_robin_rotation(fresh_state):
    acc, _ = fresh_state
    acc.add_account("a1", "a1@gmail.com", 0)
    acc.add_account("a2", "a2@gmail.com", 1)
    p1, _ = acc.pick_next()
    p2, _ = acc.pick_next()
    p3, _ = acc.pick_next()
    assert p1["id"] == "a1"
    assert p2["id"] == "a2"
    assert p3["id"] == "a1"  # cycle back


def test_rotation_skips_capped(fresh_state):
    acc, lim = fresh_state
    acc.add_account("a1", "a1@gmail.com", 0)
    acc.add_account("a2", "a2@gmail.com", 1)
    # đẩy a1 đầy cap
    for _ in range(lim.MAX_UPLOADS_PER_DAY):
        lim.record_upload(video_id="x", account_id="a1")
    # pick phải bỏ qua a1, chọn a2
    for _ in range(3):
        p, _ = acc.pick_next()
        assert p["id"] == "a2"


def test_all_capped_raises(fresh_state):
    acc, lim = fresh_state
    acc.add_account("a1", "a1@gmail.com", 0)
    for _ in range(lim.MAX_UPLOADS_PER_DAY):
        lim.record_upload(video_id="x", account_id="a1")
    with pytest.raises(acc.AccountError):
        acc.pick_next()


def test_per_account_rate_isolated(fresh_state):
    acc, lim = fresh_state
    lim.record_upload(video_id="v1", account_id="a1")
    lim.record_upload(video_id="v2", account_id="a1")
    lim.record_upload(video_id="v3", account_id="a2")
    assert lim.status(account_id="a1")["uploaded_today"] == 2
    assert lim.status(account_id="a2")["uploaded_today"] == 1
    # global vẫn riêng
    assert lim.status()["uploaded_today"] == 0


def test_disabled_account_skipped(fresh_state):
    acc, _ = fresh_state
    acc.add_account("a1", "a1@gmail.com", 0, enabled=False)
    acc.add_account("a2", "a2@gmail.com", 1)
    p, _ = acc.pick_next()
    assert p["id"] == "a2"


def test_authuser_url(fresh_state):
    acc, _ = fresh_state
    assert acc.authuser_url("https://studio.youtube.com/", 2) == "https://studio.youtube.com/?authuser=2"
    assert acc.authuser_url("https://x.com/?a=1", 3) == "https://x.com/?a=1&authuser=3"


def test_remove_account(fresh_state):
    acc, _ = fresh_state
    acc.add_account("a1", "a1@gmail.com", 0)
    acc.remove_account("a1")
    assert acc.list_accounts() == []
    with pytest.raises(acc.AccountError):
        acc.remove_account("nope")
