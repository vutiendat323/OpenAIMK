"use strict";
/* Shared display translations. Language changes never send operator commands. */
(() => {
  const vi = {
    "METEK · Kiosk Mission Control": "METEK · Điều hành kiosk",
    "Interface language": "Ngôn ngữ giao diện",
    "Skip to monitoring": "Đi đến màn hình giám sát",
    "AI OPERATIONS": "ĐIỀU HÀNH AI",
    "Kiosk operations": "Vận hành kiosk",
    "Mission Control": "Trung tâm điều hành",
    "Connecting": "Đang kết nối",
    "Live": "Trực tiếp",
    "Disconnected": "Mất kết nối",
    "Camera": "Camera",
    "Live tuning": "Tinh chỉnh trực tiếp",
    "Visual monitoring": "Giám sát hình ảnh",
    "AI decisions": "Quyết định của AI",
    "Live vision": "Hình ảnh trực tiếp",
    "Camera feed + tracking": "Camera + theo dõi",
    "Live camera with face distance and target tracking overlays": "Camera trực tiếp với khoảng cách khuôn mặt và khung theo dõi khách hàng",
    "Pipeline statistics": "Thống kê xử lý",
    "Frame rate": "Tốc độ khung hình",
    "Track latency": "Độ trễ theo dõi",
    "Spoof latency": "Độ trễ chống giả mạo",
    "Waiting": "Đang chờ",
    "Tracking": "Đang theo dõi",
    "Target locked": "Đã khóa khách hàng",
    "Waiting for camera": "Đang chờ camera",
    "Vision service not reachable": "Không kết nối được dịch vụ Vision",
    "Proximity · last 12 seconds": "Khoảng cách · 12 giây gần nhất",
    "Filtered and raw face distance history": "Lịch sử khoảng cách khuôn mặt sau lọc và trước lọc",
    "Filtered": "Sau lọc",
    "Raw": "Trước lọc",
    "Alert threshold": "Ngưỡng cảnh báo",
    "Landmark gate": "Bộ lọc điểm khuôn mặt",
    "of recent frames accepted": "khung hình gần đây được chấp nhận",
    "Visual & proximity": "Hình ảnh và khoảng cách",
    "Nearest face": "Khuôn mặt gần nhất",
    "No target": "Chưa có khách hàng",
    "No face": "Chưa thấy khuôn mặt",
    "Person": "Có người",
    "Present, not facing": "Có người, chưa nhìn vào camera",
    "Holding": "Giữ kết quả",
    "Measuring": "Đang đo",
    "Too close": "Quá gần",
    "In range": "Trong phạm vi",
    "Liveness": "Độ tin cậy người thật",
    "Spoof": "Giả mạo",
    "Raw distance": "Khoảng cách trước lọc",
    "Before smoothing": "Trước khi làm mượt",
    "Body presence": "Phát hiện người",
    "Other faces": "Khuôn mặt khác",
    "None": "Không có",
    "Body only": "Chỉ thấy thân người",
    "Idle": "Chờ",
    "IDLE": "CHỜ",
    "Head turned": "Đang quay đầu",
    "Held": "Giữ kết quả",
    "Audio monitor": "Giám sát âm thanh",
    "Listen to target audio": "Nghe âm thanh mục tiêu",
    "Listen to target audio on the OpenJarvis machine": "Nghe âm thanh mục tiêu trên máy OpenJarvis",
    "ON": "BẬT",
    "OFF": "TẮT",
    "Applying local playback…": "Đang chuyển chế độ nghe…",
    "Local playback unavailable.": "Chưa thể phát âm thanh trên máy.",
    "Playing on the OpenJarvis machine.": "Đang phát trên máy OpenJarvis.",
    "Plays on the OpenJarvis machine.": "Phát trên máy OpenJarvis.",
    "Waiting for STT audio.": "Đang chờ âm thanh gửi vào STT.",
    "Awaiting microphone": "Đang chờ micro",
    "Incoming microphone waveform": "Dạng sóng âm thanh từ micro",
    "MIC INPUT · AFTER ENHANCEMENT": "ÂM THANH MICRO · SAU XỬ LÝ",
    "16 kHz · mono": "16 kHz · đơn kênh",
    "Input level": "Mức âm đầu vào",
    "Microphone energy in dBFS": "Mức năng lượng micro theo dBFS",
    "Raw level": "Mức âm trước xử lý",
    "Noise reduction": "Khử nhiễu",
    "STT audio gate": "Bộ lọc âm thanh STT",
    "AV fusion decision": "Quyết định kết hợp âm thanh và hình ảnh",
    "Awaiting session": "Đang chờ phiên thoại",
    "STANDBY": "CHỜ PHIÊN THOẠI",
    "LISTENING": "ĐANG LẮNG NGHE",
    "ACCEPT": "CHẤP NHẬN",
    "UNCERTAIN": "CHƯA CHẮC CHẮN",
    "REJECT": "TỪ CHỐI",
    "Start a voice session on the kiosk.": "Bắt đầu phiên thoại trên kiosk.",
    "Customer speech accepted by the speaker gate.": "Bộ lọc người nói đã chấp nhận giọng khách hàng.",
    "Ambiguous speech. The backend applies safe handling.": "Chưa xác định rõ người nói. Hệ thống đang xử lý thận trọng.",
    "Speech rejected by the speaker gate.": "Bộ lọc người nói đã từ chối âm thanh này.",
    "Waiting for fresh speaker evidence.": "Đang chờ dữ liệu mới để xác định người nói.",
    "Voice telemetry is stale. Waiting for fresh data.": "Dữ liệu thoại đã cũ. Đang chờ dữ liệu mới.",
    "Customer lock": "Trạng thái khóa khách hàng",
    "Target face": "Khuôn mặt mục tiêu",
    "Evidence": "Căn cứ quyết định",
    "Voiceprint": "Đặc trưng giọng nói",
    "Voice": "Giọng nói",
    "Voice match": "Độ khớp giọng nói",
    "Overlap / extraction": "Giọng chồng lấn / tách giọng",
    "Audio + face": "Âm thanh + khuôn mặt",
    "Audio": "Âm thanh",
    "Ready": "Sẵn sàng",
    "Enrolling": "Đang ghi nhận giọng",
    "LOCKED": "ĐÃ KHÓA",
    "UNLOCKED": "CHƯA KHÓA",
    "ACQUIRING": "ĐANG XÁC ĐỊNH",
    "SEARCHING": "ĐANG TÌM",
    "LOST": "MẤT KHÁCH HÀNG",
    "RELEASING": "ĐANG NHẢ KHÓA",
    "Microphone live": "Micro đang hoạt động",
    "Bot speaking · mic live": "Bot đang nói · micro hoạt động",
    "RNNoise active": "RNNoise đang hoạt động",
    "Raw fallback": "Dùng âm thanh chưa khử nhiễu",
    "Off": "Tắt",
    "Enabled": "Bật",
    "Active speaker detection": "Nhận diện người đang nói",
    "Audio and face active speaker probability": "Xác suất người đang nói từ âm thanh và khuôn mặt",
    "Waiting for synchronized audio and video.": "Đang chờ âm thanh và hình ảnh đồng bộ.",
    "Light-ASD is disabled.": "Light-ASD đang tắt.",
    "Light-ASD is unavailable.": "Light-ASD chưa khả dụng.",
    "Collecting synchronized evidence…": "Đang thu thập dữ liệu đồng bộ…",
    "Waiting for microphone audio.": "Đang chờ âm thanh từ micro.",
    "Mouth activity": "Chuyển động miệng",
    "ASD use": "Tỷ lệ sử dụng ASD",
    "Late windows": "Cửa sổ dữ liệu đến trễ",
    "Masked / no verdict": "Bị lọc / chưa có quyết định",
    "Blocked barge-ins": "Lượt ngắt lời bị chặn",
    "Decision timeline": "Lịch sử quyết định",
    "No decisions yet.": "Chưa có quyết định.",
    "no speech evidence": "chưa có căn cứ người nói",
    "Waiting for a kiosk voice session": "Đang chờ phiên thoại trên kiosk",
    "No telemetry yet": "Chưa có dữ liệu giám sát",
    "Kiosk voice connected · observations live": "Đã kết nối phiên thoại · giám sát trực tiếp",
    "Voice data stale": "Dữ liệu thoại đã cũ",
    "Telemetry live · 15 Hz": "Giám sát trực tiếp · 15 Hz",
    "Telemetry stale": "Dữ liệu giám sát đã cũ",
    "Operator controls": "Điều khiển vận hành",
    "Close live tuning": "Đóng bảng tinh chỉnh",
    "Changes apply live after confirmation. Save writes the active configuration files.": "Thay đổi có hiệu lực sau khi được xác nhận. Nhấn Lưu để ghi vào các tệp cấu hình đang dùng.",
    "Face IPD": "Khoảng cách hai đồng tử",
    "Scales face distance for a known interpupillary distance.": "Hiệu chỉnh khoảng cách khuôn mặt theo khoảng cách hai đồng tử đã biết.",
    "Proximity alert threshold": "Ngưỡng cảnh báo khoảng cách",
    "Distance alert in this console. Kiosk activation is configured separately.": "Ngưỡng cảnh báo trên console. Khoảng cách kích hoạt kiosk được chỉnh riêng.",
    "Audio / video offset": "Độ lệch âm thanh / hình ảnh",
    "Aligns face crops with the incoming audio.": "Căn chỉnh ảnh khuôn mặt với âm thanh đầu vào.",
    "Target speaker & fusion": "Người nói mục tiêu và kết hợp tín hiệu",
    "Available during a kiosk voice session.": "Có thể chỉnh khi kiosk đang có phiên thoại.",
    "Changes apply to this voice session. Save to persist.": "Thay đổi áp dụng cho phiên thoại này. Nhấn Lưu để giữ cấu hình.",
    "Kiosk activation distance": "Khoảng cách kích hoạt kiosk",
    "Distance at which the kiosk engages a customer.": "Khoảng cách để kiosk bắt đầu tương tác với khách hàng.",
    "Target acquisition distance": "Khoảng cách xác định khách hàng",
    "Maximum distance for acquiring a speaking customer.": "Khoảng cách tối đa để xác định khách hàng đang nói.",
    "Mouth activity threshold": "Ngưỡng chuyển động miệng",
    "Minimum lip activity for visual speech evidence.": "Chuyển động môi tối thiểu để xác định người nói qua hình ảnh.",
    "ASD acceptance threshold": "Ngưỡng chấp nhận ASD",
    "Minimum audio and face probability for acceptance.": "Xác suất kết hợp âm thanh và khuôn mặt tối thiểu để chấp nhận.",
    "ASD rejection threshold": "Ngưỡng từ chối ASD",
    "Must stay below the ASD acceptance threshold.": "Phải thấp hơn ngưỡng chấp nhận ASD.",
    "Voiceprint matching threshold": "Ngưỡng khớp đặc trưng giọng",
    "Minimum similarity to confirm the customer’s voice.": "Độ tương đồng tối thiểu để xác nhận giọng khách hàng.",
    "Voiceprint rejection threshold": "Ngưỡng từ chối đặc trưng giọng",
    "Must stay below the voiceprint matching threshold.": "Phải thấp hơn ngưỡng khớp đặc trưng giọng.",
    "Bot echo matching threshold": "Ngưỡng khớp tiếng vọng của bot",
    "Minimum similarity for identifying the bot’s own voice.": "Độ tương đồng tối thiểu để nhận ra giọng của chính bot.",
    "Waiting for connection.": "Đang chờ kết nối.",
    "Save settings": "Lưu cấu hình",
    "Applying live change…": "Đang áp dụng thay đổi…",
    "Connection lost. Change was not applied.": "Mất kết nối. Thay đổi chưa được áp dụng.",
    "Live change confirmed. Save to keep it after restart.": "Thay đổi đã được xác nhận. Nhấn Lưu để giữ lại sau khi khởi động lại.",
    "Saving active settings…": "Đang lưu cấu hình hiện tại…",
    "Disconnected. Waiting to reconnect.": "Mất kết nối. Đang chờ kết nối lại.",
    "Connected. Changes apply live.": "Đã kết nối. Có thể tinh chỉnh trực tiếp.",
    "Connected. No writable configuration was selected.": "Đã kết nối. Chưa chọn tệp cấu hình có thể ghi.",
    "Vision settings saved. No active voice session to save.": "Đã lưu cấu hình Vision. Chưa có phiên thoại để lưu cấu hình giọng nói.",
    "Vision and voice settings saved.": "Đã lưu cấu hình Vision và giọng nói.",
    "saved": "đã lưu",
    "failed": "thất bại",
    "invalid value": "giá trị không hợp lệ",
  };
  const patterns = [
    [/^Face (\d+)$/, (id) => `Khuôn mặt ${id}`],
    [/^(\d+) tracked$/, (count) => `${count} khuôn mặt được theo dõi`],
    [/^Spoof (.+)$/, (value) => `Giả mạo ${value}`],
    [/^TARGET · (\d+)$/, (id) => `MỤC TIÊU · ${id}`],
    [/^TARGET LOCKED · FACE (\d+)$/, (id) => `ĐÃ KHÓA · KHUÔN MẶT ${id}`],
    [/^Face (\d+) · synchronized speech probability$/, (id) => `Khuôn mặt ${id} · xác suất lời nói đồng bộ`],
    [/^(.+) mode$/, (mode) => `Chế độ ${mode === "fusion" ? "kết hợp tín hiệu" : ["audio", "audio_only"].includes(mode) ? "âm thanh" : mode}`],
    [/^(Overlap|Solo) · TSE (ready|not ready)$/, (overlap, ready) => `${overlap === "Overlap" ? "Chồng lấn" : "Một người nói"} · TSE ${ready === "ready" ? "sẵn sàng" : "chưa sẵn sàng"}`],
    [/^Change rejected: (.+)$/, (error) => `Thay đổi bị từ chối: ${translate(error)}`],
    [/^Vision: (.+) · Voice: (.+)$/, (vision, voice) => `Vision: ${translate(vision)} · Giọng nói: ${translate(voice)}`],
  ];
  let language = "en";
  try { language = localStorage.getItem("metek.console.language") === "vi" ? "vi" : "en"; } catch { /* Storage may be disabled. */ }
  function translate(value) {
    if (language !== "vi" || typeof value !== "string") return value;
    if (Object.hasOwn(vi, value)) return vi[value];
    for (const [pattern, format] of patterns) {
      const match = value.match(pattern);
      if (match) return format(...match.slice(1));
    }
    return value; // Preserve unknown server diagnostics verbatim.
  }
  // Capture original template text once. Live modules own their updated nodes.
  const originals = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (!node.parentElement.closest("script, style, [data-language]")) {
      const key = node.textContent.trim();
      if (key && Object.hasOwn(vi, key)) originals.push({ node, source: node.textContent, key });
    }
  }
  const attributes = [...document.querySelectorAll("[aria-label]")]
    .filter((element) => !element.hasAttribute("data-language"))
    .map((element) => ({ element, source: element.getAttribute("aria-label") }));
  const title = document.title;
  function apply() {
    document.documentElement.lang = language;
    document.title = translate(title);
    originals.forEach(({ node, source, key }) => {
      if (node.isConnected) node.textContent = source.replace(key, translate(key));
    });
    attributes.forEach(({ element, source }) => element.setAttribute("aria-label", translate(source)));
    document.querySelectorAll("[data-language]").forEach((button) => {
      button.setAttribute("aria-pressed", String(button.dataset.language === language));
    });
  }
  window.MissionI18n = { t: translate, language: () => language };
  document.querySelectorAll("[data-language]").forEach((button) => {
    button.addEventListener("click", () => {
      language = button.dataset.language;
      try { localStorage.setItem("metek.console.language", language); } catch { /* Still switch for this page. */ }
      apply();
      window.dispatchEvent(new CustomEvent("vision:language"));
    });
  });
  apply();
})();
