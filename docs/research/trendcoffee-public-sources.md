# TREND Coffee — nguồn công khai đã kiểm chứng

Ngày khảo sát: **16/10/2026**. Phạm vi: `https://trendcoffee.net/`; chỉ đọc nội dung khách hàng và các API GET được ứng dụng công khai sử dụng. Không đăng nhập, gửi biểu mẫu, nhắn tin hay đặt hàng.

## Danh tính và liên hệ

[Chân trang và nội dung tiếng Việt trong ứng dụng](https://trendcoffee.net/assets/index-DmriD68d.js) công bố:

- Tên pháp lý: **HỘ KINH DOANH TREND COFFEE**; mã số thuế **8391342564-001**; ngày cấp ghi trên trang **02/04/2025**; người đại diện **Nguyễn Thị Mai Phương**. Đây là thông tin website tự công bố, chưa đối chiếu cơ quan đăng ký.
- Mục liên hệ sử dụng điện thoại **0886128008** và email **trend.coffee.tea@gmail.com**. Phần pháp lý ghi thêm **0945867620**. Chưa xác định hai số có cùng chức năng.
- Website liên kết [Fanpage Facebook](https://www.facebook.com/share/1BWte36sEf/?mibextid=wwXIfr). Có thể xác nhận đây là liên kết do website giới thiệu; chưa xác minh nội dung hoặc chủ sở hữu trang Facebook.

## Chi nhánh và khác biệt địa chỉ

[API chi nhánh](https://trendcoffee.net/api/latest/branch) tại thời điểm khảo sát trả về một bản ghi: **Chi nhánh 1**, mô tả **Chi nhánh Thủ Đức**, mã `ba9355f797`. Địa chỉ bản đồ là **3 Nguyễn Công Trứ, Hiệp Phú, Thủ Đức, Thành phố Hồ Chí Minh, Vietnam**, kèm [liên kết bản đồ](https://maps.google.com/?cid=300661943744505567).

Chân trang ghi **Số 03 đường Nguyễn Công Trứ, Phường Bình Thọ, Thành phố Thủ Đức, Thành phố Hồ Chí Minh, Việt Nam**. Hai nguồn thống nhất số nhà và đường nhưng khác phường. Không tự chọn một cách ghi hành chính làm đáp án duy nhất; cần xác nhận với quán.

## Thực đơn: phân biệt danh mục với món đang bán

[API danh mục](https://trendcoffee.net/api/latest/catalogs) công bố tám nhóm: sinh tố, món ăn, nước giải khát, cà phê, món bánh, giá tùy chỉnh, bia/rượu vang và món trà.

[API sản phẩm](https://trendcoffee.net/api/latest/products) trả về 124 sản phẩm trong phản hồi đã đọc, gồm cả bao bì, quà tặng giá 0, một món giá tùy chỉnh và tên thử nghiệm “Test AI”. Vì vậy không đưa toàn bộ danh mục sản phẩm vào thực đơn bán hàng. Các giá biến thể là dữ kiện công khai nhưng chưa đủ để khẳng định món được bán tại chi nhánh/ngày hiện tại.

Ứng dụng [thực đơn khách hàng](https://trendcoffee.net/assets/index-1sPxsUUR.js) lọc theo **ngày, chi nhánh, nhóm món, tên và khoảng giá**. Đã đọc thành công [API thực đơn khách hàng ngày 16/10/2026, Chi nhánh 1](https://trendcoffee.net/api/latest/menu/specific/public?date=2026-10-16&branch=ba9355f797&page=1) lúc **2026-10-16T15:27:55Z**: **51 món/51 biến thể tiêu chuẩn**, không còn trang tiếp theo. Cả 51 bản ghi đều active, không khóa, không ẩn/quà tặng/giá tùy chỉnh.

| Nhóm đang có trong thực đơn | Số món |
|---|---:|
| Cà phê | 15 |
| Món bánh | 10 |
| Món trà | 17 |
| Sinh tố | 9 |

Giá niêm yết **35.000–65.000 đồng**. Ví dụ: Cà phê đen 35.000; Cà phê sữa 40.000; Coffee Trend 60.000; Bánh Tiramisu 39.000; Matcha latte 55.000. Đây là ảnh chụp thực đơn theo ngày và chi nhánh. Tất cả món nhập vào JSON có `availability: unknown`; không suy diễn số lượng còn lại, tùy chọn đường/đá, thành phần hay dị ứng. Những nhóm xuất hiện trong danh mục chung nhưng không có trong thực đơn ngày này không được quảng bá là đang bán.

## Năng lực giao diện và quy tắc chưa xác nhận

[Mã ứng dụng công khai](https://trendcoffee.net/assets/index-DmriD68d.js) có luồng tại bàn, mang đi, giao hàng, giỏ hàng và thanh toán. Có đường dẫn `/booking`, `/order-instructions`, `/payment-instructions`, `/policy`, `/security`. Sự hiện diện của route hoặc nhãn thanh toán chỉ chứng minh giao diện được lập trình; không chứng minh dịch vụ đang bật hoặc giao dịch hoạt động.

Phí giao hàng phía giao diện được tính từ khoảng cách và `deliveryFeePerKm` của chi nhánh; có kiểm tra `maxDistanceDelivery`. GET `/api/latest/branch/ba9355f797/delivery-info` trả **401 Unauthorized**; dừng tại đây, không thử vượt kiểm soát truy cập. **Chưa xác lập được mức phí, bán kính giao hàng hoặc thời gian giao cụ thể.**

Nội dung giới thiệu đặt tiệc mô tả tiệc cá nhân và tiệc nhóm, menu theo set hoặc theo yêu cầu, trang trí và tư vấn qua hotline/Fanpage. Chưa có căn cứ về giá tiệc, sức chứa, lịch trống hay đặt cọc.

## Đặt hàng, thanh toán và hỗ trợ đã công bố

[Hướng dẫn đặt hàng](https://trendcoffee.net/order-instructions), qua [API nội dung](https://trendcoffee.net/api/latest/static-page/ORDER_INSTRUCTION), mô tả đăng nhập/đăng ký, chọn chi nhánh, tìm món, chọn kích cỡ/số lượng, thêm giỏ và đặt đơn. Đơn chưa thanh toán có thể sửa/hủy tại “Đơn hàng của tôi”; khi không thao tác được cần nhờ nhân viên. Hotline **0886128008 hỗ trợ 08:00–21:00 hằng ngày**; đây không phải giờ mở cửa quán.

[Hướng dẫn thanh toán](https://trendcoffee.net/payment-instructions), qua [API nội dung](https://trendcoffee.net/api/latest/static-page/PAYMENT_INSTRUCTION), công bố **QR là phương thức duy nhất**, hạn **15 phút từ lúc đặt**, quá hạn tự hủy. Nếu đã chuyển tiền nhưng chưa cập nhật sau khoảng một phút, giữ biên lai/mã giao dịch và liên hệ hỗ trợ. Không coi nội dung hướng dẫn là chứng cứ giao dịch thực tế đã thành công; enum tiền mặt/thẻ trong mã nguồn không thay thế chính sách này.

[Chính sách](https://trendcoffee.net/policy), qua [API nội dung](https://trendcoffee.net/api/latest/static-page/POLICY), đề cập hoàn tiền khi giao sai món, sản phẩm lỗi hoặc lỗi kỹ thuật làm đơn không xử lý được. Cụm “Thời gian phản hồi: 30 phút kể từ khi nhận hàng” chưa rõ cách áp dụng; **không diễn giải thành cam kết hoàn tiền trong 30 phút**. Giá có thể thay đổi; phương thức thanh toán phụ thuộc phiên bản ứng dụng. Nội dung ghi cập nhật 11/2025.

Chính sách cũng dẫn tới `/delete-account`: vô hiệu hóa tài khoản ngay và xóa dữ liệu tối đa 30 ngày, có ngoại lệ lưu giao dịch theo quy định. Chưa kiểm thử thao tác xóa.

## Giới hạn và nguyên tắc dùng cho agent

Chưa xác minh giờ mở cửa quán, tồn món, thành phần/dị ứng, thời gian nhận tiền hoàn, cách áp dụng mốc phản hồi 30 phút và năng lực giao dịch trực tiếp. Chỉ tư vấn dựa trên dữ kiện có nguồn; không hứa đơn được chấp nhận hoặc thanh toán thành công khi chưa có xác nhận từ hệ thống vận hành.

Dữ liệu đã lọc nằm tại [`data/trendcoffee-public.json`](../../data/trendcoffee-public.json), có nguồn và ngày kiểm chứng cho từng đoạn tri thức. Không chứa khóa cấu hình hoặc dữ liệu khách hàng.

Lần khảo sát đầu bằng công cụ trích xuất web không đọc được văn bản ứng dụng và tìm kiếm không có kết quả đúng tên miền. **Giới hạn lịch sử này đã được bổ sung bằng HTML/JavaScript và phản hồi API tải trực tiếp trong cùng phiên**, không phải kết luận website thiếu thông tin.

Không nhập dữ liệu từ `trendcoffee.com` tại Montclair, New Jersey hoặc quán trùng tên khác khi chưa có bằng chứng liên kết.
