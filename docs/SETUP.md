# Setup — Auto-Youtube

## 1. Cài dependencies
```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## 2. Login profile (1 lần)
Auto-Youtube dùng profile Chromium đã login sẵn (`yt-forever-profile`). Login trực tiếp trên máy chạy (KHÔNG copy cookie từ máy khác — Google bind device/IP).

> ⚠️ Lần đầu login từ IP server lạ, Google có thể yêu cầu **selfie video verification**. Cần qua bước này 1 lần thì Studio mở vĩnh viễn trên profile.

## 3. Cài systemd service (giữ login 24/7)
```bash
sudo cp deploy/yt-forever.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now yt-forever.service
systemctl status yt-forever.service
```
Service tự khởi động lại khi reboot/crash, giữ browser login vĩnh viễn.

Chỉnh đường dẫn trong `deploy/yt-forever.service` cho khớp máy bạn (WorkingDirectory, script path, FIFO path).

## 4. Kiểm tra
```bash
cd agent-harness/cli_anything
python3 -m auto_youtube.auto_youtube_cli status
python3 -m auto_youtube.auto_youtube_cli smart-plan --title "Test"
```

## 5. Audit Studio flow (sau khi qua verification)
```bash
python3 -m auto_youtube.auto_youtube_cli audit-studio
```
Lệnh này tự crawl + dump DOM 10 màn Studio + resolve selector live → xác nhận coverage đầy đủ trước khi upload thật.

## 6. Upload
```bash
python3 -m auto_youtube.auto_youtube_cli upload --file v.mp4 --title "..." --dry-run
# bỏ --dry-run để upload thật
```
