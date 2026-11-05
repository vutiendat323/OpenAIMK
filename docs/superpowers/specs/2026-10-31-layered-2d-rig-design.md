# Rig 2D theo lớp cho Nhân vật Trend

Ngày: 2026-10-31. Trạng thái: bản nháp, chờ người dùng duyệt.
Thay thế cách ghép miệng trong `docs/evals/browser-2d-motion.md`.
Nghiên cứu nền: `docs/research/2026-10-31-2d-talking-character.md`.

## Ý định và lý do

Người dùng đã từ chối bản 2D hiện tại sau nhiều vòng góp ý. Bản này phát video có sẵn rồi
dán ảnh miệng lên mặt, nên "miệng một nơi, mặt một nơi, mỗi nơi một kiểu". Người dùng cũng
mệt vì phải ghép và chỉnh mãi. Vì vậy không chỉnh tiếp cách ghép.

Mục tiêu mới: khi khách đứng trước kiosk, Trend trông như một nhân vật liền một khối đang
nói chuyện. Đầu, mắt, miệng, tóc và thân là một mô hình duy nhất, cử động cùng nhau theo
tiếng nói thật của trợ lý, giống clip mẫu.

Dựng rig thay vì talking head neural vì nghiên cứu không tìm thấy phương pháp neural nào có
bằng chứng chạy được thời gian thực cho nét anime trên RTX 3060. Rig vẽ trên trình duyệt rất
nhẹ, và mọi phần cùng lấy từ một nét vẽ.

## Người dùng đã quyết định

- Nhân dạng: `image.png_3ae5f671.jpg`, tóc búi cao, áo trắng ngà, tạp dề xanh.
- Cách cử động: theo `Woman_greeting_customers_at_counter_b58d415e_1080p.mp4`.
- Hiển thị mượt 30–60 FPS. Đây là FPS hiển thị, không phải FPS do mô hình tạo.
- Làm rig theo lớp từ các nguồn trên. Không nâng GPU.
- Đầu, mắt, miệng, tóc và thân là một rig liên tục, chạy theo âm thanh đầu ra của trợ lý.
- Khi im lặng: miệng ngậm, nhân vật chỉ thở và chớp mắt. Ngắt lời thì miệng dừng ngay.
- Tư thế gốc: tay đan trước bụng. Trend đứng yên trong một khung hình, không có đoạn máy
  quay tiến lại gần.
- Bản đầu có hai tư thế tay: tay đan trước bụng, và hai tay mở ngửa lòng bàn tay. Chuyển
  qua lại bằng vài khung lấy từ clip. Tay buông xuôi để sau.
- Đầu chỉ quay và nghiêng nhẹ, ít hơn clip. Đây là đánh đổi đã chấp nhận để tránh méo mặt.
- Vùng bị che chỉ được tô màu và mượn từ vùng lân cận, không dùng AI vẽ bù.
- Giai đoạn khuôn mặt có tối đa 2 vòng sửa, bắt đầu bằng một bản thử nhanh.

Lựa chọn của người viết, người dùng chưa phản đối:

- Viết rig bằng WebGL ngay trong kiosk, không dùng Live2D.
- Cắt lớp từ clip mẫu, không vẽ mới bằng AI.

## Mục tiêu

- Nhìn liền một khối: không còn cảm giác miệng và mặt thuộc hai hình khác nhau.
- Miệng biến dạng liên tục cùng khuôn mặt, không đổi ảnh dán.
- Đầu nghiêng và gật theo nhịp câu nói, mắt chớp, có lúc cười híp mắt, vai thở nhẹ, tóc
  đung đưa nhẹ theo đầu.
- Ít nhất 30 FPS hiển thị ổn định trên kiosk, hướng tới 60.

## Không làm

- Không dựng chân. Nguồn không có chân.
- Không nhận dạng âm vị tiếng Việt.
- Không đổi chế độ 3D, Ditto, hay giọng nói native.
- Không thêm dịch vụ đám mây, khóa API, hay chi phí trả phí.

## Coi là thất bại, dù kỹ thuật chạy được

- Lộ đường cắt hoặc lệch màu giữa các lớp.
- Mặt, đầu hoặc tay bị méo hay trông như cao su.
- Trông khác nhân vật trong ảnh tham chiếu.
- Miệng cử động khi không có tiếng, hoặc mở khi đã bị ngắt lời.
- Trông rời rạc theo đánh giá của người dùng, dù test đều pass. Biên độ quay đầu nhỏ hơn
  clip không tính là thất bại.

## Ràng buộc giữ nguyên

- Chỉ đọc âm thanh đầu ra của trợ lý, không dùng micro, không cần transcript.
- Giữ `VoicePlayer`, Fusion và kiểm tra guest-generation. 2D vẫn bỏ qua Ditto.
- Chọn trong Settings → Chung → Nhân vật khi micro tắt. Mặc định vẫn là 3D.
- Giữ ảnh poster dự phòng khi không có WebGL hoặc mất context. Tôn trọng reduced-motion:
  tắt chuyển động phụ, miệng vẫn hoạt động.
- Test và video xem thử chỉ dùng fixture, không tạo đơn hàng, thanh toán hay lệnh in thật.

