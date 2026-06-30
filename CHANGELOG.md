# Changelog

All notable changes to Auto-Youtube are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/).

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
