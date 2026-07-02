"""
Auto-Youtube CLI — agent-native, chuẩn CLI-Anything.
Core = Playwright + yt-forever-profile + HumanMode. Né quota Data API.
HARD CAP 50 video/ngày. Mọi thao tác bọc HumanMode.

One-shot commands + --json + log/screenshot khi lỗi. KHÔNG hardcode secret.
Destructive (delete/private) yêu cầu --confirm.
"""
import json
import sys

import click

from .core import (accounts, analytics, autoreply, comments, limits, manager,
                   optimizer, session, smart, studio, uploader)


def emit(data, as_json=True):
    if as_json or not isinstance(data, str):
        click.echo(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        click.echo(data)

def _apply_account(account_id):
    """Set authuser cho session theo account trong registry. None = mặc định."""
    if not account_id:
        session.set_authuser(None)
        return None
    try:
        acc = accounts.get_account(account_id)
    except accounts.AccountError as e:
        emit({"ok": False, "error": str(e)})
        sys.exit(2)
    session.set_authuser(acc["authuser"])
    return acc



@click.group(invoke_without_command=True)
@click.option("--json-output", "--json", "as_json", is_flag=True, default=True,
              help="Machine-readable JSON (default on)")
@click.pass_context
def cli(ctx, as_json):
    """Auto-Youtube — YouTube automation qua HumanMode, né quota, cap 50/ngày."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = as_json
    if ctx.invoked_subcommand is None:
        emit({"name": "auto-youtube", "version": "1.3.0", "ready": True,
              "commands": ["status", "login-check", "audit-studio", "smart-plan",
                           "upload", "list-videos", "video-info", "edit-video",
                           "delete-video", "report", "channel-stats", "video-stats",
                           "optimize", "best-time", "comments", "reply-comment", "auto-reply",
                           "limit-status", "accounts", "add-account", "remove-account",
                           "set-proxy", "rotate-pick", "account-status"],
              "hard_cap_per_day": limits.MAX_UPLOADS_PER_DAY,
              "multi_account": True, "proxy_support": True})


@cli.command("login-check")
@click.pass_context
def login_check(ctx):
    """Kiểm tra profile còn login YouTube không."""
    try:
        emit(session.check_login())
    except session.ControllerError as e:
        emit({"ok": False, "error": str(e)})
        sys.exit(1)


@cli.command("limit-status")
@click.option("--account", "account_id", default=None, help="Rate riêng theo account id")
def limit_status(account_id):
    """Trạng thái rate limit (đã upload / còn lại hôm nay)."""
    emit(limits.status(account_id=account_id))

# ---------------- MULTI-ACCOUNT + PROXY ----------------
@cli.command("accounts")
def accounts_list():
    """Liệt kê tất cả account trong registry + rate riêng từng acc."""
    emit(accounts.summary())


@cli.command("account-status")
def account_status():
    """Tổng quan multi-acc: acc nào còn quota, acc nào đầy, proxy gán gì."""
    emit(accounts.summary())


@cli.command("add-account")
@click.option("--id", "acc_id", required=True, help="ID ngắn (vd minhfrommars)")
@click.option("--email", required=True)
@click.option("--authuser", type=int, required=True, help="Chỉ số authuser trong browser (0,1,2..)")
@click.option("--channel-id", default="")
@click.option("--channel-name", default="")
@click.option("--proxy", default=None, help="vd http://host:port hoặc socks5://host:port")
@click.option("--proxy-user", default=None)
@click.option("--proxy-pass", default=None)
@click.option("--note", default="")
def add_account(acc_id, email, authuser, channel_id, channel_name,
                proxy, proxy_user, proxy_pass, note):
    """Thêm 1 account vào registry xoay vòng."""
    pxy = None
    if proxy:
        pxy = {"server": proxy}
        if proxy_user:
            pxy["username"] = proxy_user
        if proxy_pass:
            pxy["password"] = proxy_pass
    try:
        acc = accounts.add_account(acc_id, email, authuser, channel_id,
                                   channel_name, pxy, note)
        emit({"ok": True, "added": acc})
    except accounts.AccountError as e:
        emit({"ok": False, "error": str(e)})
        sys.exit(2)


@cli.command("remove-account")
@click.option("--id", "acc_id", required=True)
@click.option("--confirm", is_flag=True, help="BẮT BUỘC")
def remove_account(acc_id, confirm):
    """Xoá account khỏi registry (không đăng xuất browser, chỉ gỡ khỏi rotation)."""
    if not confirm:
        emit({"ok": False, "error": "cần --confirm"})
        sys.exit(2)
    try:
        accounts.remove_account(acc_id)
        emit({"ok": True, "removed": acc_id})
    except accounts.AccountError as e:
        emit({"ok": False, "error": str(e)})
        sys.exit(2)


@cli.command("set-proxy")
@click.option("--id", "acc_id", required=True)
@click.option("--proxy", default=None, help="vd http://host:port; bỏ trống để GỠ proxy")
@click.option("--proxy-user", default=None)
@click.option("--proxy-pass", default=None)
def set_proxy(acc_id, proxy, proxy_user, proxy_pass):
    """Gán / gỡ proxy cho 1 account."""
    pxy = None
    if proxy:
        pxy = {"server": proxy}
        if proxy_user:
            pxy["username"] = proxy_user
        if proxy_pass:
            pxy["password"] = proxy_pass
    try:
        acc = accounts.set_proxy(acc_id, pxy)
        emit({"ok": True, "account": acc["id"],
              "proxy": (acc["proxy"]["server"] if acc.get("proxy") else None)})
    except accounts.AccountError as e:
        emit({"ok": False, "error": str(e)})
        sys.exit(2)


@cli.command("rotate-pick")
@click.option("--strategy", type=click.Choice(["round_robin", "least_used"]), default=None)
def rotate_pick(strategy):
    """Chọn account kế tiếp để upload (bỏ qua acc đầy cap). Xem trước quyết định xoay."""
    try:
        acc, info = accounts.pick_next(strategy=strategy)
        emit({"ok": True, "picked": acc["id"], "email": acc["email"],
              "authuser": acc["authuser"], "rate": info})
    except accounts.AccountError as e:
        emit({"ok": False, "error": str(e)})
        sys.exit(3)




@cli.command("status")
def status_cmd():
    """Tổng trạng thái: login + rate limit."""
    out = {"rate": limits.status()}
    try:
        out["login"] = session.check_login()
    except session.ControllerError as e:
        out["login"] = {"ok": False, "error": str(e)}
    emit(out)


@cli.command("audit-studio")
@click.option("--save", default="studio-flow-audit", show_default=True)
def audit_studio(save):
    """Crawl + audit toàn bộ flow Studio (selector + dump DOM mỗi màn).
    Chạy khi đã qua verification. Báo cáo crawl ĐỦ chức năng."""
    try:
        rep = studio.crawl_studio_flow(session, audit_save=save)
        emit(rep)
        if rep.get("blocked"):
            sys.exit(2)
    except session.ControllerError as e:
        emit({"ok": False, "error": str(e)})
        sys.exit(1)


@cli.command("smart-plan")
@click.option("--title", required=True)
@click.option("--description", default="")
@click.option("--tags", default="", help="comma-separated")
@click.option("--schedule", default=None, help="ISO time để đặt lịch")
@click.option("--short", is_flag=True)
def smart_plan(title, description, tags, schedule, short):
    """Xem trước quyết định thông minh: title/audience/visibility/tags. KHÔNG upload."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    plan = {
        "title": smart.smart_title(title, keywords=tag_list),
        "audience": smart.smart_audience(title, description, tag_list),
        "visibility": smart.suggest_visibility(schedule, is_short=short),
        "tags": smart.suggest_tags(title, description, extra=tag_list),
    }
    emit(plan)