## Thiết kế

Các chi tiết dưới đây là lựa chọn của người viết, trừ khi đã nêu ở phần quyết định.

**Tài nguyên.** Một script offline mới cắt lớp từ clip mẫu trong đoạn máy quay đã ổn định.
Tách nhân vật khỏi nền. Vẽ bù các vùng bị che: da dưới tóc, cổ dưới cằm, thân sau cánh tay.
Vùng bị che chỉ dùng tô màu và mượn vùng lân cận. Xóa dấu lấp lánh ở góc dưới phải trong clip. Lớp tối thiểu: tóc sau, búi tóc, thân, cổ, mặt,
trong miệng và răng, môi, mắt, mi, lông mày, tóc trước, hai tay. Xuất một atlas và một
manifest mô tả lớp, lưới và tham số.

**Nền.** Bóng trên tường trong clip gắn với tư thế tay, nên bỏ bóng và dùng nền phẳng cùng
màu tường.

**Rig.** Mỗi lớp là một lưới tam giác. Tham số gồm: quay đầu ngang, gật, nghiêng, mở mắt,
cười mắt, hướng nhìn, mở miệng, dạng miệng, thở, và tư thế tay. Rig dùng một góc nhìn duy nhất.
Quay đầu ở biên độ nhỏ, dùng độ lệch khác nhau giữa các lớp để tạo chiều sâu giả. Tóc đi theo đầu với độ trễ nhẹ.

**Điều khiển từ âm thanh.** Dùng lại đặc trưng âm lượng và âm sắc đã có, nhưng đưa vào biến
dạng lưới liên tục thay vì đổi ảnh. Đầu gật theo điểm bắt đầu cụm từ. Chuyển động khi nghỉ
dùng nhịp có biến thiên để không lặp đều.

**Tư thế tay.** Tay đan là nền. Âm thanh chỉ đến theo luồng nên không biết trước độ dài
câu. Vì vậy tay mở được kích hoạt sau khi tiếng nói kéo dài liên tục khoảng 1–2 giây, có
khoảng cách tối thiểu giữa hai lần, không xảy ra ở mọi câu. Động tác có thể bắt đầu giữa câu.
Khi bị ngắt lời, tay về tư thế gốc
mượt mà, không nhảy hình. Các khung chuyển lấy từ clip nên có nhịp gốc 24 FPS.

**Tích hợp.** Rig thay nội dung bên trong `Avatar2D` và `avatar2d.ts`. Cách chọn chế độ và
hợp đồng `read()` với `useKioskVoice.ts` giữ nguyên. Bản hybrid hiện tại chỉ bị xóa sau khi
người dùng chấp nhận rig mới; trước đó nó vẫn là bản hoạt động.

## Các giai đoạn và cổng duyệt

Sau mỗi giai đoạn, người dùng xem video từ trình duyệt thật. Không chuyển giai đoạn khi chưa
được chấp nhận.

1. **Khuôn mặt:** chỉ đầu, mắt, miệng, tóc trên thân tĩnh, nói bằng fixture Maple. Làm bản
   thử nhanh trước khi xây script hoàn chỉnh. Đây là cổng quan trọng nhất. Có tối đa 2 vòng
   sửa sau bản đầu. Nếu vẫn không đạt, dừng và bàn về thuê họa sĩ cùng thợ rig Live2D.
2. **Thân:** thở, vai, chuyển động khi nghỉ, phiên nói dài và ngắt lời.
3. **Tay:** hai tư thế và chuyển động giữa chúng.
4. **Đưa vào kiosk:** thay bản hybrid, cập nhật tài liệu và bằng chứng.

## Tiêu chí nghiệm thu

- Người dùng chấp nhận bằng mắt ở mỗi cổng. Test không thay thế được bước này.
- Đo trên trình duyệt GPU thật: FPS hiển thị từ 30 trở lên ở 1080×1920 và 1440×1000.
- Im lặng: miệng ngậm và không biến dạng. Ngắt lời: miệng về ngậm, gói âm thanh muộn bị bỏ.
- Fallback poster, reduced-motion và mất context có test trình duyệt.
- 3D không đổi. Bộ test frontend, build, lint và test trình duyệt 2D pass.

## Rủi ro

- Rig tự viết có thể không đẹp bằng rig chuyên nghiệp. Đây là rủi ro lớn nhất, nên giai đoạn
  1 kiểm tra nó sớm.
- Clip chỉ có 1080p và là nguồn AI, nên chi tiết nhỏ có thể mềm hoặc khác nhau giữa các khung.
- Vùng tô bù có thể trông phẳng hoặc lộ nếu đầu quay quá giới hạn, nên góc quay phải bị chặn.
- Tay có thể là chỗ lộ nhất vì lấy từ khung clip riêng.
- Nếu giai đoạn 1 không đạt sau 2 vòng sửa, phương án còn lại là thuê họa sĩ và thợ rig
  Live2D, có chi phí.

## Để người xây dựng tự quyết

Thuật toán tách nền và vẽ bù, số lớp và lưới chi tiết, định dạng atlas, hằng số chuyển động,
cấu trúc code, và cách đo FPS.
