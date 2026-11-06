# Độ trễ giỏ hàng, đặt đơn và thanh toán — 2026-11-06

## Kết luận

Độ trễ quan sát được đến từ nhiều bước chờ nối tiếp: mô hình chọn hành động,
tool đặt đơn chờ POS, mô hình soạn kết quả, rồi lớp giọng nói phát kết quả.
Một checkout đang chờ còn giữ khóa chung, khiến thao tác giỏ hàng phải xếp hàng.
Truy vấn cấp số thẻ không giải thích được độ trễ hàng giây ở quy mô dữ liệu hiện tại.

Điều tra này xác nhận các cơ chế gây chậm và đo được chi phí tổng của tool.
Log hiện tại chưa tách thời gian chờ khóa, hàng đợi executor, kết nối mạng và từng
endpoint POS, nên chưa thể quy toàn bộ một lượt checkout 10 giây cho một endpoint cụ thể.

Phạm vi: đọc source hiện tại; phát lại log khách ngày **5/11**; chạy backend thật với
SQLite tạm và POS giả lập. Chưa có log khách ngày 6/11 trong nguồn đã kiểm tra để đo
luồng mới sau thay đổi thẻ rung. Không tạo đơn thật, chuyển tiền, in giấy hoặc restart.

## Số đo từ log

Đọc 24 phiên có bản ghi lời nói khách. Loại một lượt có yêu cầu mới chen vào khi
lượt trước còn chạy, vì không thể dùng chung một mốc bắt đầu.

Mốc bắt đầu là lúc yêu cầu được giao cho Codex; mốc kết thúc là lúc có câu trả lời
văn bản. Các số này **không phải** thời gian từ âm thanh cuối của khách đến loa phát.
Khoảng tool bao gồm vận chuyển Code Mode, thời gian chờ và thực thi backend.

| Luồng | Mẫu | Tool: trung vị | Từ giao yêu cầu đến trả lời văn bản: trung vị |
|---|---:|---:|---:|
| Có gọi `kiosk_checkout` | 26 lượt | 2,882 s | 8,356 s |
| Chỉ một `kiosk_checkout` | 22 lượt | Xem nhóm checkout phía trên | 7,790 s |
| `kiosk_payment` | 3 lượt không chồng lấn | 0,270 s | 4,306 s |
| `kiosk_menu` | 24 lần gọi trong 21 lượt | 0,042 s | 6,514 s, có lượt kèm checkout |

Checkout chậm nhất trong mẫu: tool 10,451 s; toàn lượt 17,468 s.
Trong 22 lượt chỉ gọi checkout, tổng hai khoảng trước tool và sau tool có trung vị
**4,510 s**. Vì vậy, chỉ làm backend nhanh hơn vẫn còn phần chờ mô hình đáng kể.

Chỉ có một lần `kiosk_cart` độc lập trong mẫu này, dùng để xem giỏ trống; không dùng
nó để suy ra độ trễ thêm vào giỏ hàng thực tế. Thao tác thêm vào giỏ được đo riêng bằng fixture.

## Những nguyên nhân và cơ chế đã kiểm tra

### 1. Nhiều lượt xử lý của mô hình

Một ví dụ lúc 17:11 ngày 5/11 có:

```text
Giao yêu cầu → chọn tool:       3,168 s
Chạy kiosk_checkout:           2,707 s
Tool trả về → trả lời văn bản:  1,921 s
Tổng:                          7,796 s
```

22/26 lượt checkout đã dùng một tool. Bốn lượt còn lại có thêm tìm menu; tổng khoảng
chờ giữa các lần gọi tool có trung vị 3,335 s trong bốn lượt đó. Chưa thể coi mọi lần
tìm thêm là thừa: một số yêu cầu cần làm rõ món. Tuy nhiên, chỉ dẫn hiện tại vừa cho
phép dùng ID trong catalog trực tiếp, vừa yêu cầu luôn tìm từng món khi khách nêu
nhiều món: [codex_voice.py](../../trendcoffee/codex_voice.py), dòng 43–49 và 77–80.
Đây là điểm chỉ dẫn cần làm nhất quán; mức cải thiện từ sửa prompt chưa được đo.

