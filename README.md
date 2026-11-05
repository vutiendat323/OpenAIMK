# Trend Coffee Agent

Nền tảng phục vụ khách bằng tiếng Việt: tư vấn có nguồn, thực đơn, bản tạm tính, yêu cầu đặt món, hỗ trợ, bộ nhớ đồng ý lưu và tiến độ. HTTP và MCP dùng chung quy tắc nghiệp vụ.

**Phạm vi hiện tại:** launcher kiosk bật kết nối API khách của `trendcoffee.net`: khách gọi rõ món và cách nhận là gửi đơn một lần, hiển thị QR ngay trong trang; không có popup hay lượt xác nhận thứ hai. Thanh toán cập nhật từ trạng thái merchant. Chạy `serve` trực tiếp mặc định vẫn là hàng đợi nội bộ; đặt `TREND_MERCHANT_ENABLED=1` để bật kết nối. Chưa gửi tin ngoài ứng dụng cho khách.

## Chạy nhanh

Cần Python 3.12+, [uv](https://docs.astral.sh/uv/) và `curl` nếu cập nhật menu từ nguồn công khai.

```bash
uv sync --locked
uv run trendcoffee init
uv run trendcoffee serve
```

Mở **http://127.0.0.1:8080/** để dùng kiosk React: lọc/tìm món, xem ảnh và chi tiết, chỉnh giỏ, bấm **Thanh toán** để nhận QR ngay, xem tiến độ; trợ lý giọng nói phục vụ ngay trên kiosk. Chọn cách nhận món rõ ràng; tại bàn cần số bàn. Không có màn duyệt đơn, popup thanh toán hoặc hộp thoại kết quả. QR xuất hiện sau khi merchant trả đúng đơn và số tiền; khách tự xác nhận giao dịch trong app ngân hàng.

Nhân viên mở **http://127.0.0.1:8080/staff.html**. Đặt `TREND_STAFF_TOKEN` bằng một giá trị ngẫu nhiên dài trước khi chạy server để bật quyền nhân viên; mã chỉ nhập tại console nhân viên. Cấu hình qua biến môi trường; `.env.example` chỉ là ví dụ, không tự nạp. Giữ host mặc định `127.0.0.1` cho dùng thử.

## Frontend kiosk

Stack: **React + TypeScript + Vite + Tailwind CSS + shadcn/ui (Radix)**. Mã nguồn trong `frontend/src/`; ảnh thật được tối ưu WebP và font tiếng Việt được phục vụ tại chỗ. Giao diện hỗ trợ desktop, màn hình dọc và điện thoại. Giá/đơn vẫn do FastAPI kiểm tra.

Cần Node.js 22.12+ khi phát triển hoặc build giao diện:

```bash
cd frontend
npm ci
npm run dev          # Vite :5173, proxy API sang FastAPI :8080
npm run test
npm run lint
npm run format:check
npm run build        # xuất vào trendcoffee/static, giữ console nhân viên
```

Khởi chạy FastAPI ở terminal khác. Build đã được lưu trong package; người chạy wheel không cần Node. Hướng dẫn ảnh và cấu trúc frontend: [frontend/README.md](frontend/README.md).

Kiosk dùng phiên khách chỉ trong bộ nhớ trình duyệt. Nút **Khách tiếp theo** xóa giỏ, hội thoại và quyền truy cập phiên trên màn hình, tạo khách mới; không hủy yêu cầu đã gửi. Tự cảnh báo sau 90 giây và kết thúc phiên sau 120 giây không tương tác. Tải lại trang cũng bắt đầu khách mới. Tiến độ cập nhật khi mở hoặc bấm cập nhật.

## Camera → AV Fusion → Codex native voice

```bash
.venv/bin/python scripts/kiosk.py start
.venv/bin/python scripts/kiosk.py status
.venv/bin/python scripts/kiosk.py stop
```

Mở **http://127.0.0.1:8080**, bấm **Bật micro** ở lần cấp quyền đầu tiên. Khi quyền micro đã được cấp, trang tự kết nối lại sau khi tải. Visual ưu tiên camera gắn trực tiếp với server (C920 nếu có); camera trình duyệt/mobile là nguồn dự phòng khi camera server không có hoặc mất khung hình. Micro vẫn lấy từ trình duyệt. Mặc định **Camera tại kiosk** chỉ xin camera trình duyệt khi Visual mất nguồn local; local phục hồi thì dừng camera web, giữ micro. Khi truy cập từ laptop/điện thoại ở nơi khác, chọn **Camera thiết bị này** trước **Bật micro** để cấp cả camera và micro của thiết bị, kể cả khi camera server vẫn hoạt động. Nếu micro đã tự bật, bấm **Tắt micro** trước khi đổi nguồn; việc này kết thúc phiên điều khiển hiện tại. Đổi nguồn trước khi bắt đầu gọi món. Sau khi model warm, đứng trước camera dưới khoảng 0,6 m trong 2 giây để tự mở khách/thread Codex mới và bật voice. Kiosk phát lời chào ngay khi mở phiên và tạm biệt khi kết thúc. Thread dùng `gpt-6-luna`, effort `medium`. Có thể bấm **Bắt đầu nói**; audio vẫn cần Fusion xác minh người nói. Ví dụ nói “Cho mình một trà vải đào mang đi”: trợ lý tìm món, gửi đơn và hiện QR ngay trên trang. Chỉ hỏi thông tin còn thiếu, không yêu cầu đọc lại câu xác nhận hay chọn phương thức thanh toán.

Launcher cũng bật **LiveTalking local** ở cổng 8010: clip `Female_staff_member_standing_3128c196.mp4`
làm nguồn đứng chờ/nói và clip vẫy tay riêng. Khi bắt đầu/dừng nói, chuyển động đầu tiếp tục;
lip-sync giữ vùng mắt gốc và chỉ ghép phần mặt bên dưới.
Mở `http://127.0.0.1:8080`, tải lại trang và chọn **Bật micro**. Theo dõi model bằng
`curl http://127.0.0.1:8080/api/avatar/status` (`ready: true`). Hướng dẫn và giới hạn asset:
[Realtime avatar](docs/workflows/realtime-avatar.md). Trong **Cài đặt**, khi micro đã bật,
có thể chọn **Vẫy tay**, **Mỉm cười**, hoặc **Đứng chờ**.

Micro → Sortformer/TitaNet/TSE kết hợp SCRFD/ByteTrack/MiniFASNet/Light-ASD/face embedder/đọc môi/YOLO/Metric3D → PCM được Fusion chấp nhận → native voice Codex. Cầu WebRTC chạy **ở backend**, dùng đăng nhập ChatGPT của CLI; trình duyệt chỉ nối cùng cổng kiosk. Mặc định launcher bật merchant checkout và hiển thị QR do Trend Coffee trả về. Dùng `TREND_MERCHANT_ENABLED=0 .venv/bin/python scripts/kiosk.py start` cho chế độ chỉ lưu nội bộ.

TREND trả lời khoảng 20–30 từ, ngắn hơn khi đủ ý; chỉ nhắc tối đa hai món, không đọc lại cả menu/đơn hoặc dẫn chuyện trước khi gọi công cụ. Chi tiết đầy đủ vẫn hiển thị trên màn hình và mọi món khách gọi vẫn được xử lý.

Giỏ hàng là cột nhỏ bên phải, hiển thị ảnh, tên, đơn giá và bộ đếm; tổng tiền/nút thanh toán ở đáy. Chạm ảnh hoặc tên món để mở ghi chú riêng; chọn “Ghi chú cho đơn” dưới tiêu đề để nhập lời nhắn chung, hoặc nói với TREND. Hai ly cùng món có ghi chú khác nhau được giữ riêng. API/MCP nhận `lines[].note` (tối đa 300 ký tự) và `order_note` (tối đa 1000 ký tự); cả hai được gửi kèm sang merchant và ràng buộc vào khóa chống gửi trùng. Ghi chú được xóa cùng giỏ/phiên đã kết thúc. Vùng QR mở rộng để mã dễ quét; màn hình ngang thấp cho phép cuộn giỏ. Luồng phát giọng native và AudioContext của trình duyệt dùng cùng **48 kHz**, tránh nhiễu do đổi mẫu riêng ở từng gói âm thanh.

Máy khác dùng tunnel, chọn cổng local trống:

```bash
ssh -N -F /dev/null -o ExitOnForwardFailure=yes -L 18080:127.0.0.1:8080 metek@100.107.85.116
```

Giữ terminal SSH mở, truy cập **http://127.0.0.1:18080** trên máy đó. Không cần forward 9877. Hướng dẫn model, ranh giới phiên và kiểm thử: [kiosk voice workflow](docs/workflows/kiosk-voice.md).

## Chọn giọng nói trên web

Ô **Giọng nói** trong khung trợ lý lấy danh sách trực tiếp từ Codex đang cài,
đúng giao thức voice v3. Hiện có 23 giọng khả dụng với đủ lời chào/tạm biệt;
**Mặc định Codex** giữ cấu hình mặc định.
Trình duyệt chưa lưu lựa chọn sẽ chọn **Maple**.
Lựa chọn được nhớ trên trình duyệt cho địa chỉ kiosk đang mở. Có thể đổi khi micro
đang bật: nếu đang có khách, giọng mới áp dụng từ phiên tiếp theo, giữ cuộc trò
chuyện và giỏ hàng hiện tại. Không cần mở terminal để chọn giọng.

Codex trả tên giọng, không trả nhãn giới tính; giao diện giữ nguyên tên thay vì
gán nhãn nam/nữ chưa xác nhận. Lời chào, hội thoại và tạm biệt dùng cùng giọng
đã chọn cho phiên. Nếu đổi giọng khi đang trò chuyện, lời tạm biệt vẫn giữ giọng
của phiên hiện tại; khách tiếp theo dùng giọng mới từ lời chào.
[Danh sách](docs/evals/codex-voice-settings.md) và
[kiểm thử đồng nhất giọng](docs/evals/consistent-kiosk-voice.md).
Porto và Selva có tên trong catalog CLI nhưng dịch vụ hiện từ chối quyền truy cập,
nên không hiển thị hai lựa chọn này.

## Thành phần

| Thành phần | Nơi triển khai |
|---|---|
| Skill phục vụ khách | [.agents/skills/trendcoffee-service/SKILL.md](.agents/skills/trendcoffee-service/SKILL.md) |
| Workflow và trách nhiệm nhân viên | [docs/workflows/customer-service.md](docs/workflows/customer-service.md) |
| RAG có nguồn | SQLite FTS5, chuẩn hóa dấu tiếng Việt; `trendcoffee/service.py` |
| Bộ nhớ | Draft hội thoại 15 phút; sở thích đồng ý lưu tối đa 30 ngày, tách biệt từng guest |
| Progress | Sự kiện đơn/hỗ trợ bền vững; `/api/progress` |
| MCP | 14 tools + resource workflow; `trendcoffee/mcp_server.py` |
| In hóa đơn | PDF chính thức của merchant → CUPS `GP-C180I`; [vận hành máy in](docs/workflows/invoice-printing.md) |
| Tri thức công khai | [data/trendcoffee-public.json](data/trendcoffee-public.json) |
| Tiến độ triển khai | [docs/PROGRESS.md](docs/PROGRESS.md) |

## Nguồn và cập nhật RAG

Bản nhập ngày 16/10/2026 có **51 món/biến thể** tại Chi nhánh 1 và **13 đoạn kiến thức** từ website/API công khai. Giá niêm yết 35.000–65.000đ. Không dùng dữ liệu sản phẩm quản trị chưa được phân vào menu; không đoán đường/đá hoặc tồn món. Địa chỉ công bố có khác biệt tên phường; giờ hotline là giờ hỗ trợ, chưa xác minh giờ mở cửa. [Biên bản nguồn](docs/research/trendcoffee-public-sources.md).

```bash
# Đọc menu công khai ngày hiện tại theo múi giờ Việt Nam; không ghi lên website.
uv run trendcoffee sync-public
# Nhập tài liệu đã kiểm chứng do người vận hành duyệt.
uv run trendcoffee import --bundle data/trendcoffee-public.json
```

Menu và tri thức tóm tắt menu hết hạn sau 24 giờ; tri thức chính sách/liên hệ có tuổi tối đa 30 ngày kể từ lần kiểm chứng. Menu cũ quá 24 giờ không tạo được bản tạm tính mới. `sync-public` cập nhật menu, danh mục từ `/api/latest/catalogs` và đoạn tri thức tóm tắt thực đơn trong cùng giao dịch, không tự thay đổi chính sách; kiểm chứng và nhập lại các đoạn chính sách khi nguồn đổi. Thanh danh mục giữ tên, thứ tự và ID của merchant; “Bán chạy”/“Món mới” lọc bằng cờ `isTopSell`/`isNew`, không tự suy đoán từ tên món. Danh mục rỗng không bổ sung món ngoài thực đơn công khai. Snapshot không bảo đảm tồn món. Tổng tiền là tạm tính theo giá niêm yết, chưa chốt phí/ưu đãi; nhân viên đối soát trước khi tiếp nhận.

Máy kiosk dùng systemd user timer để đồng bộ menu mỗi 6 giờ, lúc **00:00, 06:00, 12:00 và 18:00 theo giờ Việt Nam**. Timer chạy bù sau khi máy bật lại nếu bỏ lỡ lịch. Bản cấu hình nằm trong `scripts/systemd/`, dùng workspace `~/Projects/OpenAIMK` và DB `.runtime/trendcoffee.db`; chỉnh đường dẫn nếu cài ở nơi khác.

```bash
install -Dm644 scripts/systemd/trendcoffee-menu-sync.service ~/.config/systemd/user/trendcoffee-menu-sync.service
install -Dm644 scripts/systemd/trendcoffee-menu-sync.timer ~/.config/systemd/user/trendcoffee-menu-sync.timer
systemctl --user daemon-reload
systemctl --user enable --now trendcoffee-menu-sync.timer
# Đồng bộ ngay, không cần khởi động lại API.
systemctl --user start trendcoffee-menu-sync.service
systemctl --user list-timers trendcoffee-menu-sync.timer
journalctl --user -u trendcoffee-menu-sync.service -n 20 --no-pager
```

Máy kiosk không có phiên đăng nhập thường trực cần bật `loginctl enable-linger "$USER"` để user timer tiếp tục chạy khi đăng xuất. Nếu nguồn công khai lỗi, lần đồng bộ báo thất bại và giữ nguyên menu đã kiểm chứng; lần kế tiếp chạy theo lịch. Trang kiosk đang hiển thị menu cũ cần tải lại để lấy dữ liệu mới.

## MCP

Chạy stdio: `uv run trendcoffee mcp`. Đã có cấu hình Codex theo project tại [.codex/config.toml](.codex/config.toml); host cần tải lại project/phiên để nhận server. Cấu hình project chỉ có hiệu lực khi project được host tin cậy, theo [tài liệu MCP chính thức](https://learn.chatgpt.com/docs/extend/mcp?surface=cli). File [mcp.example.json](mcp.example.json) cung cấp cấu hình host; thay đường dẫn nếu clone ở nơi khác. Không có log ứng dụng trên stdout. Kết nối một host sẽ khởi động một tiến trình dùng chung DB chỉ định.

Tools: `create_guest_session`, `search_knowledge`, `get_menu`, `get_tables`, `get_preferences`, `remember_preference`, `forget_preferences`, `checkout_order`, `draft_order`, `submit_request`, `get_progress`, `get_payment`, `print_invoice`, `get_invoice_status`, `request_handoff`. `get_tables()` đọc tình trạng bàn live từ merchant; có thể truyền `table_label` để hỏi một bàn. Chọn `at_table` mà chưa chỉ định bàn sẽ tự lấy bàn `available` đầu tiên theo danh sách merchant; lựa chọn này không phải đặt giữ chỗ. `get_menu` nhận `queries=["cà phê muối", "cà phê sữa", "trà bắc"]`; truyền tất cả dòng và cách nhận vào một `checkout_order` với `checkout_id` cố định cho những lần thử lại cùng đơn. `get_payment` lấy QR/trạng thái của đơn thuộc phiên khách. Hai tool hóa đơn đọc/xếp lịch bản in chính thức, không xác nhận thanh toán hoặc in lại. Capability guest là bí mật, dùng riêng cho cùng khách; không in token vào log hoặc câu trả lời.

Gợi ý theo ý khách dùng suy luận trên **toàn menu**: phiên native nhận đủ tên, mô tả, nhóm món, giá và ID ngay khi mở. Với “trái cây”, model chọn món phù hợp từ dữ liệu rồi gọi `kiosk_menu(item_ids=[...])` để hiển thị, không phụ thuộc chữ “trái cây” có trong tên. Giới hạn giá và các lựa chọn khách tránh cũng được cân nhắc. Gợi ý không tự tạo giỏ/đơn. MCP dùng `get_menu()` để đọc toàn menu, rồi `get_menu(item_ids=[...])` để xác minh món đã chọn.

Tìm tên món vẫn chịu được lỗi nhận giọng nói: `resolved_item_ids` là tên khớp rõ, `suggestions` là tối đa ba món thật gần đúng cần hỏi ngắn trước khi thêm. Kết quả chưa rõ kèm `catalog` và `requires_catalog_review` để model xem lại toàn menu, không kết luận thiếu món từ một chuỗi không khớp. Giao diện dùng ID kết quả từ backend để hiện đúng món dù chuỗi khách nói khác tên.

Resource: `trendcoffee://workflow`. Skill được đặt tại `.agents/skills` để agent tương thích tự khám phá; các host khác có thể dùng file cấu hình ví dụ. Không sửa cấu hình toàn cục của máy.

## Model tùy chọn và độ trễ

Lõi chạy không cần API key và không gọi model cho các luồng thông thường. Nếu đặt cả `OPENAI_API_KEY` và `TREND_OPENAI_MODEL`, server có thể dùng OpenAI Responses để chọn ID đoạn kiến thức cho câu hỏi chưa khớp. Model chỉ chọn trong dữ liệu đã duyệt; câu trả lời lấy nguyên văn từ dữ liệu, không được tính tiền hoặc cập nhật giao dịch. Timeout toàn lượt là 4 giây, không tự retry; lỗi trả về câu trả lời địa phương trung thực. Chưa đo gọi model trực tiếp vì không cấu hình credential.

```bash
uv run trendcoffee benchmark --requests 300
uv run pytest -q
uv run ruff check trendcoffee tests
uv run ruff format --check trendcoffee tests
uv build
```

[Kết quả benchmark](docs/evals/latency.json) ghi p50/p95/p99, số mẫu, số phiên đồng thời và lỗi. Mục tiêu nội bộ p95 <250ms; kết quả là HTTP trong tiến trình, chưa gồm mạng, trình duyệt, model hay POS. Không dùng số này làm SLA khách hàng ngoài thực tế.

## Lưu trữ và triển khai

SQLite mặc định `.runtime/trendcoffee.db`; đổi bằng `--db` hoặc `TREND_DB`. WAL hỗ trợ nhiều kết nối trên một máy. Phiên guest có hạn 30 ngày; dữ liệu hết hạn được dọn khi tạo phiên mới. Xóa sở thích có hiệu lực ngay; không xóa lịch sử đơn đang xử lý. Không lưu toàn bộ hội thoại. Backup DB bằng SQLite backup API hoặc dừng tiến trình trước khi sao chép để giữ nhất quán WAL.

Trước khi mở cho khách thật: cần kiểm thử đơn được cho phép và quét QR từ đầu đến cuối trên hệ thống merchant, xác minh phí/ưu đãi, cấu hình HTTPS, danh tính khách/nhân viên, giới hạn lưu lượng/body tại gateway và quy trình dữ liệu của quán. Adapter hiện dùng API checkout công khai của ứng dụng merchant; chưa có SLA production hoặc triển khai nhiều máy. Xem [luồng merchant và giới hạn kiểm thử](docs/workflows/merchant-checkout.md). Các yêu cầu/đơn test chỉ nằm trong DB riêng của phép kiểm tra; benchmark không tạo lưu lượng lên website quán.
