# SELF-AUDIT v1.3.0 — MULTI-ACCOUNT + PROXY + CDP KEEPER (03/07/2026)

> Yêu cầu anh Nấng: login vĩnh viễn 2 acc, build xoay acc (add thoải mái), khung proxy, audit kỹ.

## ✅ HẠ TẦNG LOGIN — ĐÃ VÁ TRIỆT ĐỂ
| Hạng mục | Trạng thái | Bằng chứng |
|---|---|---|
| Profile cũ crash SIGTRAP (OOM) | ✅ backup + tạo profile mới sạch | headful test OK trên profile mới |
| Login 2 acc | ✅ anh Nấng login tay qua noVNC | LOGGED_IN=true cả authuser 0 + 1 |
| Keeper mới (thay controller FIFO crash) | ✅ `yt-gui-keeper.sh` + systemd | active; Chrome thật + CDP 18801 + noVNC + tab YouTube giữ sống, auto-restart |
| Tự login script | ❌ Google chặn headless ("browser not secure") | phải login tay qua noVNC — đã làm |
| Cookies persist | ✅ 86 cookies (SAPISID/SID/LOGIN_INFO) | verify qua CDP |

## ✅ 2 ACCOUNT ĐÃ ĐĂNG KÝ (verify live)
| id | email | authuser | channel_id | quota |
|---|---|---|---|---|
| minhfrommars | minhfrommars@gmail.com | 0 | UCQOb70ar5EgoD4rtIjvS0fg (From Mars Minh) | 50/ngày riêng |
| tanso_nacha | tanso.nacha@gmail.com | 1 | UCLuHAuQGklSW1AjpykHNScA (Official Nacha) | 50/ngày riêng |

→ Tổng volume: **100 video/ngày** (2 acc × 50). Add thêm acc → cộng thêm 50/acc.

## ✅ MULTI-ACCOUNT ENGINE (module `accounts.py`)
- Registry `state/accounts.json`: id/email/authuser/channel/proxy/enabled/note
- **Chuyển acc = authuser** (`?authuser=N`) trong CÙNG 1 browser — ổn định, không login lại, không multi-profile rời rạc
- Rotation round_robin (0→1→0) + least_used; **tự bỏ qua acc đầy cap ngày**
- Rate limit RIÊNG mỗi acc: `state/rate_<id>.json` (limits.py account-aware, giữ tương thích global cũ)
- CLI: `accounts`, `account-status`, `add-account`, `remove-account`, `rotate-pick`

## ✅ PROXY SCAFFOLDING
- Mỗi acc gán proxy riêng (http/socks5 + user/pass): `set-proxy --id X --proxy socks5://h:p`
- `add-account ... --proxy ...` gán ngay lúc thêm
- Uploader đọc proxy acc; ghi chú tầng keeper để launch chrome với proxy tương ứng (multi-proxy per-acc cần keeper riêng — đã tài liệu hoá, khung sẵn sàng)
- Validate proxy: bắt buộc field `server`, sai format → reject

## ✅ CLI ACCOUNT-AWARE (10 lệnh nhận `--account`)
upload (+`--rotate`), list-videos, video-info, edit-video, delete-video,
channel-stats, video-stats, report, comments, reply-comment.
`_apply_account()` set authuser trước khi thao tác.

## ✅ VERIFY LIVE END-TO-END (03/07)
| Thao tác | Acc | Kết quả |
|---|---|---|
| login-check qua CDP | current | logged_in=true, session_index=1 |
| list-videos --account minhfrommars | authuser 0 | kênh UCQOb..., video "Thiền Định Tọa Sen" |
| list-videos (default) | authuser 1 | kênh UCLuHA..., video "Câu chuyện của bé" |
| switch authuser 0↔1 | — | studio resolve đúng channel mỗi acc |
| **upload REAL --account tanso_nacha** | authuser 1 | ✅ video_id 4L5kgANh13o, unlisted, rate tanso 1/50 |
| **delete REAL --account tanso_nacha** | authuser 1 | ✅ verified_gone=true |
| rate isolation | — | minhfrommars 0/50, tanso 1/50 riêng biệt |
| tab YouTube giữ sống sau upload/delete | — | ✅ vẫn 1 tab, keeper active |

## 🐛 BUG THẬT BẮT + FIX (03/07)
1. **Uploader stop systemd + relaunch headful** → clobber keeper + crash SIGTRAP + tắt tab.
   → FIX: uploader connect qua CDP (tab mới), KHÔNG stop keeper, giữ tab YouTube sống.
2. **Selector chỉ tiếng Anh** ("Create"/"Delete") → acc tanso.nacha UI tiếng Việt ("Tạo"/"Xóa") → fail.
   → FIX: (a) ép `?hl=en` khi upload; (b) selector bilingual Create/Tạo, Delete/Xóa, "Delete forever"/"Xóa vĩnh viễn"; manager goto dùng hl=en.
3. **session.py FIFO controller** đã bỏ (crash) → rewrite sang CDP, API giữ nguyên tương thích manager/comments/analytics + thêm `set_authuser()`.

## 🧪 TESTS: 34/34 PASS
22 cũ + 12 mới (test_accounts.py): add/dup-reject/proxy-validate/rotation/skip-capped/all-capped/per-acc-rate-isolation/disabled-skip/authuser-url/remove.

## ⚠️ GHI CHÚ / VIỆC CÒN LẠI (không chặn)
- Multi-proxy per-acc THẬT: hiện browser keeper 1 instance dùng chung; proxy field đã lưu + uploader đọc, nhưng để mỗi acc đi proxy khác nhau đồng thời cần keeper launch nhiều chrome (mỗi acc 1 proxy) — khung đã có, kích hoạt khi anh cấp danh sách proxy.
- comments/analytics delete English-only vài chỗ khác: đã phủ hl=en cho manager; nếu gặp UI Việt chỗ khác sẽ bổ sung bilingual tương tự.

## KẾT LUẬN v1.3
Multi-account + rotation + proxy scaffolding HOÀN CHỈNH, verify THẬT: upload/list/switch/delete per-acc chạy live trên 2 kênh. Login vĩnh viễn ổn định qua CDP keeper (hết crash). Add acc mới = 1 lệnh `add-account`. Tăng volume 50→100→... theo số acc.