Realtime còn phải giao yêu cầu sang Codex và phát câu trả lời sau đó. Chỉ dẫn nói
một lời đáp ngắn trước khi giao việc nằm ở dòng 176; log cho thấy lời đáp và tool có
thể chồng thời gian, nên không cộng toàn bộ thời lượng lời đáp vào độ trễ tool.

### 2. Checkout chờ nhiều yêu cầu POS nối tiếp

Fixture chạy code thật trong `InteractionHost` → `Service` → `MerchantClient`.
POS giả lập trả response đơn khách không có `branch`; QR là URL ảnh thuộc miền
được cho phép. Chuỗi yêu cầu quan sát được:

| Tình huống | Các bước checkout | Số yêu cầu |
|---|---|---:|
| Mang đi, QR có sẵn | tạo đơn → đọc đơn → tải ảnh QR | 3 |
| Mang đi, cần khởi tạo thanh toán | tạo đơn → đọc đơn → khởi tạo → đọc đơn → tải ảnh QR | 5 |
| Ăn tại bàn, tự chọn bàn, QR có sẵn | đọc bàn → đọc bàn → tạo đơn → đọc đơn → tải ảnh QR | 5 |
| Ăn tại bàn, cần khởi tạo thanh toán | đọc bàn → đọc bàn → tạo đơn → đọc đơn → khởi tạo → đọc đơn → tải ảnh QR | 7 |

Nếu merchant trả QR dạng data URI thì bỏ bước tải ảnh. Những request này được
**đếm bằng fixture**, không phải số lần gọi mạng đã truy vết cho từng đơn thật.

Hai lần đọc bàn nằm ở `kiosk_fulfillment` chọn bàn và `MerchantClient.create`
đổi số bàn thành ID. `Service._send_merchant` đọc lại đơn nếu thiếu `branch`,
dù validator có hỗ trợ đơn khách không có trường này.
Nguồn: [kiosk.py](../../trendcoffee/kiosk.py), dòng 1560–1585;
[service.py](../../trendcoffee/service.py), dòng 544–566;
[merchant.py](../../trendcoffee/merchant.py), dòng 155–162.

`MerchantClient._request` và `_image` tạo rồi đóng `httpx.Client` mỗi lần; các
request nối tiếp không dùng chung connection pool. Điều này tạo cơ hội tối ưu kết
nối, nhưng chưa có số đo DNS/TCP/TLS riêng để định lượng phần tiết kiệm.

### 3. Một checkout chậm chặn cả thao tác giỏ hàng

Cả tool giọng nói và lệnh chạm dùng `InteractionHost.lock`, giữ khóa trong lúc chờ
checkout/POS. Nguồn: [kiosk.py](../../trendcoffee/kiosk.py), dòng 979–1012 và 1718–1723.

Fixture giữ POST tạo đơn trong **150 ms**, rồi gửi lệnh giỏ hàng qua `host.command`:
lệnh giỏ bị chặn, hoàn tất sau **152,371 ms**. Đây là bằng chứng trực tiếp cho việc
độ trễ checkout có thể lan sang thao tác giỏ, dù bản thân thao tác giỏ rất nhanh.
Không suy ra rằng khóa đã gây ra mọi lần khách báo chậm khi thêm món.

Khi phiên kiosk hoạt động, frontend gửi thay đổi giỏ về server và chờ trạng thái
trả về thay vì cập nhật giỏ cục bộ ngay: [App.tsx](../../frontend/src/App.tsx), dòng 190–210.

### 4. Kiểm tra thanh toán có các bước chờ riêng

