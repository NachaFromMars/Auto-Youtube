"""Unit tests cho smart layer + rate limiter. Chạy offline, KHÔNG cần browser."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "agent-harness", "cli_anything"))

from auto_youtube.core import smart, limits  # noqa: E402


# ---------- smart_title ----------
def test_title_basic():
    r = smart.smart_title("Hướng dẫn thiền định")
    assert r["value"] == "Hướng dẫn thiền định"


def test_title_truncate():
    long = "A" * 150
    r = smart.smart_title(long)
    assert len(r["value"]) <= smart.MAX_TITLE
    assert any("truncated" in w for w in r["warnings"])


def test_title_prepend_keyword():
    r = smart.smart_title("video mới", keywords=["Thiền Định"])
    assert "Thiền Định" in r["value"][:40]


# ---------- smart_audience ----------
def test_audience_kids():
    r = smart.smart_audience("Bài hát thiếu nhi cho bé học chữ")
    assert r["made_for_kids"] is True


def test_audience_mature():
    r = smart.smart_audience("Phim kinh dị 18+ bạo lực")
    assert r["age_restrict"] is True
    assert r["made_for_kids"] is False


def test_audience_neutral_default_notkids():
    r = smart.smart_audience("Review điện thoại 2026")
    assert r["made_for_kids"] is False


def test_audience_force():
    r = smart.smart_audience("anything", force="kids")
    assert r["made_for_kids"] is True


# ---------- visibility ----------
def test_visibility_scheduled():
    r = smart.suggest_visibility("2026-07-01T18:00:00")
    assert r["value"] == "scheduled"


def test_visibility_default_private():
    r = smart.suggest_visibility(None)
    assert r["value"] == "private"


# ---------- limits ----------
def test_limit_constants():
    assert limits.MAX_UPLOADS_PER_DAY == 50


def test_limit_can_upload_shape():
    ok, reason, info = limits.check_can_upload()
    assert isinstance(ok, bool)
    assert "max" in info or "count" in info


if __name__ == "__main__":
    import subprocess
    raise SystemExit(subprocess.call(["python3", "-m", "pytest", "-q", __file__]))


# ---- v1.1: optimizer tests ----
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", "agent-harness", "cli_anything"))
from auto_youtube.core import optimizer  # noqa: E402


def test_best_time_shapes():
    r = optimizer.best_time("short")
    assert r["kind"] == "short"
    assert isinstance(r["golden_hours_vn"], list) and r["golden_hours_vn"]
    assert r["day_type"] in ("weekday", "weekend")


def test_next_slot_future():
    from datetime import datetime
    r = optimizer.next_slot("long")
    assert r["slot_vn"] is not None
    assert datetime.fromisoformat(r["slot_vn"]) > datetime.now()


def test_optimize_seo_short_adds_shorts_hashtag():
    r = optimizer.optimize_seo("Thiền buổi sáng", "nhạc thiền", ["thiền"], is_short=True)
    assert "#Shorts" in r["hashtags"]
    assert "#Shorts" in r["description"] or "#shorts" in r["description"].lower()
    assert r["next_slot"]["slot_vn"]


def test_optimize_seo_no_duplicate_hashtags():
    desc = "đã có #thiền rồi"
    r = optimizer.optimize_seo("Thiền tĩnh tâm", desc, [], is_short=False)
    assert r["description"].lower().count("#thiền") == 1
