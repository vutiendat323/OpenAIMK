# Visual → guest/thread mới → AV Fusion → Codex native voice

User authorizes implementation only in OpenAIMK. Never modify `/home/metek/Projects/jarvis` or root `AGENTS.md`. The latest steering requires **audio after AV Fusion**; raw browser microphone must never bypass that boundary.

## Accepted behavior

- An operator grants camera/microphone once. Browser camera feeds the isolated local Visual worker; fresh processed-frame evidence under 0.6m for five seconds opens a new guest capability and Codex thread. Owner absence three seconds ends it with bounded sensor-loss grace.
- Preserve SCRFD, ByteTrack, MiniFASNet, face embedder/lips, Light-ASD, YOLO and sibling Metric3D. Preserve copied Audio SpeakerStream with Sortformer, TitaNet, TSE and VisionAudioBridge. Missing models/evidence fail closed.
- Browser PCM16 16kHz mono → Fusion → accepted/masked PCM → **backend-owned** WebRTC → native `codex app-server` voice. Native ChatGPT authentication remains inside Codex. No substitute STT/LLM/TTS and no raw browser WebRTC track.
- Voice and touch share one authoritative cart, explicit fulfillment/table and exact server quote. Subsequent complete affirmative customer turn or independent touch confirmation submits a local pending request. Payment remains unverified and POS/bank disconnected.
- One controller/guest; generation checks inside mutation locks; call-id deduplication; old callbacks, partial microphone packets, delayed/TSE audio and playback cannot cross guest reset. Camera persists between guests only while armed. Maximum ten minutes, warning at nine, idle120s includes accepted speech/touch/playback.
- Code Mode host is required by the selected Codex model for dynamic tools. Disable shell, apps/plugins, web, external MCP, multi-agent; sandbox read-only, approval never. Server-owned schema and guest capability checks remain the authority.

## Implementation

`codex_voice.py` handles native JSONL RPC; `native_peer.py` owns filtered media transport and actual CLI v3 transcript events. `av_transport.py` supervises a model worker; `av_worker.py` composes copied Audio ports. `visual_worker.py` starts all required Visual models on loopback9877, without touching original Jarvis. `kiosk.py` owns lifecycle/cart/quote; `api.py` exposes authenticated same-origin WS on the existing8080 port. React owns capture/playback and displays server state. `scripts/kiosk.py` manages only recorded workspace-owned processes.

## Validation

Use failing-then-passing regression tests for freshness, guest races, confirmation negation, tool arguments, partial-audio reset and process closure. Run full backend/frontend checks, copied Visual regressions, fixture browser journeys, native transport/tool smoke and real worker rejection with no live face. Independent review checks customer isolation and fail-closed evidence. Physical camera/people, live TSE quality and calibration require at-counter validation; no fake success or merchant/payment claim.