`PaymentQr` đợi 3 giây **sau khi request trước hoàn tất** rồi đọc lại. Một lần đọc
thanh toán pending có thể lại tải ảnh QR từ URL. Do đó chu kỳ là 3 giây cộng thời
gian request, không phải cứ đúng mỗi 3 giây nhận kết quả.
Nguồn: [PaymentQr.tsx](../../frontend/src/components/PaymentQr.tsx), dòng 37–71;
[service.py](../../trendcoffee/service.py), dòng 592–641;
[merchant.py](../../trendcoffee/merchant.py), dòng 303–348.

Khi backend đã xác minh paid, thông báo còn tạo lượt Codex mới và yêu cầu gọi lại
`kiosk_payment` trước khi Trend nói. Nếu có tool checkout/payment đang chạy, thông
báo còn chờ tool đó hoàn tất, tối đa 20 giây. Đây là thời gian chờ có điều kiện;
không khẳng định mỗi thông báo đều chờ 20 giây.
Nguồn: [claim_guard.py](../../trendcoffee/claim_guard.py), dòng 216–225;
[kiosk.py](../../trendcoffee/kiosk.py), dòng 2089–2114.

Chưa có mốc ngân hàng xác nhận trong dữ liệu đã đọc để đo toàn bộ thời gian từ
khách chuyển tiền đến Trend thông báo.

### 5. Cấp số thẻ và phần xử lý cục bộ rất nhỏ trong phép đo này

30 lần chạy với SQLite tạm, không POS mạng, không worker in:

| Bước | Trung vị |
|---|---:|
| Thêm một món vào giỏ qua host | 0,638 ms |
| Checkout nội bộ | 0,977 ms |
| Đọc thanh toán nội bộ | 0,943 ms |

Truy vấn `_next_card` trên DB thật ở chế độ **chỉ đọc**, 317 đơn, 300 lần:
trung vị **0,565 ms**, cao nhất 1,234 ms. Đây không phải phép đo tranh chấp writer
và không dự báo hiệu năng khi DB lớn hơn nhiều.

In hóa đơn/raster chữ có dấu chạy trong worker sau khi có bằng chứng thanh toán,
không phải bước checkout phải chờ để nhận QR. Chưa có bằng chứng cho thấy việc
in header thẻ rung gây độ trễ đặt đơn đang được báo.

## MCP và chỉ dẫn: phân biệt hai đường gọi

Kiosk giọng nói dùng dynamic kiosk tools qua app-server/Code Mode. Nó tắt inherited
MCP servers trong `CodexVoice.argv` (dòng 243–255). Các số đo trên không chứng minh
MCP stdio chậm; không nên gộp mọi độ trễ tool thành độ trễ MCP.

Đường MCP riêng gọi cùng `Service`, nên có cùng chuỗi chờ POS, nhưng chưa được đo
end-to-end trong điều tra này. Có các chỉ dẫn cũ dễ dẫn đến thêm bước:

- `get_menu` còn hướng sang `draft_order` dù chỉ dẫn server đã cho phép `checkout_order` trực tiếp.
- Resource `trendcoffee://workflow` nói checkout trả QR, sau đó lại hướng đọc `get_payment`.

Nguồn: [mcp_server.py](../../trendcoffee/mcp_server.py), dòng 42–53 và 150–165.
Đây là rủi ro workflow thấy trong source, chưa có trace MCP chứng minh tần suất.

## Hướng sửa theo bằng chứng

1. Làm nhất quán đường đặt đơn một lần trong cả prompt kiosk và MCP. Bỏ tìm lại món
   khi ID/options đã rõ và catalog còn mới; giữ bước làm rõ khi món thực sự mơ hồ.
2. Giảm round trip POS: dùng lại kết nối; dùng cùng dữ liệu bàn trong một checkout;
   xem xét bỏ GET chỉ vì thiếu `branch` khi response đã đủ dữ liệu và đã qua validator.
   Giữ kiểm tra đơn, giá và chống tạo trùng.
3. Tách chờ mạng khỏi khóa giỏ bằng thiết kế giữ snapshot/revision và chống kết quả
   cũ. Không bỏ khóa đơn giản vì có thể làm sai giỏ hoặc tạo trùng đơn.
