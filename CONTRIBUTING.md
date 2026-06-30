# Contributing

## Dev setup
```bash
pip install -r requirements.txt
python -m playwright install chromium
python -m pytest tests/ -q
```

## Quy tắc
- **KHÔNG commit secret**: cookie, token, password, profile dir đều trong `.gitignore`. Kiểm tra `git diff` trước khi push.
- **HumanMode mọi thao tác**: mọi click/type tương tác Studio phải qua `humanmode.py`, không gọi `page.click` trực tiếp ở flow.
- **Rate limit bất khả xâm phạm**: không bypass `limits.check_can_upload()`. Cap 50/ngày là hard limit.
- **Destructive cần confirm**: xóa/private video yêu cầu `--confirm`.
- Thêm selector mới → cập nhật `studio.SELECTORS` với fallback chain, chạy `audit-studio` verify.

## Test
- Unit test offline (smart/limits): `tests/test_smart_limits.py`.
- Integration (Studio): chạy thủ công sau khi profile login + qua verification.

## PR
Mở PR vào `main`, mô tả thay đổi + kết quả test. Không tự merge khi chưa review.