@cli.command("upload")
@click.option("--file", "video_path", required=True, type=click.Path(exists=True))
@click.option("--title", required=True)
@click.option("--description", default="")
@click.option("--tags", default="", help="comma-separated")
@click.option("--kids", type=click.Choice(["auto", "yes", "no"]), default="auto")
@click.option("--visibility", type=click.Choice(["private", "unlisted", "public"]),
              default="private", show_default=True)
@click.option("--schedule", default=None, help="ISO time -> scheduled")
@click.option("--short", is_flag=True, help="Đánh dấu Shorts")
@click.option("--playlist", default=None)
@click.option("--thumbnail", default=None, type=click.Path())
@click.option("--dry-run", is_flag=True, help="Chỉ in plan, KHÔNG upload")
@click.option("--account", "account_id", default=None,
              help="account id trong registry (switch authuser + rate riêng + proxy). Bỏ trống=mặc định")
@click.option("--rotate", is_flag=True, help="Tự chọn account kế tiếp (bỏ qua acc đầy cap)")
def upload_cmd(video_path, title, description, tags, kids, visibility, schedule,
               short, playlist, thumbnail, dry_run, account_id, rotate):
    """Upload 1 video (HumanMode, gate 50/ngày). --dry-run để xem plan trước.
    --account <id> up bằng acc cụ thể; --rotate tự xoay acc để tăng volume."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    mfk = {"auto": None, "yes": True, "no": False}[kids]
    if rotate and not account_id:
        try:
            acc, _info = accounts.pick_next()
            account_id = acc["id"]
        except accounts.AccountError as e:
            emit({"ok": False, "stage": "rotate", "error": str(e)})
            sys.exit(3)
    res = uploader.upload(
        video_path=video_path, title=title, description=description, tags=tag_list,
        made_for_kids=mfk, visibility=visibility, schedule_iso=schedule,
        is_short=short, playlist=playlist, thumbnail=thumbnail, dry_run=dry_run,
        account_id=account_id)
    emit(res)
    if not res.get("ok"):
        sys.exit(3)


@cli.command("list-videos")
@click.option("--limit", default=20, show_default=True)
@click.option("--account", "account_id", default=None, help="account id (switch authuser)")
def list_videos(limit, account_id):
    """Liệt kê video trên kênh: id, title, visibility, views, date."""
    _apply_account(account_id)
    try:
        emit(manager.list_videos(session, limit=limit))
    except (session.ControllerError, RuntimeError) as e:
        emit({"ok": False, "error": str(e)})
        sys.exit(1)

@cli.command("video-info")
@click.option("--id", "video_id", required=True)
@click.option("--account", "account_id", default=None, help="account id (switch authuser)")
def video_info(video_id, account_id):
    """Chi tiết 1 video: title, desc, kids, visibility, draft-state."""
    _apply_account(account_id)
    try:
        emit(manager.get_video(session, video_id))
    except (session.ControllerError, RuntimeError) as e:
        emit({"ok": False, "error": str(e)})
        sys.exit(1)

@cli.command("edit-video")
@click.option("--id", "video_id", required=True)
@click.option("--title", default=None)
@click.option("--description", default=None)
@click.option("--visibility", type=click.Choice(["private", "unlisted", "public"]),
              default=None)
@click.option("--account", "account_id", default=None, help="account id (switch authuser)")
def edit_video(video_id, title, description, visibility, account_id):
    """Sửa title/description/visibility video đã up (verify sau khi save)."""
    _apply_account(account_id)
    if title is None and description is None and visibility is None:
        emit({"ok": False, "reason": "cần ít nhất 1 trong --title/--description/--visibility"})
        sys.exit(1)
    try:
        emit(manager.edit_video(session, video_id, title=title,
                                description=description, visibility=visibility))
    except (session.ControllerError, RuntimeError) as e:
        emit({"ok": False, "error": str(e)})
        sys.exit(1)

@cli.command("delete-video")
@click.option("--id", "video_id", required=True)
@click.option("--confirm", is_flag=True, help="BẮT BUỘC để xóa thật (destructive)")
@click.option("--account", "account_id", default=None, help="account id (switch authuser)")
def delete_video(video_id, confirm, account_id):
    """XÓA video vĩnh viễn. Destructive — yêu cầu --confirm."""
    _apply_account(account_id)
    try:
        res = manager.delete_video(session, video_id, confirm=confirm)
        emit(res)
        if not res.get("ok"):
            sys.exit(3)
    except (session.ControllerError, RuntimeError) as e:
        emit({"ok": False, "error": str(e)})
        sys.exit(1)

@cli.command("channel-stats")
@click.option("--account", "account_id", default=None, help="account id (switch authuser)")
def channel_stats(account_id):
    """Số liệu kênh từ Studio Analytics (không tốn quota API)."""
    _apply_account(account_id)
    try:
        emit(analytics.channel_overview(session))
    except (session.ControllerError, RuntimeError) as e:
        emit({"ok": False, "error": str(e)})
        sys.exit(1)

@cli.command("video-stats")
@click.option("--id", "video_id", required=True)
@click.option("--account", "account_id", default=None, help="account id (switch authuser)")
def video_stats_cmd(video_id, account_id):
    """Số liệu 1 video từ analytics."""
    _apply_account(account_id)
    try:
        emit(analytics.video_stats(session, video_id))
    except (session.ControllerError, RuntimeError) as e:
        emit({"ok": False, "error": str(e)})
        sys.exit(1)

@cli.command("report")
@click.option("--limit", default=10, show_default=True, help="Số video trong báo cáo")
@click.option("--account", "account_id", default=None, help="account id (switch authuser)")
def report_cmd(limit, account_id):
    """Báo cáo tổng hợp kênh: overview + dashboard + video list."""
    _apply_account(account_id)
    try:
        emit(analytics.report(session, manager, limit=limit))
    except (session.ControllerError, RuntimeError) as e:
        emit({"ok": False, "error": str(e)})
        sys.exit(1)

@cli.command("optimize")
@click.option("--title", required=True)
@click.option("--description", default="")
@click.option("--tags", default="", help="comma-separated")
@click.option("--short", is_flag=True)
def optimize_cmd(title, description, tags, short):
    """Gói tối ưu SEO: title + desc + hashtags + tags + giờ vàng + slot kế tiếp."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    emit(optimizer.optimize_seo(title, description, tag_list, is_short=short))

