# Bot theo dõi vé sự kiện CTSV HUST (GitHub Actions + ntfy)

Bot tự kiểm tra danh sách vé theo lịch trên GitHub; iPhone nhận thông báo nếu danh sách hoặc số chỗ thay đổi, kể cả khi laptop đã tắt. **Bot không tự đặt vé.**

## Bước 1: Chuẩn bị iPhone

1. Cài ứng dụng **ntfy** chính chủ tại https://apps.apple.com/app/ntfy/id1625396347.
2. Mở ntfy, chọn Subscribe to topic, dùng máy chủ `https://ntfy.sh`. Tự đặt tên topic **dài và khó đoán**, chẳng hạn `hustctsv-A7fQ2xZ9wLm5Vr83` (không dùng y nguyên ví dụ này).
3. Cho phép thông báo cho ntfy trên iPhone.
4. Kiểm tra ntfy từ Windows PowerShell (đổi tên topic trước khi chạy):

```powershell
Invoke-RestMethod -Method Post -Uri 'https://ntfy.sh/TOPIC_RIENG_CUA_BAN' -Body ([Text.Encoding]::UTF8.GetBytes('Test thong bao CTSV HUST')) -ContentType 'text/plain; charset=utf-8'
```

Nếu điện thoại chưa nhận, kiểm tra ntfy trước khi cài bot.

## Bước 2: Lấy phiên đăng nhập trên Windows

Yêu cầu cài Python. Chạy `python --version` trước; nếu Windows không nhận lệnh, cài Python và bật tùy chọn thêm Python vào PATH. **Mở PowerShell trong thư mục giải nén `hust-ctsv-bot`, không chạy tại `C:\Windows\System32`**:

```powershell
python -m pip install -r requirements.txt
python -m playwright install chromium
python capture_login.py
```

Cửa sổ Chromium sẽ mở ra. **Tự đăng nhập HUST** trên cửa sổ này, mở phần Đặt vé và chờ danh sách sự kiện hiện ra. Quay lại PowerShell, nhấn Enter. Script lưu `.auth/auth.b64`.

**CẢNH BÁO:** Đây là thông tin phiên đăng nhập, có thể cho phép người khác truy cập tài khoản. Không gửi file/nội dung của file cho ai, không tải file lên GitHub, không dán vào chat. Tập tin `.gitignore` đã chặn thư mục `.auth/` nếu bạn dùng Git đúng cách.

## Bước 3: Tạo repo và đưa mã nguồn lên GitHub

1. Tại https://github.com/new tạo repository `hust-ctsv-watcher` (**Public**). Repo công khai chỉ chứa mã bot và dấu vân tay SHA-256, **không chứa** thông tin phiên đăng nhập.
2. Tải source lên đúng cấu trúc: `capture_login.py`, `check_events.py`, `requirements.txt`, `README.md`, `state/last.json`, `.github/workflows/monitor.yml` và `.gitignore`.
3. Cách dễ để giữ đúng cấu trúc thư mục là dùng GitHub Desktop (https://desktop.github.com/). Chọn **File > Add local repository** và chọn thư mục bot; nếu được hỏi tạo repository tại đây thì đồng ý. Sau đó **Publish repository** lên GitHub ở chế độ Public. Kiểm tra kỹ danh sách file chuẩn bị commit: tuyệt đối không có `.auth/`.

## Bước 4: Cài GitHub Secrets

Trong repository: **Settings > Secrets and variables > Actions > New repository secret**.

Tạo 2 secrets:

- `NTFY_TOPIC`: tên topic riêng (không phải cả URL).
- `HUST_AUTH_B64`: nội dung của `.auth/auth.b64`. Muốn copy an toàn từ PowerShell:

```powershell
Get-Content -Raw .auth\auth.b64 | Set-Clipboard
```

Dán vào trường secret trên GitHub; không tạo file trong repo.

Nếu GitHub Actions không ghi được state, vào **Settings > Actions > General > Workflow permissions**, chọn **Read and write permissions** rồi Save.

## Bước 5: Chạy thử và bật tự động

1. Vào repository > **Actions > HUST CTSV ticket watcher > Run workflow** để chạy thử.
2. Lượt chạy đầu chỉ lưu dấu mốc bảng sự kiện, **không gửi thông báo cho các sự kiện đang có sẵn**.
3. Các lượt sau tự chạy theo Cron (mặc định cách nhau 5 phút). Khi phát hiện thay đổi, sẽ gửi thông báo qua ntfy đến iPhone; chạm để mở trang đặt vé.
4. Nếu báo lỗi, mở **Actions > lần chạy gần nhất > Monitor events** để xem bước lỗi. Không đăng ảnh/log chứa phiên đăng nhập hay secrets.

## Chi phí, thời gian và hạn chế

- **Public repo + runner tiêu chuẩn**: GitHub Actions miễn phí. Tránh vô tình commit dữ liệu cá nhân do repo là công khai.
- **Private repo**: GitHub Free có 2.000 phút Actions/tháng, và *mỗi job tính làm tròn lên phút*, chạy mỗi 5 phút có thể vượt hạn mức. Để giảm xuống hai lần mỗi giờ, sửa `.github/workflows/monitor.yml`:

```yaml
on:
  schedule:
    - cron: '3,33 * * * *'
```

- Lịch GitHub có thể trễ hoặc bỏ lỡ một số lượt; không đảm bảo kịp vé mở rất nhanh.
- Trình phân tích theo dõi **bảng sự kiện nói chung**; thay đổi số chỗ, trạng thái, tên sự kiện hoặc bố cục đều có thể phát thông báo. Không xác nhận được chỉ có sự kiện mới.
- CTSV có thể thay đổi bố cục, yêu cầu xác thực bổ sung, hoặc không cho tái dùng phiên đăng nhập từ máy chủ. Hãy kiểm tra lượt chạy đầu; bot sẽ báo lỗi đọc trang thay vì cam kết đang hoạt động.
- Khi phiên hết hạn, chạy lại `python capture_login.py` và cập nhật secret `HUST_AUTH_B64`.
- Tôn trọng quy định CTSV; không dùng bot để vượt CAPTCHA hoặc tự động giữ chỗ trái quy định.
- Dừng theo dõi bằng cách tắt workflow trong tab Actions. Nếu nghi lộ phiên đăng nhập, đăng xuất mọi thiết bị (nếu hệ thống hỗ trợ), thu hồi và tạo phiên mới.
