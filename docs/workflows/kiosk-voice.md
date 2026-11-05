# Kiosk camera, Fusion và Codex voice

## Chạy tại OpenAIMK

Chạy từ `/home/metek/Projects/OpenAIMK`. Không chỉnh sửa hoặc chạy launcher của `/home/metek/Projects/jarvis`. Giữ nguyên `AGENTS.md`.

```bash
uv sync --group dev
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/python scripts/kiosk.py start
.venv/bin/python scripts/kiosk.py status
# Sau khi sửa backend:
.venv/bin/python scripts/kiosk.py stop --service api
.venv/bin/python scripts/kiosk.py start --service api
```

API/UI ở loopback 8080; Visual riêng ở loopback 9877. Launcher kiểm tra cwd, command và thời điểm khởi động PID trước khi dừng tiến trình. Model warm-up chạy nền, log trong `.runtime/kiosk-api.log`, `kiosk-visual.log`, `av-worker.log`. Launcher không dừng dịch vụ chiếm cổng ngoài quyền quản lý.

Trình duyệt cần localhost hoặc HTTPS để cấp camera/micro. Với SSH, forward local 18080 sang remote 8080 rồi mở `http://127.0.0.1:18080`. Người vận hành cấp quyền micro một lần qua nút **Bật micro**. Khi đã có quyền, trang tự kết nối; AudioContext đang chờ tương tác không ngăn camera local mở phiên. **Tắt micro** dừng các track của trình duyệt và ngắt phiên điều khiển; camera server do Visual quản lý vẫn chạy. Khi còn kết nối, hết phiên khách giữ camera để phát hiện khách tiếp theo.

## Môi trường model

Bản sao `Visual/.venv` đã được kiểm tra với Python 3.12, Torch 2.14.0/CUDA, NeMo 3.0.0, websockets 17.x và tomlkit 0.15.x. Không chạy entrypoint/shebang từ virtualenv sao chép khi chúng còn trỏ về jarvis. Worker đặt PYTHONPATH vào `OpenAIMK/Audio/src` và xác minh nguồn import.

Nếu cần môi trường mới, tạo **bên trong workspace**:

```bash
uv venv .runtime/av-venv --python 3.12
uv pip install --python .runtime/av-venv/bin/python -r Visual/requirements.txt -r Visual/requirements-asd.txt -e './Audio[nemo,vision,toml]'
TREND_AV_PYTHON="$PWD/.runtime/av-venv/bin/python" .venv/bin/python scripts/kiosk.py start
```

Cần model SCRFD, face embedder, face landmarks, YOLO và PAD weights trong bản sao Visual; checkout `Metric3D/` cạnh `Visual/`. Light-ASD ONNX cùng manifest và TSE TorchScript nằm ở `.runtime/models/`. Sortformer/TitaNet và checkpoint depth được cache trong `.runtime/huggingface` / `.runtime/torch`. Không tự bỏ qua model thiếu; Visual từ chối khởi động nếu model yêu cầu không tải được. Không đưa weights/venv/runtime vào package nguồn.

## Luồng và quyền sở hữu

1. Ở chế độ mặc định **Camera tại kiosk**, Visual mở camera local của server làm nguồn chính, ưu tiên thiết bị C920 theo đường dẫn ổn định. Có thể chỉ định `VISION_CAMERA_PATH` hoặc `VISION_CAMERA_INDEX`. Camera browser/mobile gửi qua WebRTC tới 30 fps (từ 2026-11-05, như C920; đường JPEG 640×480 qua socket khi WebRTC chưa nối vẫn khoảng 15 fps) làm nguồn dự phòng: chỉ được chọn khi không còn frame local mới trong 0,5 giây và luồng browser đã ổn định. Camera local có lại frame thì được ưu tiên ngay; thử mở lại mỗi 2 giây khi mất thiết bị. Không trộn frame hai nguồn. Trình duyệt vẫn lấy micro; mở micro riêng ngay từ đầu. Chỉ khi Visual báo nguồn local mất tín hiệu mới xin camera trình duyệt; local phục hồi thì dừng track video web mà giữ micro. Visual theo dõi người, liveness, miệng và độ sâu. Event mang timestamp/sequence của **frame đã xử lý**, không lấy frame camera mới để làm mới kết quả cũ. PAD hết hạn sau 1,5 giây.
   Khi khách dùng laptop/điện thoại ở nơi khác, chọn **Camera thiết bị này** trước khi bật micro. Trình duyệt xin camera trước của thiết bị cùng micro trong một lần cấp quyền; lựa chọn được gửi qua socket điều khiển đã xác thực và chỉ ghi đè ưu tiên local cho luồng video thuộc chủ phiên đó. Telemetry local_camera_available=true vẫn mô tả camera server, không ngăn camera thiết bị. Luồng thiết bị mất tín hiệu hoặc ngắt kết nối thì quay về camera server; camera server tiếp tục được đọc. Muốn đổi nguồn khi micro đã bật, tắt micro trước khi bắt đầu phiên gọi món mới. SSH forward đúng cú pháp: ssh -N -L 8080:127.0.0.1:8080 user@server, rồi mở http://127.0.0.1:8080 trên laptop; tunnel không thay thế lựa chọn nguồn camera.