@cli.command("best-time")
@click.option("--kind", type=click.Choice(["short", "long"]), default="long",
              show_default=True)
def best_time_cmd(kind):
    """Giờ vàng đăng bài hôm nay (giờ VN) + slot kế tiếp."""
    emit({"today": optimizer.best_time(kind), "next_slot": optimizer.next_slot(kind)})

@cli.command("comments")
@click.option("--limit", default=15, show_default=True)
@click.option("--account", "account_id", default=None, help="account id (switch authuser)")
def comments_cmd(limit, account_id):
    """Đọc comment inbox mới nhất."""
    _apply_account(account_id)
    try:
        emit(comments.list_comments(session, limit=limit))
    except (session.ControllerError, RuntimeError) as e:
        emit({"ok": False, "error": str(e)})
        sys.exit(1)

@cli.command("reply-comment")
@click.option("--index", required=True, type=int, help="Index từ lệnh comments")
@click.option("--text", required=True)
@click.option("--account", "account_id", default=None, help="account id (switch authuser)")
def reply_comment_cmd(index, text, account_id):
    """Reply comment theo index trong inbox."""
    _apply_account(account_id)
    try:
        res = comments.reply_comment(session, index, text)
        emit(res)
        if not res.get("ok"):
            sys.exit(3)
    except (session.ControllerError, RuntimeError) as e:
        emit({"ok": False, "error": str(e)})
        sys.exit(1)

@cli.command("auto-reply")
@click.option("--limit", default=20, show_default=True, help="Số comment quét")
@click.option("--max-replies", default=20, show_default=True)
@click.option("--dry-run", is_flag=True, help="Chỉ xem plan, KHÔNG reply thật")
@click.option("--channel-handle", default=None,
              help="Handle chủ kênh (vd @BanTangTocDai) để bỏ qua comment tự đăng")
def auto_reply_cmd(limit, max_replies, dry_run, channel_handle):
    """AUTO-REPLY: quét inbox → phân loại (khen/hỏi/request/spam) → reply thông minh.
    Spam/negative chỉ flag, KHÔNG reply. Chống reply trùng qua state file."""
    try:
        res = autoreply.run(session, limit=limit, max_replies=max_replies,
                            dry_run=dry_run, channel_handle=channel_handle)
        emit(res)
        if not res.get("ok"):
            sys.exit(3)
    except (session.ControllerError, RuntimeError) as e:
        emit({"ok": False, "error": str(e)})
        sys.exit(1)

if __name__ == "__main__":
    cli()
