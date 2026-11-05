# Avatar realtime local: nguồn nghiên cứu và lựa chọn cho RTX 3060 12GB

Ngày kiểm tra nguồn: 2026-10-30. Phạm vi: mô hình avatar công khai, chạy local; không thay dịch vụ voice/Codex hiện có. Đây là đối chiếu tài liệu chính chủ, chưa chạy benchmark GPU hoặc xem lại chất lượng clip trên máy kiosk.

## Kết luận lựa chọn

Giữ Ditto làm baseline hiện tại. Chưa có bằng chứng đủ mạnh để thay bằng một mô hình phổ dụng khác mà đồng thời bảo đảm đúng khuôn miệng/răng của nhân vật, độ trễ thấp và realtime trên **RTX 3060 12GB**. “Real-time” trong paper thường nói về GPU khác hoặc chỉ một phần pipeline.

Nếu ưu tiên cao nhất là hình dáng miệng/răng của nhân vật gốc, hướng đáng nghiên cứu là **mô hình theo từng nhân vật, học từ video nói có răng/miệng nhất quán**. Tuy nhiên bộ clip AI toàn thân 8–10 giây hiện có chưa mặc nhiên là dữ liệu huấn luyện phù hợp. InsTaG là ngoại lệ đáng thử với dữ liệu ít; các recipe SyncTalk, ER-NeRF và TalkingGaussian phổ biến yêu cầu video dài hơn. Chi tiết và nguồn bên dưới.

## Phải phân biệt ba nhóm

