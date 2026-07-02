# TEST THÀNH CÔNG — Multi-Account Rotation Upload (03/07/2026)

> Yêu cầu anh Nấng: test upload xoay 2 acc bằng clip có sẵn trong VPS, test OK thì push GitHub + ghi lại quá trình test.

## Môi trường test
- Keeper: systemd `yt-forever` (yt-gui-keeper.sh) — Chrome thật headful + CDP 18801 + noVNC, tab YouTube giữ sống. **active**.
- 2 account đã login vĩnh viễn, đăng ký registry:
  - `minhfrommars` — authuser 0 — kênh UCQOb70ar5EgoD4rtIjvS0fg — tên "Tần Số Nacha"
  - `tanso_nacha` — authuser 1 — kênh UCLuHAuQGklSW1AjpykHNScA — tên "Tần Số Nacha 1", @tansonacha1
- Rotation cursor reset về 0 trước khi test.

## Quá trình test (chạy thật, không mock)

### Bước 0 — Preview rotation
```
$ auto_youtube rotate-pick   # sau reset cursor=0
next pick: minhfrommars authuser 0
```

### Upload #1 — `--rotate` (kỳ vọng minhfrommars / authuser 0)
```
$ auto_youtube upload --file test-media/thien-dinh-lotus.mp4 \
    --title "Xoay Acc Test 1 — Thiền Tọa Sen 🧘" --rotate --visibility unlisted --short
=> ok: True | stage: published | acc: minhfrommars | authuser: 0 | video_id: rSc64oFVaBM
```
✅ Rotation chọn ĐÚNG account 0. Upload thật thành công, video published (unlisted).

### Upload #2 — `--rotate` (kỳ vọng tanso_nacha / authuser 1)
```
$ auto_youtube upload --file facebook-data/video-assets/blacknacha-shadow-moon-motion.mp4 \
    --title "Xoay Acc Test 2 — Shadow Moon 🌙" --rotate --visibility unlisted --short
=> ok: True | stage: published | acc: tanso_nacha | authuser: 1 | video_id: KRUqKRlQcuk
```
✅ Rotation TỰ XOAY sang account 1. Upload thật thành công.

### Verify — per-account rate isolation
```
$ auto_youtube accounts
minhfrommars authuser 0 -> 1 /50 today
tanso_nacha  authuser 1 -> 2 /50 today
```
✅ Mỗi account đếm quota RIÊNG. minhfrommars +1 (upload#1). tanso_nacha =2 (1 test upload trước đã xóa + upload#2). Không lẫn lộn.

## KẾT QUẢ
| Tiêu chí | Kết quả |
|---|---|
| Round-robin xoay 2 acc | ✅ #1→au0, #2→au1 tự động |
| Upload THẬT lên đúng kênh mỗi acc | ✅ rSc64oFVaBM (au0), KRUqKRlQcuk (au1) |
| authuser switch trong cùng browser | ✅ không login lại |
| Rate limit riêng từng acc | ✅ 1/50 và 2/50 độc lập |
| Tab YouTube giữ sống suốt test | ✅ keeper active, không crash |
| Clip nguồn từ VPS | ✅ thien-dinh-lotus.mp4 + blacknacha-shadow-moon-motion.mp4 |

## Ghi chú
- 2 video test đăng chế độ **unlisted** (không public), có thể xóa sau bằng `delete-video --id <vid> --account <acc> --confirm`.
- Handle @tansonacha cho Kênh 1 KHÔNG khả dụng (đã bị chiếm) — chờ anh Nấng chọn handle thay thế. Tên kênh + @tansonacha1 đã đổi xong.

**Kết luận: CHỨC NĂNG XOAY ACC UPLOAD HOẠT ĐỘNG THẬT, ĐẠT.**
