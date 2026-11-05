# Trend Kiosk Manager (cửa sổ bật/tắt dịch vụ)

Cửa sổ desktop đơn giản cho nhân viên không dùng terminal. Nó gọi `scripts/kiosk.py`, nên
chỉ dừng các tiến trình mà launcher đã ghi nhận cho thư mục này.

## Mở

- Cài lối tắt một lần: `.venv/bin/python scripts/install_manager_shortcut.py`, rồi mở menu ứng dụng
  và tìm **Trend Kiosk Manager**.
- Hoặc chạy trực tiếp: `.venv/bin/python scripts/kiosk_manager_gui.py` (cần `.venv` có Tkinter và một màn hình).

## Dùng

- Thanh trên cùng: **Kiosk đang rảnh** (xanh), **Đang phục vụ khách** (cam), hoặc chưa kết nối được.
- Ba dịch vụ: Trend (API), Thị giác (Visual), Nhân vật (Avatar). Mỗi dịch vụ có đèn trạng thái
  (xanh đang chạy, cam đang khởi động, đỏ đã tắt, xám = cổng đang do chương trình khác dùng) và các nút
  Bật, Tắt, Khởi động lại, Nhật ký. Có thêm Bật tất cả, Tắt tất cả, Khởi động lại tất cả, Mở kiosk.
- Tắt hoặc khởi động lại khi **đang có khách**: cửa sổ hỏi chọn *Chờ khách xong rồi làm* (tự làm khi kiosk
  rảnh liên tục 30 giây), *làm ngay* (ngắt khách), hoặc Hủy.
- Cài đặt: mã nhân viên `TREND_STAFF_TOKEN` (lấy từ biến môi trường nếu có, nếu không từ
  `.runtime/kiosk-manager.json`, quyền 0600, không vào git) và tùy chọn **Tự bật lại dịch vụ nếu bị tắt
  ngoài ý muốn** (mặc định tắt; tối đa 3 lần trong 10 phút, cách nhau 30 giây; chỉ với dịch vụ đang
  chạy khi mở cửa sổ hoặc do cửa sổ bật).
- Đóng cửa sổ không tắt kiosk.

## Mã nguồn và kiểm tra

- Logic không cần màn hình: `scripts/kiosk_manager.py`. Cửa sổ Tkinter: `scripts/kiosk_manager_gui.py`.
- `tests/test_kiosk_manager.py`: logic bằng giả lập (không bật dịch vụ thật); test cửa sổ tự bỏ qua khi không có màn hình.