2. Presence mới liên tục dưới 0,6 m trong 2 giây hoặc thao tác bắt đầu thủ công tạo guest capability và mở thread Codex riêng. Khi idle chỉ làm nóng các model local; không chuẩn bị thread/cuộc gọi native. Theo dõi chính chủ phiên; người đứng cạnh không giữ phiên cũ. Rời vị trí 3 giây hoặc mất evidence sẽ kết thúc sau grace có giới hạn. Khoảng cách camera chưa hiệu chuẩn là ước lượng. Lời chào bản ghi native chỉ phát sau khi Fusion và voice sẵn sàng; nếu kết nối thất bại thì chưa phát lời chào, và khi kết nối lại không phát lặp trong cùng phiên.
3. PCM16 mono 16 kHz, gói 80 ms → `Audio.SpeakerStream`: Sortformer, TitaNet, TSE và `VisionAudioBridge`. Raw-level VAD chỉ phục vụ bookkeeping; native VAD thấy audio sau lọc. Fusion xác định speaker bằng Light-ASD và voiceprint. Lúc chưa khóa người nói, evidence cũ hoặc tách overlap thất bại, upstream chỉ nhận silence. Không có đường micro browser gửi thẳng sang native voice.
4. Backend WebRTC đưa PCM được chấp nhận vào voice native của `codex app-server`. CLI 0.163.0 đã kết nối bằng ChatGPT login; native WebSocket đã trả lỗi yêu cầu API key nên không dùng làm đường mặc định. Không tự thay thế bằng STT/LLM/TTS khác, không chuyển credentials tới browser.
5. Native voice giao việc cho Codex; scoped tools cập nhật giỏ/fulfillment/quote/view. Code Mode host cần bật để model gọi dynamic tools; shell, apps, plugins, web search, agent khác và MCP kế thừa bị tắt. Thread dùng `gpt-6-luna`, effort `medium`, sandbox read-only, approval never; không tự đổi model khi model yêu cầu không khả dụng. Host vẫn kiểm tra schema, generation, call-id và quyền phiên.
6. RTP đầu ra được giải mã ở backend. Chế độ Pet (từ 2026-11-03): backend phát lại qua kết nối WebRTC riêng (`trendcoffee/speaker.py`, lệnh socket `speaker_offer`); Chrome phát bằng NetEQ, ngoài luồng JavaScript. Bộ đệm khởi động 100 ms ở backend tự tăng 40 ms sau mỗi lần cạn (tối đa 300 ms). Lời chào/tạm biệt đi cùng track. Khi WebRTC chưa kết nối hoặc ở Avatar 3D, PCM vẫn đi qua WebSocket như cũ. Bắt đầu/dừng phát báo về `bot_started/bot_stopped` của Audio, gồm đuôi echo (WebRTC: backend báo, dừng trễ 150 ms). Mỗi lần đổi guest xóa capture packet dở, queue phát, audio delayed/TSE, face/voice lock và callback cũ. Không flush audio khách trước sang phiên sau.

Lời chào/tạm biệt dùng bản ghi native **PCM16 mono 48 kHz theo từng giọng** trong
`frontend/public/voice/<voice>/`; `default/` được tạo không truyền voice override.
Build sao chép sang `trendcoffee/static/voice/`; backend đọc và cache theo cả câu
và giọng. Chỉ hiển thị giọng native có đủ hai bản ghi. Sự kiện `session`/`ended`
mang câu nói và giọng tương ứng; browser xóa âm thanh phiên cũ trước khi phát.
Giọng được giữ suốt một phiên, kể cả lời tạm biệt khi người dùng đã chọn giọng
khác cho phiên tiếp theo. Tạm biệt không cần giữ quyền gọi tool hoặc chờ model.
Dọn kết nối native cũ chạy nền sau khi thu hồi quyền phiên; shutdown vẫn chờ dọn
xong. Tắt thiết bị hoặc mất kết nối dừng phát ngay.

Khi cập nhật danh sách giọng Codex, chuẩn bị các bản ghi còn thiếu rồi build:

```bash
PYTHONPATH=. .venv/bin/python scripts/prepare_voice_clips.py
npm --prefix frontend run build
```

