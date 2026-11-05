# Trend Coffee avatar assistant

The voice controls now live with a barista portrait, current conversation and audio waveform. Desktop uses assistant / menu / cart columns; categories move above the menu. Tablet and mobile place the assistant above the menu. The original menu layout remains available when voice is disabled.

## Interaction

- Start uses the existing camera/microphone permission flow. Begin, end and disarm retain the existing session behavior.
- Speaking state comes from actual PCM playback. The waveform samples the playback analyser, or the microphone analyser while Fusion has locked the active speaker. Silence and inactive states show quiet bars.
- The panel shows final voice turns in a scrolling conversation; history is bounded to six in memory and cleared on session/end/disarm.
- “Nhắn tin với Trend” opens the existing chat view. “Tự chọn trên menu” moves to the menu. Touch ordering and merchant QR remain in their normal screens.
- The portrait is a static generated 3D illustration, with no facial rig or lip-sync renderer. It represents a fictional virtual barista, labeled “TRỢ LÝ AI”.

## Asset and reference

Reference direction: supplied reception-kiosk images and [AI Avatar Platform UI/UX Design](https://dribbble.com/shots/27065828-AI-Avatar-Platform-UI-UX-Design). The provided images establish the virtual-receptionist direction; no claim of replicating the linked animation.

Generated with the built-in `image_gen` tool. Original: `output/imagegen/trend-barista.png`. Runtime asset: `frontend/public/avatars/trend-barista.webp`, 1024×1536 with alpha, approximately 138 KB. WebP conversion preserves framing/transparency; the original PNG is retained. Vite copies the runtime asset into `trendcoffee/static/avatars/`.

Final generation prompt:

> Use case: stylized-concept. Asset type: production web kiosk virtual barista avatar, portrait 2:3 framing. Generate ONE original friendly young adult Vietnamese woman as a polished high-end 3D digital human, inspired by the general category of virtual receptionists, not any existing character or real person. Visible from full head with plenty of headroom down to mid-thigh, front-facing, natural gentle smile, warm dark-brown eyes, black hair neatly tied in a low bun with a few soft face-framing strands. Wear a modest crisp ivory collared blouse with rolled sleeves and a plain dark forest-green barista apron with subtle stitched details, simple tan apron straps. Relaxed welcoming pose, hands loosely together at waist, anatomically correct fingers, realistic proportions. Contemporary elegant semi-realistic 3D render, natural skin material, soft warm studio key light and gentle rim light. All subject edges contained within frame. Genuine transparent background, no environment, no kiosk hardware, no text, no logos, no props, no watermark. Asset should integrate on a cream and sage-green Trend Coffee assistant panel. Produce a clean transparent PNG cutout.

## Verification

`tests/browser_voice_smoke.py` runs an isolated fixture API with fake devices and synthetic PCM, never a live merchant write. It checks the portrait, analyser-driven waveform, both transcript roles, shared cart, next-guest isolation, responsive screenshots and axe when available. Independent review also covers 600px-height screens and voice-disabled layout. Physical AV recognition and real-world acoustic quality require separate field validation.