4. Giữ kiểm tra paid mới từ merchant, nhưng tránh tải lại QR không đổi và tránh đọc
   paid lần nữa chỉ để phát thông báo khi đã có kết quả xác minh phù hợp.
5. Bổ sung mốc `lock_wait`, executor wait, DB, tables, create, fetch, initiate, QR image,
   tool result, first output audio và browser playout. Hiện `Server-Timing` chỉ đo tổng HTTP;
   thiếu breakdown cho dynamic tools và merchant calls. Log chỉ thời gian, stage và mã tương quan;
   không ghi token, QR, payload đơn hoặc lời khách.

Chưa sửa hoặc triển khai những hướng này trong lượt điều tra.

## Tái lập và kiểm chứng

Artifacts nằm trong `output/order-latency-2026-11-06/`:

- `analyze_rollouts.py`: chỉ đọc log, xuất tool/timing; không chép lời khách hay token.
- `rollout-timings.json`: số đo từng lượt và thống kê.
- `probe_backend.py`: DB tạm, HTTP mock, fixture khóa; không khởi động server/worker.
- `backend-probe.json`: số đo backend và chuỗi request của fixture.

```sh
.venv/bin/python output/order-latency-2026-11-06/analyze_rollouts.py --output output/order-latency-2026-11-06/rollout-timings.json --max-final-seconds 5
.venv/bin/python output/order-latency-2026-11-06/probe_backend.py
.venv/bin/ruff check output/order-latency-2026-11-06/analyze_rollouts.py output/order-latency-2026-11-06/probe_backend.py
```

Lệnh đầu trả exit 1: `SLOW: checkout median 8.356s exceeds diagnostic budget 5.0s`.
5 giây là ngưỡng kiểm tra chẩn đoán, không phải SLA đã thống nhất. Replay log cũ
luôn cho số cũ; muốn đánh giá bản sửa phải chạy trên trace mới. Lệnh probe exit 0,
fixture khóa được xác nhận; Ruff sạch. Không chạy full suite vì không sửa ứng dụng.

Sandbox khiến `asyncio.run` treo khi đóng thread executor ngay cả với phép thử tối
thiểu; probe backend được chạy ngoài sandbox sau khi được cho phép. Không coi lỗi
môi trường chẩn đoán này là nguyên nhân gây chậm kiosk đang chạy.

Log transcript xuất hiện khi một đoạn lời nói hoàn tất; khoảng văn bản → transcript
có chứa thời lượng nói, không được gọi là độ trễ trước khi bắt đầu nói. Các con số
5,3 giây trong ghi chép cũ đã được sửa cách diễn giải tại PROGRESS ngày 4/11.

## Tự đánh giá bằng agent-self-evaluation

| Trục | Điểm / 5 | Bằng chứng và giới hạn |
|---|---:|---|
| Chính xác | 4 | Đối chiếu trace, fixture chuỗi POS và khóa; chưa đo từng endpoint thật. |
| Đầy đủ | 4 | Bao phủ giỏ, checkout, payment, thẻ, prompt và hai đường tool; thiếu trace MCP end-to-end mới. |
| Rõ ràng | 4 | Tách ms cục bộ, giây toàn lượt và thời điểm transcript; báo cáo dài để giữ bằng chứng. |
| Có thể hành động | 4 | Có hai script chạy lại và các hướng sửa cụ thể; cần telemetry mới cho outlier POS. |
| Ngắn gọn | 4 | Kết luận và bảng số đo ở đầu; chi tiết tái lập nằm cuối. |

Trung bình: **4,0/5**. Ưu tiên tiếp: đo từng stage POS, đo first-audio/loa, rồi so
sánh workflow trước/sau trên cùng fixture và trace mới. Người dùng có thể kiểm tra
các kết luận trực tiếp bằng script; các khoảng chưa đo được đều được nêu rõ.