| Nhóm | Cơ chế và hệ quả đối với yêu cầu giữ nguyên nhân vật |
|---|---|
| Sinh/inpaint ảnh từ latent | Ví dụ LatentSync sinh vùng ảnh bằng diffusion có điều kiện audio, reference và masked frame. Đây không phải thao tác giữ nguyên pixel của khoang miệng. [LatentSync chính chủ](https://github.com/bytedance/LatentSync#-introduction). |
| Biến dạng feature nguồn rồi giải mã | Ditto sinh motion trong không gian LivePortrait; warping appearance feature từ ảnh nguồn rồi decoder tạo ảnh. LivePortrait thuần cần driving motion/video. **Suy luận:** giữ feature nguồn giúp bám diện mạo, nhưng decoder vẫn tổng hợp ảnh; không có bảo đảm răng luôn đúng như clip gốc. Thay bộ audio-to-motion không tự loại bỏ giới hạn renderer. [Ditto, §3.1](https://arxiv.org/html/2411.19509v3#S3.SS1). |
| Huấn luyện theo nhân vật: 2D/NeRF/3DGS | SyncTalk_2D học video của một nhân vật; GaussianTalker xây canonical 3DGS rồi biến dạng theo audio. **Suy luận:** có cơ hội học chính răng và phong cách nói của nhân vật, nhưng chỉ từ dữ liệu nhìn thấy; không tương đương giữ nguyên mọi pixel hay tạo được phần miệng chưa xuất hiện. [SyncTalk_2D](https://github.com/ZiqiaoPeng/SyncTalk_2D), [GaussianTalker paper](https://arxiv.org/abs/2404.16012). |

## Shortlist thực tế

| Lựa chọn | Bằng chứng phần cứng, dữ liệu, giới hạn | Quyết định cho kiosk hiện tại |
|---|---|---|
| **Ditto hiện tại** | Paper đo trên **A100**: online head RTF 0.895, first-frame delay 385ms; online full body RTF 0.914, 392ms. Các số này không phải kết quả 3060. Repo có PyTorch và training branch; code Apache-2.0. [Paper §4.6](https://arxiv.org/html/2411.19509v3#S4.SS6), [README](https://github.com/antgroup/ditto-talkinghead), [LICENSE](https://github.com/antgroup/ditto-talkinghead/blob/main/LICENSE). | Giữ baseline; đo toàn pipeline trước khi thay model. Chất lượng offline 50 bước và live 5 bước là hai cấu hình khác, không nên dùng clip offline để chứng minh live đã đạt. Các cấu hình/số đo local là thông tin từ phiên làm việc, chưa được kiểm chứng trong nghiên cứu này. |
| **LivePortrait + audio predictor khác** | Benchmark chính chủ cho RTX4090 với `torch.compile`: warping **5.21ms**, generator **7.59ms** mỗi frame. LivePortrait không tự giải quyết audio-to-motion. License MIT nhưng pretrained InsightFace detection phải thay/được cấp quyền phù hợp khi dùng thương mại. [Speed](https://github.com/KlingAIResearch/LivePortrait/blob/main/assets/docs/speed.md), [README](https://github.com/KlingAIResearch/LivePortrait), [LICENSE](https://github.com/KlingAIResearch/LivePortrait/blob/main/LICENSE). | Không coi là một model mới chữa tận gốc miệng/răng. Với motion đã nhanh, lợi ích có thể nhỏ nếu bottleneck vẫn là warping/decoder/composite. Đây là suy luận kiến trúc, cần profiler xác nhận. |
| **SyncTalk_2D** | Nhân vật riêng; input recipe **5 phút** nói trước camera, ít di chuyển, ánh sáng ổn định, audio sạch; output face resolution **328**; README nói khoảng 5 giờ train, không nêu GPU benchmark. Repo không thấy LICENSE ở root khi kiểm tra; chữ “commercial-grade” không phải giấy phép. [README và file list](https://github.com/ZiqiaoPeng/SyncTalk_2D). | Có thể là thử nghiệm 2D nhẹ khi có video huấn luyện thích hợp và quyền sử dụng rõ ràng; chưa phải drop-in với clip 8–10 giây. |
| **SyncTalk 3D** | Recipe **4–5 phút, 25 FPS, khoảng 512×512**. Mode portrait paste generated face lên ảnh gốc. Code có **CC BY-NC 4.0**, cấm dùng thương mại theo điều khoản hiện tại. [README](https://github.com/ZiqiaoPeng/SyncTalk#data-preparation), [LICENSE](https://github.com/ZiqiaoPeng/SyncTalk/blob/main/LICENSE). | Không ưu tiên cho triển khai kiosk thương mại; yêu cầu dữ liệu cũng chưa khớp. |
| **ER-NeRF** | Recipe **1–5 phút, 25 FPS, khoảng 512×512**, cần preprocess và train riêng. Repo code MIT; còn phụ thuộc face parsing/3DMM/Basel assets phải kiểm tra riêng. [README](https://github.com/Fictionarry/ER-NeRF#usage), [LICENSE](https://github.com/Fictionarry/ER-NeRF/blob/main/LICENSE). | Hợp nghiên cứu nhân vật cố định khi có dữ liệu mới. Chưa có benchmark chính chủ 3060 đủ để cam kết FPS kiosk. |
| **GaussianTalker, bản Cho et al.** | Chính chủ test **RTX3090/A6000**; paper công bố tới **120 FPS** rendering, cần train theo dữ liệu nhân vật. LICENSE của repo là Gaussian-Splatting License, giới hạn nghiên cứu/đánh giá phi thương mại nếu chưa có đồng ý khác. [README](https://github.com/cvlab-kaist/GaussianTalker), [Paper](https://arxiv.org/abs/2404.16012), [LICENSE](https://github.com/cvlab-kaist/GaussianTalker/blob/main/LICENSE.md). | Nhanh về cấu trúc nhưng vướng dữ liệu/giấy phép. Không trộn với model khác cũng tên GaussianTalker của pixelai-team; FPS của hai paper không thay thế nhau. |
| **TalkingGaussian** | Tách face/mouth và tạo tooth mask; recipe **1–5 phút, 25 FPS, khoảng 512×512**. Repo ghi research-only và dựa Gaussian Splatting. [README](https://github.com/Fictionarry/TalkingGaussian), [Upstream license](https://github.com/graphdeco-inria/gaussian-splatting/blob/main/LICENSE.md). | Đúng hướng nghiên cứu anatomy hơn việc thay một model inpaint phổ dụng; chưa đủ căn cứ triển khai thương mại hoặc chạy ngay bằng clip hiện tại. |

## Ngoại lệ dữ liệu ngắn: InsTaG

CVPR2025 InsTaG dùng pretrained motion priors và adaptation theo người. Paper báo **5 giây** dữ liệu, **82.5 FPS trên RTX3080Ti**, inference peak **1826MB**, adaptation **2214MB** trong thiết lập của tác giả. Đây là ứng viên đáng thử cho GPU 12GB, **không phải benchmark RTX3060** và không đo latency voice-to-display của kiosk. [Paper, Table 1/10 và implementation details](https://arxiv.org/html/2502.20387v1).

Repo mặc định adaptation **10 giây**, nhận video người đang nói **25 FPS, khoảng 512×512**. Tác giả lưu ý HuBERT nên có ít nhất 10 giây, AVE có thể jitter/crash; pretrained weights và code được mô tả dành cho research. [README](https://github.com/Fictionarry/InsTaG).

**Đánh giá:** thử có kiểm soát sau khi làm rõ quyền triển khai. Một clip toàn thân 720p có thể có quá ít pixel mặt hoặc quá ít trạng thái khoang miệng. AI tạo răng khác nhau giữa các frame sẽ tạo dữ liệu mâu thuẫn; kéo dài bằng loop không bổ sung viseme mới. Đây là suy luận từ yêu cầu học theo video, chưa được kiểm chứng với asset của kiosk. Cần xem crop mặt thực tế, audio đồng bộ và độ nhất quán răng trước khi train.

## Các model streaming mới không nên thay vội

| Model công khai | Nguồn chính chủ và lý do |
|---|---|
| **SoulX-FlashHead Lite/Pro** | Lite công bố **96 FPS trên RTX4090**; Pro **10.8 FPS/4090**, realtime với **hai RTX5090**. Lite/Pro đã phát hành. Đây là image-to-video generation; chưa thấy benchmark 3060 hoặc bảo đảm anatomy. Chỉ giữ làm ứng viên A/B, không chuyển production theo con số 4090. [Repo chính chủ](https://github.com/Soul-AILab/SoulX-FlashHead). DiT/Wan VAE Apache-2.0; Lite có LTX VAE **Open-RAIL-M**, phải theo từng component. [Model card](https://huggingface.co/Soul-AILab/SoulX-FlashHead-1_3B). |
| **Alibaba-Quark LiveAvatar** | Phiên bản FP8 cho **48GB GPU**; full single-GPU hướng dẫn **80GB**. **45+ FPS** được công bố trên multi-H800. Vượt xa VRAM12GB trong cấu hình phát hành; không hợp máy hiện tại. Đây là repo nghiên cứu, khác dịch vụ HeyGen trùng tên. [Repo chính chủ](https://github.com/Alibaba-Quark/LiveAvatar). |
| **LipForcing** | 14B đã phát hành; **~37GB** peak với precomputed text embeddings, **~50GB** nếu chạy T5. 1.3B vẫn unchecked trong roadmap lúc kiểm tra; số31FPS không có nghĩa có checkpoint nhẹ để dùng ngay hoặc chạy được trên3060. Test environment là **H200**. Loại bản14B khỏi shortlist12GB; theo dõi1.3B khi thực sự phát hành. [Repo chính chủ](https://github.com/cvlab-kaist/LipForcing). |
| **LatentSync** | Chính chủ ghi inference **8GB cho1.5**, **18GB cho1.6**; 1.6 tăng lên512×512. README không cung cấp bằng chứng realtime3060 hoặc causal live input. 1.5 có thể vừa VRAM nhưng vẫn là diffusion sinh vùng miệng; không chữa mặc nhiên lỗi anatomy. Dùng đánh giá offline nếu cần, không gắn vào hot path hiện tại. [Repo chính chủ](https://github.com/bytedance/LatentSync#-inference). |
| **AVTR-1** | Self-hosted, dual-audio motion, dùng renderer weights từ Ditto/LivePortrait. Bảng tác giả:5-frame/200ms chunk mất **206ms trên3060Ti**,181ms trên3070; **không có3060**. Đây là throughput chunk, chưa phải latency turn-to-display. [README](https://github.com/avaturn-live/avtr-1). Renderer và streamer **PolyForm Noncommercial**, bất kể doanh thu; model có license riêng. Không phải drop-in thương mại miễn phí. [Component license map](https://github.com/avaturn-live/avtr-1/blob/main/LICENSE.md). |

## Thứ tự thử và tiêu chí loại

1. **Baseline Ditto**: dùng cùng avatar, cùng audio tiếng Việt và đúng cấu hình live; ghi hình gốc + crop miệng. Phân biệt neural FPS, FPS encoder/RTP và FPS trình duyệt; frame lặp không tính là frame neural mới.
2. **Thử giảm overhead renderer đang có**, rồi mới đổi model audio-to-motion. Profile quyết định nơi tối ưu; không suy từ paper GPU khác ra tốc độ3060. Giảm số bước chỉ được chấp nhận sau A/B anatomy và lipsync.
3. **Nếu anatomy vẫn không đạt:** thử InsTaG như nhánh nghiên cứu độc lập sau khi kiểm tra quyền sử dụng và chất lượng dữ liệu; hoặc tạo bộ video nói theo nhân vật dài hơn để đánh giá2D/3DGS. Không tự động tải/train nhiều model cùng lúc.
4. **Ngưỡng chấp nhận do dự án đặt**: cùng nguồn răng/khuôn miệng qua các âm mở/khép môi, không răng nhấp nháy hoặc đổi cấu trúc; audio không đứt; latency không tăng dần trong phiên dài; dừng nói khi bị ngắt; benchmark đồng thời compositor/encoder/browser đang chạy. Các tiêu chí này là đề xuất đánh giá, không phải kết quả đã đo.

Nếu yêu cầu “không được vẽ lại răng” là tuyệt đối, giải pháp có tính bảo đảm hơn là dùng **khung hình/patch miệng thực sự từ bộ asset đã duyệt**, chọn theo trạng thái phát âm và ghép có kiểm soát. Đây là hướng thiết kế cần bộ viseme đủ phủ; clip 8–10 giây chưa chứng minh có đủ. Nó cũng phải đánh đổi độ tự nhiên/coarticulation. Không mô hình sinh ảnh tổng quát nào trong các nguồn đã đọc đưa ra bảo đảm giữ anatomy chính xác cho mọi audio.