Lệnh tạo bản ghi dùng thread native v3 riêng, không có business tool, với hai
tệp nguồn cố định ở thư mục `voice/` làm đầu vào tổng hợp; không thu micro thật.
Chỉ lưu đầu ra khi transcript khớp câu cần đọc và audio hợp lệ. `catalog.json`
ghi giọng, transcript và SHA-256 của PCM. Có thể dùng `--voice maple` để chuẩn bị
một giọng, hoặc `--force` để tạo lại. Sau khi build, khởi động lại API khi kiosk
không có khách để nạp bộ ghi mới.
Lệnh trả lỗi nếu giọng nào không chuẩn bị được và ghi lý do vào `unavailable`
trong manifest; các giọng đã tạo đủ vẫn dùng được. Hiện Porto và Selva bị dịch vụ
từ chối quyền truy cập, còn 23 giọng native cùng default đã có đủ hai bản ghi.

Chạm màn hình và voice dùng **một giỏ hàng phía server** khi phiên voice hoạt động. Bản tạm tính mất hiệu lực khi giỏ/fulfillment thay đổi. Xác nhận voice yêu cầu **turn.done** có ID và thời điểm bắt đầu turn được ghi nhận sau bản tạm tính và câu đồng ý hoàn chỉnh; mảnh transcript hoặc câu “đừng xác nhận” không đủ. Nút xác nhận có quyền riêng mà model không thể giả mạo bằng argument. Chỉ lưu yêu cầu `pending_acceptance`, payment `unverified`; lời nói không xác minh tiền.

## Thời gian và giới hạn

Camera **thiết bị này** gửi frame bằng cả timer và nhịp AudioWorklet để tránh chỉ còn 1–2 FPS khi timer tab bị giảm nhịp. Lời chào chờ gói mic thực sự tới API, xác nhận khởi tạo A‑V và kết nối native; mic/camera/A‑V được kiểm tra lại ngay trước khi chào. `/api/kiosk/status` có `microphone_receiving`, `accepted_audio_receiving` và `audio_gate` để phân biệt nhận mic với âm thanh đã được bộ lọc cho qua. Xem [kết quả kiểm tra](../evals/device-camera-av-readiness.md); FPS và nhận diện trên thiết bị thật vẫn cần đo trực tiếp.

- Tối đa 10 phút/khách, cảnh báo phút 9; idle 120 giây tính cả chạm, speech được chấp nhận và playback.
- Diarizer ultra_low xử lý chunk 240 ms; evidence ASD dùng cửa sổ 1 giây. Mask delay 0,7 giây là deadline thiếu evidence của Audio, không phải SLA toàn hệ thống. Khóa speaker cần lời nói đủ để xác minh; câu đầu có thể cần nhắc lại.
- Queue PCM/WebRTC/ASD có giới hạn; audio không có bằng chứng không được bypass để giảm latency. GPU worker tách khỏi API để tải model không chặn thao tác menu.
- Native Codex quản lý lịch sử thread theo cấu hình CLI; mỗi guest dùng thread mới. Ảnh/PCM/voiceprint phía bridge chỉ ở memory; preferences chỉ lưu sau consent như workflow hiện tại.

## Kiểm thử

```bash
.venv/bin/python -m pytest -q
npm --prefix frontend test
npm --prefix frontend run build
PYTHONPATH=tests:. .venv/bin/python tests/browser_voice_smoke.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=Visual:. Visual/.venv/bin/python -m pytest Visual/tests/presentation/test_kiosk_provenance.py Visual/tests/domain/test_scene.py Visual/tests/domain/test_scene_bodies.py Visual/tests/application/test_source_reset.py Visual/tests/presentation/test_ws_server.py -q -p no:cacheprovider
```

Browser smoke dùng database fixture, thiết bị giả, kiểm tra giỏ chung/đổi khách/disarm và 375/768/1440 px. Native smoke đã dùng giọng tổng hợp gọi `kiosk_menu` với fixture, nhận audio đầu ra. Worker thật đã chặn cùng câu tổng hợp khi không có khuôn mặt sống; không có transcript khách lọt sang Codex. Warm attach → listening đo một lần khoảng 2.947 ms, không tính 5 giây presence và khóa speaker, không phải p95/SLA.

Cần chạy tại quầy để xác nhận camera/micro thật, PAD, lip sync, overlap/TSE và khoảng cách với người thật. Không suy ra chất lượng nhận diện tại quầy từ fake camera, unit tests hoặc handshake. Kiosk vẫn hỗ trợ chạm nếu voice/model/tài khoản gián đoạn. Checkout và QR merchant được bổ sung trong [merchant workflow](merchant-checkout.md); quét/chuyển khoản thật vẫn cần kiểm thử được cho phép tại quán.

## Protocol references

Native method shapes were generated from the installed CLI0.163.0 into `.runtime/codex-schema/`; observed data-channel events were checked against live synthetic input. [OpenAI App Server documentation](https://learn.chatgpt.com/docs/app-server) describes JSONL initialization, threads and dynamic tools. The [official0.163.0 realtime implementation](https://github.com/openai/codex/blob/rust-v0.163.0/codex-rs/core/src/realtime_conversation.rs) supplies the pinned native handoff behavior. New public GPT-Live event names differ from this installed native version; partial deltas are never treated as completed approval.
