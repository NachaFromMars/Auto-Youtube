# Changelog

All notable changes to Auto-Youtube are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

## [1.2.0] - 2026-07-02

### Added
- **Auto-Reply engine** (`core/autoreply.py` + `auto-reply` command): scans comment inbox, classifies (praise/question/request/spam/negative/generic), replies from smart template pool (no immediate repeats), skips own-channel comments, flags spam/negative WITHOUT replying, dedupe state file prevents double-reply, human-like 8-20s gaps, `--dry-run` + `--max-replies` caps.
- 7 autoreply tests (22 total).

### Fixed (verified live 02/07)
- **Schedule flow**: Studio has NO "SCHEDULE" radio — it's a collapsed section; `_fill_schedule` now clicks `#second-container-expand-button`, verifies pre-filled date, picks time from 15-min dropdown. Verified real: video scheduled public 3 Jul 2026 20:00.
- **delete-video**: content-page hover menu doesn't render via JS; correct flow is edit-page `#overflow-menu-button` → "Delete" → checkbox → "Delete forever" + redirect verify. Verified real deletion.
- **comments inbox**: default "Unresponded" filter chip hides replied/own comments → chip removed on load; `list_comments` now sees all.
- **reply-comment submit**: thread-level "Reply" button only OPENS the box; real submit is the "Reply" button after "Cancel" → fixed + post-submit verify. Verified real reply posted.

## [1.1.0] - 2026-07-02

### Added — Full-stack manager (all verified LIVE on real Studio)
- **Manager** (`core/manager.py`): `list-videos` (Videos + Shorts tabs, id/title/visibility/views/date), `video-info` (title/desc/kids/visibility/draft-state), `edit-video` (title/description/visibility with post-save verify), `delete-video` (destructive, requires `--confirm`).
- **Analytics** (`core/analytics.py`): `channel-stats` (key metrics + realtime subscribers/views-48h), `video-stats`, `report` (overview + dashboard + video list one-shot).
- **Comments** (`core/comments.py`): `comments` (inbox reader), `reply-comment` (by index).
- **Optimizer** (`core/optimizer.py`, pure Python): `optimize` (SEO bundle: title + hashtag-injected description + tags), `best-time` (VN golden hours per content type), `next_slot` (next golden slot ISO for scheduling).
- **Uploader upgrades**: schedule datepicker fill (`_fill_schedule`), thumbnail upload for long videos, audience + visibility radio verify-with-retry (bug learned from first real upload).
- 4 new optimizer tests (15 total).

### Fixed (bugs found during first REAL upload, 2026-07-02)
- `input[type=file]` is hidden in YouTube upload dialog → `_first()` now supports `state="attached"`.
- Audience radio click not registering → video stuck in draft; now verified + JS-retried ×3 (same for visibility radios).
- Analytics SPA renders slowly → wait bumped to 7s (verified threshold).
- Content page: Shorts live in separate tab → list-videos scans Videos + Shorts tabs.

### Verified end-to-end
- First real upload: Shorts `lealmted3Zw` (unlisted) published successfully with rate-limit accounting (1/50).

## [1.0.0] - 2026-06-30

### Added
- **HumanMode engine** (`humanmode/humanmode.py`): Bézier mouse movement, human typing with typos + rhythm, reading-scroll, semantic pauses, `assert_youtube_url()` domain guard, random distraction.
- **Rate limiter** (`core/limits.py`): HARD CAP **50 uploads/day** (VN timezone), 8/hour soft cap, 90s min-gap between uploads. State persisted to JSON, daily rollover.
- **Smart layer** (`core/smart.py`): intelligent title optimization (length/keyword/emoji/anti-clickbait), COPPA-aware audience detection (made-for-kids + age-restriction), visibility + tag suggestions.
- **Session manager** (`core/session.py`): CLI ↔ persistent browser bridge via FIFO controller.
- **Studio flow** (`core/studio.py`): selector map (15 keys, fallback chains), 10-screen audit map, `crawl_studio_flow()` live selector resolver + DOM dump.
- **Uploader** (`core/uploader.py`): full upload flow (long + short) with HumanMode wired into every action, rate-limit gate before browser launch, controller pause/resume, per-stage screenshots.
- **CLI** (`auto_youtube_cli.py`): Click-based, `--json` default, one-shot commands — `status`, `login-check`, `limit-status`, `smart-plan`, `audit-studio`, `upload`, `list-videos`.
- **systemd service** (`deploy/yt-forever.service`): keeps browser profile logged-in 24/7, auto-restarts on reboot/crash.
- Tests, examples, docs, SELF-AUDIT report.

### Design principles
- **Quota-free**: no YouTube Data API v3 → no 10k-unit/day limit. Drives real Studio UI.
- **Anti-detection**: every action wrapped in HumanMode.
- **Safety**: no hardcoded secrets, destructive ops require `--confirm`, screenshots/logs on failure.

### Known gaps
- Studio selectors sourced from reference (adasq/youtube-studio); live DOM verification pending account verification (`audit-studio` ready to run).
