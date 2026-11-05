# Trend Coffee — discovery và đề xuất agent phục vụ khách

Ngày nghiên cứu: 16/10/2026. Trạng thái: **đề xuất nghiệp vụ ban đầu, giữ lại làm lịch sử khảo sát**. Truy cập mạng đã hoạt động ở giai đoạn triển khai; dữ kiện mới gồm menu/chính sách được kiểm chứng trong [biên bản nguồn cập nhật](trendcoffee-public-sources.md). Các giới hạn truy cập dưới đây mô tả lần khảo sát ban đầu, không phải kết quả mới nhất.

## 1. Kết quả nghiên cứu

[Website được chỉ định](https://trendcoffee.net/) trả về tiêu đề **TREND Coffee**, nhưng công cụ web không trích xuất được nội dung. Chưa đủ căn cứ kết luận nguyên nhân là JavaScript, đăng nhập hay cấu hình truy cập. Trình duyệt tự động của phiên khảo sát không khởi động được vì thiếu Chrome; truy cập trực tiếp từ shell không phân giải được tên miền.

Chưa xác minh được menu, giá, địa chỉ, giờ mở cửa, kênh liên hệ, hình thức nhận món và chính sách đổi/hủy. Các đường dẫn thử nghiệm không được coi là tính năng đã tồn tại. Xem [biên bản kiểm chứng nguồn](trendcoffee-public-sources.md). Chưa có bằng chứng Trend Coffee liên kết với Grab hoặc với các doanh nghiệp trùng tên.

Để vẫn đưa ra đề xuất có cơ sở, nghiên cứu tham khảo tài liệu chính thức về vận hành đơn đồ ăn/uống:

- GrabMerchant mô tả việc cửa hàng chủ động chấp nhận hoặc từ chối đơn theo khả năng phục vụ. **Suy luận cho đề xuất:** tách yêu cầu của khách khỏi việc quán chấp nhận. [Nguồn](https://merchant.grab.com/vn-vn/blog/nhandonthucong)
- Hướng dẫn xử lý đơn hủy phân biệt nguyên nhân từ cửa hàng và giao nhận; nêu việc cập nhật đóng/mở quán, hết món và thực đơn. **Suy luận cho đề xuất:** agent cần trạng thái vận hành hiện tại và cách chuyển người xử lý. [Nguồn](https://merchant.grab.com/vn-vn/blog/donhangbihuy)

Các tài liệu tham khảo không thay thế chính sách riêng của Trend Coffee.

## 2. Mô hình nghiệp vụ đề xuất

Agent có một cuộc hội thoại liên tục với khách, đồng thời phối hợp với thu ngân, pha chế và nhân viên phục vụ. Mục tiêu là giúp khách chọn đúng, nhận đúng và giải quyết xong yêu cầu.

| Vai trò | Việc agent thực hiện | Điều kiện để hoàn tất |
|---|---|---|
| Tư vấn bán hàng | Hỏi khẩu vị, ngân sách khi cần; gợi ý tối đa 2–3 lựa chọn phù hợp | Có món khách chọn từ menu đã kiểm chứng |
| Tiếp nhận đơn | Ghi từng ly, số lượng, tùy chọn, cách nhận; trình lại giá và tổng tiền | Khách xác nhận và quán tiếp nhận |
| Phục vụ | Theo dõi tiến độ, tiếp nhận yêu cầu hỗ trợ tại bàn nếu quán có phục vụ tại bàn | Nhân viên/hệ thống xác nhận đã xử lý |
| Hỗ trợ sau mua | Tra đơn, ghi nhận thiếu/sai món, đổi/hủy, vấn đề thanh toán | Có kết quả thực tế hoặc người tiếp quản rõ ràng |

Thứ tự ưu tiên đề xuất: chính xác món và tiền → hoàn thành phục vụ → gợi ý mua thêm phù hợp. Đo hiệu quả bằng đơn hoàn tất và sự cố được giải quyết, không chỉ số tin nhắn hay số món bán thêm.

## 3. Luồng đặt món

1. **Nhận diện nhu cầu:** xem menu, gọi món, hỏi tiến độ hay cần hỗ trợ. Hỏi thông tin còn thiếu; giữ lại thông tin khách đã cung cấp.
2. **Xác định cách nhận:** tại bàn, mang đi hoặc giao hàng, nhưng chỉ cung cấp hình thức quán thực sự hỗ trợ. Chỉ hỏi số bàn/điểm nhận/địa chỉ khi cần.
3. **Chọn món:** dựa trên menu, giá và trạng thái còn bán mới nhất. Các tùy chọn như kích cỡ, nóng/lạnh, đường/đá chỉ xuất hiện nếu món có hỗ trợ.
4. **Kiểm tra khả năng phục vụ:** quán đang nhận đơn, món còn bán, tùy chọn hợp lệ và thời gian đáp ứng. Hết món thì xin lựa chọn thay thế.
5. **Khách duyệt đơn:** đọc lại từng dòng món, tùy chọn, số lượng, cách nhận và tổng tiền. Phí chưa biết phải được nêu rõ trước khi chốt tổng.
6. **Gửi yêu cầu:** chỉ thông báo quán đã nhận khi có xác nhận thật và mã tham chiếu. Gửi lại sau lỗi phải kiểm tra đơn cũ để tránh trùng.
7. **Theo dõi đến khi nhận món:** tiến độ pha chế và giao nhận lấy từ hệ thống/nhân viên, không suy ra từ thời gian trôi qua.

### Hai trạng thái cần theo dõi riêng

```text
Đơn: bản nháp → khách xác nhận → chờ quán → quán nhận → chuẩn bị → sẵn sàng → hoàn tất
                                      ↘ từ chối/hết thời gian chờ

Tiền: chưa thanh toán → chờ xác minh → đã thanh toán
                                    ↘ thất bại
      đã thanh toán → yêu cầu hoàn → đang hoàn → đã hoàn/hoàn thất bại
```

Đây là mô hình đề xuất. Hủy đơn là một yêu cầu cần được duyệt theo trạng thái thực tế; hủy không đồng nghĩa đã hoàn tiền. Với giao hàng, cần thêm bước bàn giao và xác nhận giao thành công. Thời điểm thu tiền phải theo quy trình của quán, không mặc định thu trước hay sau.

## 4. Quy tắc quan trọng

- **Chi tiết từng ly:** hai ly cùng tên nhưng khác tùy chọn là hai dòng khác nhau; ghi chú của ly này không áp vào ly kia.
- **Tổng tiền:** cộng giá từng dòng và phụ thu hợp lệ, trừ ưu đãi đủ điều kiện, thêm các phí/thuế chưa được tính trong giá. Chỉ dùng giá và quy tắc đã xác minh; kiểm tra lại khi giỏ thay đổi.
- **Đổi món:** trình lại món và giá mới để khách xác nhận. Khi quán đã nhận hoặc đang pha chế, cần xác nhận khả năng đổi từ nhân viên.
- **Thanh toán:** lời khách báo chuyển khoản hoặc ảnh biên lai là thông tin cần đối soát; chỉ báo đã thanh toán khi nguồn thu tiền xác nhận.
- **Thời gian:** thông báo ước tính có nguồn và cập nhật khi thay đổi. Chưa có dữ liệu thì nói đang kiểm tra, không đưa mốc giao tùy ý.
- **Thành phần:** chỉ trả lời thông tin đã xác minh. Yêu cầu tránh thành phần hoặc dị ứng chưa đủ dữ liệu cần chuyển nhân viên kiểm tra trước khi chốt món.
- **Quyền xử lý:** agent tư vấn và chuẩn bị yêu cầu; tạo/sửa/hủy đơn, giảm giá hay hoàn tiền cần đúng quyền và kết quả thao tác thực tế.
- **Bàn giao:** lưu vấn đề, mã đơn, chi tiết đã xác minh, yêu cầu của khách, người phụ trách và tiến độ. Chỉ nói đã chuyển khi việc bàn giao thành công.

## 5. Dữ liệu cần có để agent phục vụ thật

| Nhóm | Nội dung tối thiểu | Cách sử dụng |
|---|---|---|
| Quán | Địa chỉ, giờ hoạt động, cách nhận món, đầu mối hỗ trợ | Trả lời thông tin và định tuyến |
| Menu | Mã món, tên, mô tả, giá, tùy chọn hợp lệ, thành phần đã xác minh | Tư vấn và lập đơn |
| Vận hành | Đang nhận đơn, hết món/tùy chọn, khả năng đáp ứng, thời điểm cập nhật | Kiểm tra trước khi chốt |
| Chính sách | Thanh toán, phí, ưu đãi, đổi/hủy, hoàn tiền, hóa đơn | Báo giá và xử lý yêu cầu đúng quyền |
| Giao dịch | Mã đơn, các dòng món, tổng tiền, tiến độ, thanh toán, lịch sử sửa | Theo dõi và đối soát |

Mỗi dữ kiện cần nguồn và thời điểm kiểm chứng. Menu công khai giúp mô tả sản phẩm; tồn món, tiến độ và thanh toán cần nguồn vận hành hiện tại. Khi các nguồn mâu thuẫn, xác minh lại thay vì chọn thông tin có lợi cho việc chốt đơn.

## 6. Phạm vi triển khai đề xuất

**Bước đầu:** một agent thống nhất để tư vấn theo menu đã kiểm chứng, lập bản nháp đơn và ghi nhận hỗ trợ. Nhân viên xác nhận đơn và tiền. Chọn một kênh đang có khách thực tế; website là ứng viên, chưa được xác minh là kênh đặt hàng hiện tại.

**Bước tiếp:** nối nguồn menu/tồn món và hệ thống nhận đơn đang được quán sử dụng; bổ sung tra tiến độ và xác nhận thanh toán. Chỉ mở quyền thao tác khi có kiểm soát trùng đơn và truy vết thay đổi.

**Mở rộng sau:** đặt lại món từng mua, gợi ý theo sở thích khách đồng ý lưu, ưu đãi và nhiều kênh. Giao hàng, đặt bàn, tích điểm và đặt số lượng lớn là khả năng để đánh giá, chưa phải dịch vụ đã xác nhận của Trend Coffee.

### Tình huống kiểm chứng trước khi phục vụ khách

| Tình huống | Kết quả mong đợi |
|---|---|
| Hai ly cùng món, tùy chọn khác nhau | Giữ đúng từng dòng và tổng tiền |
| Hết món sau lúc khách chọn | Báo thay đổi, đề xuất phương án hợp lệ, xin xác nhận lại |
| Gửi đơn bị mất phản hồi | Kiểm tra đơn đã tạo trước khi thử lại |
| Khách báo đã chuyển tiền nhưng chưa đối soát | Giữ trạng thái chờ xác minh, chuyển thu ngân |
| Khách sửa/hủy khi đang chuẩn bị | Ghi yêu cầu và xin quyết định của quán |
| Thiếu món hoặc giao trễ | Tra đơn, xác định người xử lý, theo dõi đến kết quả |
| Chuyển nhân viên không thành công | Báo đúng tình trạng và đưa kênh hỗ trợ đã xác minh nếu có |

Chỉ số đề xuất để đo trong thử nghiệm: độ chính xác dòng món/tổng tiền, tỷ lệ đơn khách xác nhận được quán tiếp nhận, tỷ lệ đơn hoàn tất, lỗi đơn trùng, thời gian giải quyết hỗ trợ và mức hài lòng. Chưa có dữ liệu để đặt mục tiêu doanh thu hay thời gian phục vụ cụ thể.

## 7. Kết luận và giới hạn

Đề xuất ưu tiên một agent **hiểu nhu cầu → chuẩn bị đơn đúng → phối hợp phục vụ → theo dõi đến kết quả**. Đây là khung nghiệp vụ có thể dùng để chuẩn bị triển khai. Discovery riêng về Trend Coffee vẫn còn thiếu nội dung website đã hiển thị và nguồn vận hành; chưa thể khẳng định đã hiểu menu hoặc quy trình thực tế của quán.
