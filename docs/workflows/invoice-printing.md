# In hóa đơn khi merchant xác nhận thanh toán

Launcher kiosk và cấu hình MCP của project đặt `TREND_PRINT_QUEUE=GP-C180I`. Chạy `serve`/`mcp` trực tiếp cần đặt biến này để bật in; đặt chuỗi rỗng để tắt. Thay đổi môi trường có hiệu lực khi dịch vụ/MCP khởi động lần tiếp theo. Stack đang dừng được giữ nguyên trong lần triển khai này.

## Điều kiện và tài liệu

Sau khi đơn mới có mã merchant, hệ thống lưu lịch in trong cùng transaction SQLite. Worker của API/MCP tiếp tục theo dõi dù khách đóng trang hoặc phiên giọng nói kết thúc. Việc khách quét QR chưa phải bằng chứng thanh toán.

Chỉ in khi đơn merchant có trạng thái `paid` hoặc `completed`, payment có **cả** `statusCode=completed` và `statusMessage=completed`, đúng mã đơn/chi nhánh hoặc dấu nhận diện kiosk, món/số lượng và số tiền; đồng thời có `invoice.slug` hợp lệ. Hóa đơn có thể xuất hiện chậm hơn thanh toán, khi đó worker tiếp tục đợi. Đơn đã có trước khi bật tính năng không tự được đăng ký in.

PDF lấy từ `POST https://trendcoffee.net/api/latest/invoice/export/public` với `{"order":"<merchant_order_slug>"}`, theo mẫu OpenJarvis được cung cấp tại `src/openjarvis/kiosk/printing.py` và `cups.py`. Chỉ chấp nhận PDF tối đa 5 MB, không theo redirect. Không dựng phiếu giả từ dữ liệu giỏ hàng. PDF chuyển thành ESC/POS 576 dot / 203 dpi, giữ toàn bộ các trang, gửi CUPS một bản tới `GP-C180I`.

Yêu cầu cài CUPS (`lp`, `ipptool`) và Poppler (`pdftoppm`). `lpstat -p GP-C180I` chỉ đọc trạng thái máy in. Adapter không thay đổi cấu hình CUPS hoặc hàng đợi khác.

Mỗi bản in có dòng cố định in đậm phía trên hóa đơn: `AI ORDER,QUY KHACH VUI LONG DOI 15 NHAN MON TAI QUAY NHE`. Nội dung được xuống hai dòng để vừa giấy, xuất hiện một lần cho cả tài liệu nhiều trang và không sửa PDF merchant.

## Tool và trạng thái

- MCP `print_invoice(session_token, order_id)`: đăng ký một lần cho đơn của chính khách; gọi lại trả trạng thái cũ, không in lại hoặc vượt qua kiểm tra merchant.
- MCP `get_invoice_status(session_token, order_id)`: đọc trạng thái.
- HTTP tương ứng: `POST` / `GET /api/orders/{order_id}/invoice`, dùng guest Bearer token.

| Trạng thái | Ý nghĩa |
|---|---|
| `waiting`, `checking` | Chưa đủ chứng cứ hoặc đang tải/xử lý PDF; chưa gửi máy in |
| `submitting`, `held`, `releasing` | Đang gửi một job giữ lại, lưu ID rồi xác minh đúng job trước khi cho in |
| `submitted`, `processing` | CUPS đã nhận job; chưa khẳng định in xong |
| `completed` | Đúng job CUPS báo hoàn tất thành công, không còn queued-in-device/cảnh báo |
| `failed` | Chứng cứ/tài liệu không khớp hoặc job báo lỗi |
| `unknown` | Không xác định kết quả gửi/nhả job; nhân viên kiểm tra hàng đợi/giấy |

Khóa duy nhất mã đơn merchant/mã hóa đơn và chuyển trạng thái nguyên tử ngăn API/MCP/worker đồng thời gửi bản thứ hai. Khởi động lại tiếp tục job đã giữ có ID xác định. Mất phản hồi khi gửi/nhả job giữ trạng thái chưa rõ; hệ thống không gửi lại bản mới. File PDF/raster tạm được xóa sau xử lý. Sổ in lưu theo thời hạn 30 ngày của đơn khách.

## Kiểm chứng

`uv run pytest tests/test_invoice_printing.py tests/test_printer.py -q` dùng merchant/printer giả lập, gồm hoàn tất thanh toán, PDF lỗi, quyền theo khách, worker MCP, chạy đồng thời, khởi động lại và mất phản hồi máy in. Không tạo đơn/thu tiền/in giấy thật. Kiểm chứng ngoài quầy còn cần một giao dịch hoàn tất thực tế để kiểm tra giấy in từ PDF merchant và hành vi máy in vật lý.
