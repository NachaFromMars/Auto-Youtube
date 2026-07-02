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

from .core import (analytics, comments, limits, manager, optimizer, session,
                   smart, studio, uploader)


def emit(data, as_json=True):
    if as_json or not isinstance(data, str):
        click.echo(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        click.echo(data)


@click.group(invoke_without_command=True)
@click.option("--json-output", "--json", "as_json", is_flag=True, default=True,
              help="Machine-readable JSON (default on)")
@click.pass_context
def cli(ctx, as_json):
    """Auto-Youtube — YouTube automation qua HumanMode, né quota, cap 50/ngày."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = as_json
    if ctx.invoked_subcommand is None:
        emit({"name": "auto-youtube", "version": "1.1.0", "ready": True,
              "commands": ["status", "login-check", "audit-studio", "smart-plan",
                           "upload", "list-videos", "video-info", "edit-video",
                           "delete-video", "report", "channel-stats", "video-stats",
                           "optimize", "best-time", "comments", "reply-comment",
                           "limit-status"],
              "hard_cap_per_day": limits.MAX_UPLOADS_PER_DAY})


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
def limit_status():
    """Trạng thái rate limit (đã upload / còn lại hôm nay)."""
    emit(limits.status())


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
def upload_cmd(video_path, title, description, tags, kids, visibility, schedule,
               short, playlist, thumbnail, dry_run):
    """Upload 1 video (HumanMode, gate 50/ngày). --dry-run để xem plan trước."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    mfk = {"auto": None, "yes": True, "no": False}[kids]
    res = uploader.upload(
        video_path=video_path, title=title, description=description, tags=tag_list,
        made_for_kids=mfk, visibility=visibility, schedule_iso=schedule,
        is_short=short, playlist=playlist, thumbnail=thumbnail, dry_run=dry_run)
    emit(res)
    if not res.get("ok"):
        sys.exit(3)


@cli.command("list-videos")
@click.option("--limit", default=20, show_default=True)
def list_videos(limit):
    """Liệt kê video trên kênh: id, title, visibility, views, date."""
    try:
        emit(manager.list_videos(session, limit=limit))
    except (session.ControllerError, RuntimeError) as e:
        emit({"ok": False, "error": str(e)})
        sys.exit(1)

@cli.command("video-info")
@click.option("--id", "video_id", required=True)
def video_info(video_id):
    """Chi tiết 1 video: title, desc, kids, visibility, draft-state."""
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
def edit_video(video_id, title, description, visibility):
    """Sửa title/description/visibility video đã up (verify sau khi save)."""
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
def delete_video(video_id, confirm):
    """XÓA video vĩnh viễn. Destructive — yêu cầu --confirm."""
    try:
        res = manager.delete_video(session, video_id, confirm=confirm)
        emit(res)
        if not res.get("ok"):
            sys.exit(3)
    except (session.ControllerError, RuntimeError) as e:
        emit({"ok": False, "error": str(e)})
        sys.exit(1)

@cli.command("channel-stats")
def channel_stats():
    """Số liệu kênh từ Studio Analytics (không tốn quota API)."""
    try:
        emit(analytics.channel_overview(session))
    except (session.ControllerError, RuntimeError) as e:
        emit({"ok": False, "error": str(e)})
        sys.exit(1)

@cli.command("video-stats")
@click.option("--id", "video_id", required=True)
def video_stats_cmd(video_id):
    """Số liệu 1 video từ analytics."""
    try:
        emit(analytics.video_stats(session, video_id))
    except (session.ControllerError, RuntimeError) as e:
        emit({"ok": False, "error": str(e)})
        sys.exit(1)

@cli.command("report")
@click.option("--limit", default=10, show_default=True, help="Số video trong báo cáo")
def report_cmd(limit):
    """Báo cáo tổng hợp kênh: overview + dashboard + video list."""
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
def comments_cmd(limit):
    """Đọc comment inbox mới nhất."""
    try:
        emit(comments.list_comments(session, limit=limit))
    except (session.ControllerError, RuntimeError) as e:
        emit({"ok": False, "error": str(e)})
        sys.exit(1)

@cli.command("reply-comment")
@click.option("--index", required=True, type=int, help="Index từ lệnh comments")
@click.option("--text", required=True)
def reply_comment_cmd(index, text):
    """Reply comment theo index trong inbox."""
    try:
        res = comments.reply_comment(session, index, text)
        emit(res)
        if not res.get("ok"):
            sys.exit(3)
    except (session.ControllerError, RuntimeError) as e:
        emit({"ok": False, "error": str(e)})
        sys.exit(1)

if __name__ == "__main__":
    cli()
