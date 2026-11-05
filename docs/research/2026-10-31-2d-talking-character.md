# Talking head for the anime Nhân vật Trend: sources and selection for one RTX 3060 — 2026-10-31

Sources checked 2026-10-31. Scope: which method generates the whole face (head, eyes,
mouth, expression) as one image from one reference or the existing video, driven by audio,
for an anime character, live on one local RTX 3060 12 GB on Linux or in the browser. This
is a source and repository review. **No model was installed or run, and no GPU benchmark was
taken.** Application code, assets and services are unchanged. Every 3060 figure for a method
we do not already run is labelled **Inference**.

The brief was refocused mid-research from rig-based lip-sync to neural talking heads. Live2D,
Rive, Spine, Inochi2D and viseme tools are therefore reduced to the fallback table in
[section 7](#7-rig-and-viseme-fallback-short).

## Bottom line

**No published method meets all of this: anime-validated, audio-driven, whole-face, and
real time on a 3060.** The closest fit is one the repo already has.

- **Recommendation: Ditto whole-head output on Trend's anime clip.** Turn off the mouth
  compositor and show the full generated head. It is the only audio-driven method with a
  measured streaming result on this exact GPU, and needs no new model, key or payment. The
  first step is a cheap offline anime test, because Ditto has never been run on this art.
  The mouth-versus-face style split disappears because all facial pixels come from one
  decoder pass. The price is real: the softness and colour drift the user reported on
  2026-10-30 comes back, and a generated head still sits inside source-video pixels at the
  hairline and neck.
- **Fallback: Talking Head Anime 3 (THA3).** It is the only anime-native whole-image
  renderer whose weights allow commercial use. It renders per frame, so nothing buffers and
  interruption is immediate. It is not audio-driven, so it needs an audio-to-vowel step, and
  the head is only about 128 px, which is its main weakness.
- **Do not build on the 2026 streaming diffusion models on a 3060.** LeapTalk is the most
  promising method overall, and its whole square is generated as one image. But it peaks at
  about 11.8 GB at 512×512, needs 1.12 s of audio per default chunk, and has only been shown
  real time on RTX 4090-class hardware. No 3060 measurement exists. It becomes the first
  choice only if the GPU is upgraded.

## What "one image" actually means

The user's complaint is about seams between separately rendered regions. Methods fall into
four classes, and the headline "real-time talking head" hides the difference.

| Class | What is generated | Remaining seam | Examples |
|---|---|---|---|
| A. Whole frame | Every pixel of the output square, in one decode | None inside the square. Pasting that square onto a body adds one back. | THA3/THA4, LeapTalk, FlashHead, IMTalker |
| B. Whole head, warped | A 512 px head crop, warped from source features, then pasted back | Crop boundary at hair and neck. Inside the head, none. | LivePortrait, Ditto as designed |
| C. Lower-face inpaint | Mouth and jaw only | Face versus mouth, the user's complaint | MuseTalk, Wav2Lip, the current `tensorrt-mouth` |
| D. Sprite swap | Nothing is generated | Face versus mouth | The rejected 2D atlas |

Class C is why the kiosk's Ditto path still shows a mouth region: `composite_mouth` preserves
source pixels outside a feathered mouth and lower-jaw region
([evaluation](../evals/avatar-state-appearance.md)).

## Local facts that decide this

| Fact | Value | Source |
|---|---|---|
| Ditto generated mouth rate in live WebRTC, speech | **15.6 FPS**; changed-pose rate 8.8 | [throughput evaluation](../evals/avatar-neural-throughput.md) |
| Ditto isolated peak VRAM | 4,098 MiB | [throughput evaluation](../evals/avatar-neural-throughput.md) |
| Three services at rest, including Ditto | 7,398 MiB of 12,288 MiB | [continuity evaluation](../evals/kiosk-media-continuity-2026-10-30.md) |
| Native output | Mono PCM16, 48 kHz; input end to first audio about 1.0–2.0 s | [streaming evaluation](../evals/voice-streaming-continuity.md) |
| Ditto streaming model | Causal, past features plus 80 ms of already received audio; 160 ms stride | [`ditto_realtime.py`](../../scripts/ditto_realtime.py) |
| MediaPipe on this anime clip | Tracked all 239 frames offline | [motion evaluation](../evals/browser-2d-motion.md) |

**Inference, non-avatar VRAM:** 7,398 − 4,098 ≈ 3.3 GB for the other services. These two
samples come from different runs, so this is an order of magnitude only. Live Fusion load is
not included.

**Inference, how far a 3060 is from a 4090.** No talking-head method below publishes a 3060
number, so a calibration is needed. Ditto's renderer is built on LivePortrait's
([Ditto §3.1](https://arxiv.org/html/2411.19509v3)). LivePortrait's warping and generator take
5.21 + 7.59 = 12.8 ms on an RTX 4090
([speed table](https://github.com/KlingAIResearch/LivePortrait/blob/main/assets/docs/speed.md)).
The kiosk's 3060 measured 15.07 FPS, or 66 ms, for separately compiled PyTorch models on
GPU-resident inputs ([evaluation](../evals/ditto-avatar.md)), and 48.5 ms for the TensorRT full
renderer with transfers
([report](../../output/avatar-quality-review/neural-fps/tensorrt-hybrid-ampnorm.json)). That
gives **a 3060 roughly 4–5× slower than a 4090 on this family of networks**. It is one
convolutional workload with non-identical settings and may not transfer to a transformer. Use
it to rank options, not to promise a frame rate.

## 1. Anime-specific methods

### Talking Head Anime 3 (THA3)

- **Input and output:** one 512×512 image with alpha, frontal, upright, hands low, and the head
  in roughly a 128×128 box in the upper middle. Other sizes are resized
  ([README](https://github.com/pkhungurn/talking-head-anime-3-demo)).
- **Driver, not audio:** a pose vector. The parameters include `mouth_aaa`, `iii`, `uuu`, `eee`,
  `ooo`, `delta`, mouth corners and smirk, plus eyebrow, eye and iris groups, `head_x`, `head_y`,
  `neck_z`, `body_y`, `body_z` and `breathing`
  ([`pose_parameters.py`](https://github.com/pkhungurn/talking-head-anime-3-demo/blob/main/tha3/poser/modes/pose_parameters.py)).
  The vector is 45-dimensional ([THA4 paper](https://ar5iv.labs.arxiv.org/html/2311.17409)).
- **One image:** yes. Head, eyes, mouth and torso come from one generated 512 px RGBA frame.
- **Anime evidence:** the strongest available, as this is its purpose. Known defects: thin
  structures such as hair strands can vanish after rotation
  ([THA4 paper](https://ar5iv.labs.arxiv.org/html/2311.17409)), and large hats and props are
  unsupported ([Extras README](https://github.com/SillyTavern/SillyTavern-Extras/blob/main/talkinghead/README.md)).
- **Measured speed conflicts, so treat it as unresolved:**
  - RTX 3060: "about 9-10 FPS" ([SillyTavern docs](https://docs.sillytavern.app/extensions/talkinghead/);
    model variant not stated).
  - RTX 3070 Ti mobile, `separable_half`: about 40–50 FPS render, about 520 MB VRAM
    ([Extras README](https://github.com/SillyTavern/SillyTavern-Extras/blob/main/talkinghead/README.md)).
  - RTX 3070 Ti mobile, Raven defaults: "a bit under 25 FPS"
    ([Raven avatar README](https://github.com/Technologicat/raven/blob/main/raven/avatar/README.md)).
  - Full THA4-era system: 116.8–159.6 ms per frame across its three test machines, including
    a GTX 1080 Ti ([THA4 paper](https://ar5iv.labs.arxiv.org/html/2311.17409)).
- **Latency and interruption:** per-frame pose input with no audio window. Setting the mouth
  morphs to rest takes effect on the next frame (**Inference** from the architecture).
- **Licence:** code MIT; models **CC BY 4.0**, so commercial use with attribution is allowed
  ([README](https://github.com/pkhungurn/talking-head-anime-3-demo)).

Three problems are specific to Trend:

1. **The input needs an open mouth.** "The character's eyes and mouth must be open, so that the
   model sees what they look like when open"
   ([Extras README](https://github.com/SillyTavern/SillyTavern-Extras/blob/main/talkinghead/README.md)).
   `mouth_aaa` defaulting to 1.0 in `pose_parameters.py` is consistent with this. The reference
   image has a closed smile, so an open-mouth frame from the video would be needed. Raven's
   workaround when a mouth will not animate is pasting one from another character
   ([Raven README](https://github.com/Technologicat/raven/blob/main/raven/avatar/README.md)),
   which is the hand-stitching the user rejected.
2. **The head is small.** The input is fixed at 512×512
   ([Raven README](https://github.com/Technologicat/raven/blob/main/raven/avatar/README.md)).
   **Inference:** Trend's head measures about 500 px tall in the 1920 px source by eye, so
   fitting the 128 px box keeps about a quarter of that linear resolution, and a portrait kiosk
   needs close to 4× upscaling. Raven's Anime4K path takes 512 to 1024 in 4.3–10 ms on an RTX
   4090 laptop GPU but "will not regenerate missing details."
3. **It needs an audio step.** See [the fallback](#fallback-tha3-with-streaming-vowel-weights).

Prior art for the mouth: Raven lip-syncs THA3 with a phoneme-to-morph table. It needs timestamped
phonemes from Kokoro TTS, so it cannot run on our output-only PCM as written
([README](https://github.com/Technologicat/raven/blob/main/raven/avatar/README.md),
[`tts.py`](https://github.com/Technologicat/raven/blob/main/raven/client/tts.py)). Its server is
AGPL-3.0-only ([README](https://github.com/Technologicat/raven)). SillyTavern's talkinghead
support was dropped in 1.12.13, and Extras is discontinued
([docs](https://docs.sillytavern.app/extensions/talkinghead/)).

### Talking Head Anime 4 (THA4)

- **Method:** a slow full model distils a character-specific student of about 1.8 MB against 627 MB
  for the full system ([paper](https://ar5iv.labs.arxiv.org/html/2311.17409)).
- **Speed, student:** 12.5 ms on RTX A6000, 15.1 ms on Titan RTX, 22.1 ms on GTX 1080 Ti, at 512×512
  ([paper, Table 4](https://ar5iv.labs.arxiv.org/html/2311.17409)). That is the best published
  whole-image anime rate on consumer hardware.
- **Browser:** student models ran in TensorFlow.js demos
  ([project page](https://pkhungurn.github.io/talking-head-anime-4)). This is the only neural anime
  renderer found that demonstrably runs in a browser. However, the conversion code "is not included
  in this repository" and the author "will not release it unless I change my mind"
  ([README](https://github.com/pkhungurn/talking-head-anime-4-demo)).
- **Cost per character:** about 30 hours on an RTX A6000, plus a hand-made facial-organ mask
  ([README](https://github.com/pkhungurn/talking-head-anime-4-demo)).
- **Licence blocker:** code is MIT, but THA4 models are **CC BY-NC 4.0**
  ([README](https://github.com/pkhungurn/talking-head-anime-4-demo)). Whether a student trained from
  a non-commercial teacher is commercially usable is **unresolved**; I found no statement from the
  author. It should not ship without written permission.
- **Audio:** not supported. Drivers are iFacialMocap and webcam blendshapes.
- The same open-mouth and 128 px constraints apply.

### Other anime-specific work

Repeated searches found **no released, audio-driven, anime-specific real-time method**.
TalkingMachines states it can animate "arbitrary styles—including photorealistic, anime, and 3D
avatars" ([PDF](https://arxiv.org/pdf/2506.03099)). It is an 18-billion-parameter model
([abstract](https://arxiv.org/abs/2506.03099)). Its cheapest setting still uses one H100 for the
score model, with the VAE decoder on separate GPU resources, so it is out of scope for one 3060.
No code release was found.

## 2. LivePortrait family

- **Driver:** LivePortrait needs a driving video or motion template and has no audio input
  ([README](https://github.com/KlingAIResearch/LivePortrait)).
- **Anime in training:** the authors report that a model trained only on realistic video "generalizes
  poorly to styled portraits, e.g., anime." They therefore mix in about 60K styled images, including
  AAHQ, and about 1.3K styled clips ([paper](https://arxiv.org/html/2407.03168)). This is better
  stated intent than most methods have. It is not a measured result on cel anime.
- **Anime in the field:** the face detector is the weak point. [Issue #108](https://github.com/KlingAIResearch/LivePortrait/issues/108),
  labelled `anime`, reports "not work with anime or toon." The maintainer suggests manual cropping
  and points to X-Pose. One user still hit an error with auto-crop disabled.
- **Animals mode:** fine-tuned on animals and requires X-Pose ([README](https://github.com/KlingAIResearch/LivePortrait)).
  It targets animals, not anime.
- **One image:** class B. Output is 512×512, and stitching pastes the head back without pixel
  misalignment at the shoulder ([paper](https://arxiv.org/html/2407.03168)).
- **Speed:** 12.8 ms on RTX 4090. FasterLivePortrait reports 30+ FPS on RTX 3090 with TensorRT,
  including pre- and post-processing ([README](https://github.com/warmshao/FasterLivePortrait)).
- **Licence:** MIT code, but InsightFace's models are non-commercial, and commercial users "should
  remove and replace" them ([LICENSE](https://github.com/KlingAIResearch/LivePortrait/blob/main/LICENSE),
  [InsightFace](https://github.com/deepinsight/insightface)). FasterLivePortrait offers a MediaPipe
  replacement ([README](https://github.com/warmshao/FasterLivePortrait)).

**Audio variants:** JoyVASA generates LivePortrait-space motion from audio, covers human and animal
modes, and is MIT licensed ([README](https://github.com/jdh-algo/JoyVASA),
[LICENSE](https://github.com/jdh-algo/JoyVASA/blob/main/LICENSE)). It was tested on an RTX 4060 Laptop
with 8 GB, but its README gives no FPS and I found no streaming figure. FasterLivePortrait integrates
it. It uses the same renderer as Ditto, and Ditto is already optimised here, so **there is no reason
to switch** (consistent with the [earlier note](realtime-avatar-stack-sources.md)).

## 3. Ditto: would full-face output remove the seam?

Ditto builds its motion space on LivePortrait and reuses LivePortrait's motion extractor, appearance
extractor and face renderer ([paper §3.1](https://arxiv.org/html/2411.19509v3)). A search summary
claiming otherwise was wrong and has been discarded.

**The seam, plainly.** Whole-head output removes the mouth-versus-face split: mouth, cheeks and eyes
would all come from one decoder pass. It does not make the frame one image. The generated head is
still pasted into the source video frame, leaving a soft boundary at the hairline and neck. The paper
describes this as stitching the head onto the original body
([§4.4](https://arxiv.org/html/2411.19509v3)). That boundary is hair or skin against matching source
pixels rather than two styles of mouth, so **Inference:** it should be far less objectionable, but
this is unproven.

**What it costs, from local measurements:**

| Item | Partial mouth decoder | Full decoder | Source |
|---|---|---:|---|
| Whole renderer, mean | 44.48 ms | 48.48 ms | [ROI report](../../output/avatar-quality-review/neural-fps/tensorrt-hybrid-roi.json), [full report](../../output/avatar-quality-review/neural-fps/tensorrt-hybrid-ampnorm.json) |
| Speed | Measured 15.6 generated FPS live | **Inference:** about 14 FPS, scaling by render time | [evaluation](../evals/avatar-neural-throughput.md) |
| Accuracy to PyTorch | Passes on displayed mouth only | Passes full-face: worst MAE 0.09346 RGB255 | [evaluation](../evals/avatar-neural-throughput.md) |
| Upper-face change from source | Exactly zero | 4.06/255 mean RGB MAE | [evaluation](../evals/avatar-state-appearance.md) |

- **Speed cost is small:** about 4 ms per frame. **The 15–20 generated FPS target would stay unmet.** The
  current path sits at its bottom edge at 15.6, and earlier live runs measured 14.2–14.6
  ([evaluation](../evals/avatar-opening-limit.md)).
- **Visual cost is the real one.** The compositor exists because whole-face replacement changed
  eyes, hair, cheeks and texture ([evaluation](../evals/avatar-state-appearance.md)). The 4.06/255
  figure was measured on the semi-realistic source. **Inference:** flat anime shading may hide it
  better or show it worse, and only a test can say.
- **Rest needs new logic.** The kiosk cuts back to source pixels after 280 ms without voiced PCM
  ([evaluation](../evals/avatar-neural-throughput.md)). With whole-head output, that cut would
  visibly swap the entire face. **Inference:** it needs a crossfade or a generated neutral rest,
  and the second costs GPU time during silence.
- **`renderer_backend: tensorrt` alone is not enough.** It selects the full decoder, but
  [`_present_at`](../../scripts/ditto_realtime.py) still calls `composite_mouth`. A head-mask
  compositor must be added. Prepared caches bind source hashes, so a new source also needs the
  preparation step rerun ([evaluation](../evals/avatar-neural-throughput.md)).
- **Eyes and pose:** the kiosk uses `use_d_keys=("exp",)` and `drive_eye=False`
  ([`ditto_realtime.py`](../../scripts/ditto_realtime.py)). Head pose and blinks therefore come from
  the source clip, while audio drives expression. That suits this clip, whose head and arms already
  move.

**Anime evidence for Ditto is thin.** The paper reports "stable performance across diverse portrait
styles" ([§4.4](https://arxiv.org/html/2411.19509v3)), and its examples are not named as anime. The
only GitHub issue in its repo matching "anime", [#83](https://github.com/antgroup/ditto-talkinghead/issues/83),
is about fine-tuning artefacts on HDTF. "cartoon" matched none. **The kiosk has only run Ditto on the semi-realistic standing clip**
(`.runtime/trend-avatar.json`), not on the anime art. The checkpoint list names `insightface_det.onnx`
([README](https://github.com/antgroup/ditto-talkinghead)), so LivePortrait's detection failure may apply.
Separately, that is a commercial licence concern for the **current 3D mode** too.

**Anime pacing.** Community documentation notes that early-2000s anime used about 12 FPS for new
cels ([Extras README](https://github.com/SillyTavern/SillyTavern-Extras/blob/main/talkinghead/README.md)).
**Inference:** 14 generated FPS may read as on-model for this art, where it reads as choppy on a
realistic face. This is an argument to test, not evidence.

## 4. 2026 streaming diffusion models

These are class A: one forward pass generates the whole square from reference and audio.

### LeapTalk (arXiv 2608.00079, July 2026)

- **Input and method:** reference image plus speech, one network evaluation per chunk, built on a
  FlashHead base. Wav2vec audio features ([README](https://github.com/zhangrongxiang/LeapTalk),
  [paper](https://arxiv.org/html/2608.00079v1)).
- **Licence:** repo and weights Apache-2.0; the owner confirmed commercial use of the LoRA and
  `audio_proj` weights and asked for attribution
  ([issue #8](https://github.com/zhangrongxiang/LeapTalk/issues/8)). The Lite decoder is TAEHV, which
  avoids FlashHead Lite's Open-RAIL-M LTX VAE.
- **Speed, paper:** 200 FPS Lite on H200. Single A100 at 512×512: 104 FPS. At 384×384: 191. At 256×256:
  476 ([paper, Table 9](https://arxiv.org/html/2608.00079v1)). The owner says RTX 4090 is close to A100
  ([issue #8](https://github.com/zhangrongxiang/LeapTalk/issues/8)).
- **Speed, third party, end to end on RTX 4090:** RTF 0.41 at 1 step, 0.73 at 2 steps. 4 steps gives RTF
  1.37 with no sync gain ([issue #8](https://github.com/zhangrongxiang/LeapTalk/issues/8)).
- **VRAM, third party:** a warm renderer peaks at about **11.8 GB at 512×512** and 20.7 GB at 576×1024,
  measured on a 96 GB card ([issue #7](https://github.com/zhangrongxiang/LeapTalk/issues/7)). A 96 GB
  card imposes no pressure, so the true minimum may be lower. FlashHead's model file alone is 6.0–6.1 GB
  ([file list](https://huggingface.co/Soul-AILab/SoulX-FlashHead-1_3B)).
- **Streaming latency:** stream code uses `frame_num − 5`, so a 33-frame chunk gives **28 new frames, 1.12 s
  of audio** ([`leaptalk_stream.py`](https://github.com/zhangrongxiang/LeapTalk/blob/main/leaptalk_stream.py)).
  Issue #7 confirms 1.12 s chunks with first frame at about 0.77 s on an RTX PRO 6000. Paper Table 8 is
  consistent with this: FPS × T_gen gives 4, 12 and 28 new frames for chunks of 9, 17 and 33. A 17-frame
  chunk means 0.48 s of audio per chunk at 82 FPS on A100, and a 9-frame chunk 0.16 s at 45.4 FPS.
- **Anime evidence:** qualitative only. The paper says it preserves identity and visual style on "cartoons,
  sculptures, and oil paintings." I inspected Figure 10: the "cartoon" is a heavily shaded 3D-style game
  character, **not flat cel anime** ([paper](https://arxiv.org/html/2608.00079v1)).
- **Language, directly relevant to Vietnamese:** the authors validated only Chinese and English
  ([issue #1](https://github.com/zhangrongxiang/LeapTalk/issues/1)). At 2 steps, a third party
  measured LSE-C 6.96 on German against 7.47 on an English translation of the same answer, and suspected the
  English wav2vec encoder. A fine-tune then helped: 290 clips from six portraits rendered through FlashHead Pro
  as teacher, on one H200, reached 8.25 on four held-out German answers at 2 steps and RTF 0.73 on RTX 4090
  ([issue #8](https://github.com/zhangrongxiang/LeapTalk/issues/8)). The owner estimates 1–2 days of H200 for a
  portrait fine-tune. These are small samples. The same route could plausibly adapt to Vietnamese (**Inference**).
- **Lips:** TAEHV's "main degradation is slight blurriness in fine regions such as lips"
  ([paper](https://arxiv.org/html/2608.00079v1)).
- **Interruption:** frames arrive in whole chunks. Queued frames can be dropped instantly, but an in-flight
  chunk keeps the GPU until it finishes (**Inference** from the stream design).

**Inference, on a 3060 at 512×512:**

- **Speed:** using the 4–5× calibration, about 21–26 FPS pure generation from the paper figure, or about
  12–15 FPS end to end from RTF 0.41. Audio chunks fix the frame count, so anything under 25 FPS falls
  behind speech. 2 steps, which the non-English results favour, is worse. Lower resolutions leave margin, but the
  owner says quality off the 512×512 training shape is not guaranteed, speaking of 576×1024
  ([issue #7](https://github.com/zhangrongxiang/LeapTalk/issues/7)).
- **Memory:** 11.8 GB + about 3.3 GB exceeds 12 GB, even with Ditto stopped.
- **Latency:** native audio arrives paced in real time, so speech must be held for the chunk length plus
  generation. Default chunks add more than 1.12 s to the 1.0–2.0 s the kiosk already spends before first audio.

**Conclusion: not viable on a 3060 on published figures, mainly for memory and speech delay, though no 3060 run
exists. First choice if the GPU is upgraded.**

### SoulX-FlashHead (arXiv 2602.07449, February 2026)

- Audio-direct, 512×512, 1.3-billion-parameter model. Lite is claimed at 96 FPS on one RTX 4090
  ([paper](https://arxiv.org/abs/2602.07449), [README](https://github.com/Soul-AILab/SoulX-FlashHead)).
- **The 96 FPS figure should not be relied on.** The evaluation section says FPS was measured on an H20, not a 4090
  ([paper](https://arxiv.org/html/2602.07449v3)). LeapTalk's paper lists it at 14.42 FPS for 4 steps
  ([Table 1](https://arxiv.org/html/2608.00079v1)). A user reports 62 s for a 52 s clip on a 4090 with
  crop, super-resolution and paste ([issue #18](https://github.com/Soul-AILab/SoulX-FlashHead/issues/18)).
  A third party measured Lite at RTF 0.64 on RTX 4090 ([LeapTalk #8](https://github.com/zhangrongxiang/LeapTalk/issues/8)).
  **Inference:** RTF of about 2.6–3.2 on a 3060.
- About 6 GB per instance on an RTX 5090 ([issue #83](https://github.com/Soul-AILab/SoulX-FlashHead/issues/83), model not
  stated), and that report also cites 1–2 s audio/video desync while streaming.
- Lite users report blurry mouths and disappearing teeth
  ([issue #21](https://github.com/Soul-AILab/SoulX-FlashHead/issues/21)), and 5 of 10 test images distorted
  ([issue #73](https://github.com/Soul-AILab/SoulX-FlashHead/issues/73)). No anime evidence was found.
- Licences: DiT and Wan VAE Apache-2.0; Lite's LTX VAE Open-RAIL-M
  ([model page](https://huggingface.co/Soul-AILab/SoulX-FlashHead-1_3B)).

### Others found

| Method | Finding | Verdict for a 3060 |
|---|---|---|
| [IMTalker](https://arxiv.org/html/2511.22167v1) | 42 FPS audio-driven on RTX 4090 at 512×512; "accepts diverse portrait styles"; no stylised evaluation; [code and weights released](https://github.com/cbsjtu01/IMTalker), repo Apache-2.0 per GitHub | **Inference:** 8–11 FPS. Streaming not described. |
| [AvatarForcing](https://arxiv.org/abs/2603.14331) | 34 ms/frame with a 1.3B student; hardware not stated on the abstract page | Unknown; no code found |
| [Live Avatar](https://github.com/Alibaba-Quark/LiveAvatar) | 45 FPS on multi-card H800; single GPU needs at least 80 GB VRAM, FP8 48 GB | Ruled out |
| [SoulX-FlashTalk](https://github.com/Soul-AILab/SoulX-FlashTalk) | 32 FPS on 8×H800 | Ruled out |
| TalkingMachines | See section 1 | Ruled out |

## 5. Older baselines

| Method | Facts | Status here |
|---|---|---|
| **MuseTalk** | Lip-sync on a 256×256 face region; 30+ FPS on Tesla V100; own weights free for any purpose, other dependencies carry their own licences ([README](https://github.com/TMElyralab/MuseTalk)) | Class C seam. Native run **rejected** by the user for naturalness ([evaluation](../evals/realtime-avatar.md)). Not re-recommended. |
| **Wav2Lip** | Open model personal/research/non-commercial; trained on LRS2 ([README](https://github.com/Rudrabha/Wav2Lip)) | Class C seam, licence blocks use, **visually rejected** ([evaluation](../evals/realtime-avatar.md)). Not re-recommended. |
| **SadTalker** | Licence now Apache-2.0 ([README](https://github.com/OpenTalker/SadTalker)); 2.17 FPS in FlashHead's comparison ([paper](https://arxiv.org/html/2602.07449v3)) | Not real time. No anime validation found. |
| **LiteAvatar** | 30 FPS on CPU only; mouth parameters from a Chinese ASR model's features; a light 2D face generator ([README](https://github.com/HumanAIGC/lite-avatar)); MIT per GitHub | Only for gallery avatars. [Custom avatar training](https://github.com/HumanAIGC/lite-avatar/issues/26) is undocumented, so Trend cannot be used today. Class C by description. |

## 6. Comparison

"3060?" is measured only where it says so. Interruption entries are **Inference** from each design.

| Method | Audio direct? | One image? | Anime evidence | Speed | VRAM | Min. latency | Interruption | Commercial licence |
|---|---|---|---|---|---|---|---|---|
| **Ditto whole-head** | Yes | Class B: head yes, paste at hair/neck | Weak; renderer trained on styled art; never run on Trend | **3060 measured:** 15.6 FPS partial, ~14 full (**Inference**) | 4,098 MiB peak, measured | 160 ms stride + 80 ms context | Existing epoch reset; needs crossfade | Apache code; **replace InsightFace** |
| THA3 | No, needs vowels | Class A | **Strongest** | 3060: 9–10 FPS; 3070 Ti mobile: <25 to 40–50 | ~520 MB | Per frame, plus vowel analysis | Next frame | **Yes, CC BY** |
| THA4 student | No | Class A | **Strongest** | 22 ms on GTX 1080 Ti | Not published | Per frame | Next frame | **Blocked:** NC teacher |
| LivePortrait + JoyVASA | Via JoyVASA | Class B | As Ditto | 30+ FPS on 3090, renderer only | Not published | Not published | Unknown | MIT; replace InsightFace |
| LeapTalk | Yes | Class A, inside square | Qualitative, non-anime "cartoon" | **4090:** RTF 0.41; 3060 not measured | ~11.8 GB | ≥1.12 s default; 0.48 s at 17 frames | Drop queue; chunk finishes | **Yes, Apache** |
| FlashHead Lite | Yes | Class A, inside square | None | 4090: RTF 0.64 | ~6 GB, unclear | About 1 s chunks | Drop queue | Open-RAIL-M VAE |
| IMTalker | Yes | Class A | None | 4090: 42 FPS | Not published | Not described | Unknown | Apache per GitHub |
| MuseTalk | Yes | **Class C** | None | V100: 30+ FPS | Not checked | Not checked | Queue reset | Mixed; user-rejected |

## 7. Rig and viseme fallback, short

Outside the talking-head family. Use only if both neural options fail. A rig avoids the user's complaint in a
different way: one drawn set of layers deforms together, so the mouth and face share one style. **Inference:**
that is why VTuber products use it.

| Option | Facts | Cost to reach Trend |
|---|---|---|
| **Live2D Cubism** | Web SDK is WebGL/TypeScript ([SDK](https://www.live2d.com/en/sdk/about/)). Lip-sync sets `ParamMouthOpenY` from volume, values 0–1 ([manual](https://docs.live2d.com/en/cubism-sdk-manual/lipsync/)). Vowels are rig work, not SDK work. Small-scale businesses under ¥10M latest sales are exempt ([help](https://help.live2d.com/en/sdk/sdk_007/)); otherwise a per-work release licence, signed a month before release; events and embedded use: contact Live2D ([licence](https://www.live2d.com/en/sdk/license/)). `pixi-live2d-display` is MIT, targets PixiJS 6 ([repo](https://github.com/guansss/pixi-live2d-display)). | Needs layers and a rig. See-through decomposes one image into up to 23 layers but is explicitly **not** a full Image-to-Live2D pipeline ([repo](https://github.com/shitagaki-lab/see-through)). Rigger needed. |
| **Rive** | MIT runtimes, no runtime fees; paid seat from $9 removes export splash ([pricing](https://rive.app/pricing)). | Mouth poses and mesh rig must be built by hand |
| **Spine** | Runtime use requires an editor licence; currently $379 Professional under $500K revenue, Enterprise above ([purchase](https://esotericsoftware.com/spine-purchase)). | As Rive, layers needed |
| **Inochi2D** | BSD-2-Clause, D language; web via Wasm with a patched runtime ([repo](https://github.com/Inochi2D/inochi2d)). | Web immature for a kiosk |

| Audio-to-viseme | Facts | Use |
|---|---|---|
| **wLipSync** | MFCC in AudioWorklet/WASM; any Web Audio source; requires a calibrated profile, currently made in Unity; MIT ([repo](https://github.com/mrxz/wLipSync)) | **Chosen for the THA3 fallback** |
| **uLipSync** | Unity; MFCC with per-phoneme calibration; labels are arbitrary, MIT ([repo](https://github.com/hecomi/uLipSync)). VTube Studio's Advanced Lipsync uses it and outputs `VoiceA/I/U/E/O`, and recommends it over the OVR-based mode ([wiki](https://github.com/DenchiSoft/VTubeStudio/wiki/Lipsync)) | The proven practice |
| **Rhubarb** | File-based; phonetic recogniser is language-independent but less precise ([repo](https://github.com/DanielSWolf/rhubarb-lip-sync)) | Fails streaming |
| **Meta OVR** | SDK terms limit use to approved hardware unless documentation says otherwise ([licence](https://developers.meta.com/horizon/licenses/oculussdk/)) | Avoid; legacy per VTube Studio |
| **HeadTTS** | Kokoro TTS with phoneme timestamps ([repo](https://github.com/met4citizen/HeadTTS)) | Fails: needs its own TTS |
| **Azure visemes** | Cloud service, not reviewed further | Fails: new cloud service |

## Recommendation: Ditto whole-head on the anime clip

**Why this one:** it is the only option with measured real-time streaming on this GPU, it costs nothing new,
latency is known, and interruption machinery exists. It also fails fast: step 1 answers the anime question
in about a day. Its risk is visual, not engineering.

| Step | Work | Pass condition |
|---|---|---|
| 1. Anime gate | With the kiosk stopped, offline, render one Vietnamese phrase with `Woman_greeting_customers_at_counter_b58d415e_1080p.mp4` and with `trend-character.jpg`, using the full decoder and existing weights. Nothing is installed. | Face registers. **User accepts mouth shapes and face.** If not, stop and go to the fallback. |
| 2. Detector | If registration fails or to clear the licence, replace InsightFace detection with MediaPipe, which already tracks this clip. | Registration on all source frames; no InsightFace models in the path |
| 3. Source | Pick a calm frame range, because the clip's prerecorded speech leaks into source-relative expression. Rebuild the 2D avatar cache. | Mouth still at silence |
| 4. Compositor | Add a head-mask mode next to `composite_mouth`, with hair and neck feathering, using the `tensorrt` decoder. | No visible boundary at normal viewing distance |
| 5. Rest and interruption | Crossfade generated-to-source on rest, cut, and epoch reset, or render a generated neutral rest. | Mouth stops within one frame and the whole-face change is not a visible pop |
| 6. Kiosk integration | Serve this through the existing avatar stream for the Settings → Nhân vật 2D choice. Keep 3D. Retire the atlas path after acceptance. | Existing browser and guest-generation regressions pass |
| 7. Measure | Generated and changed-pose FPS, VRAM with Fusion live, physical acoustic sync, several Vietnamese phrases and voices. | Reported separately, without lowering the 15–20 FPS target silently |

- **User supplies:** a visual verdict at step 1 and step 4; a window with no guests for GPU work.
- **User pays:** nothing. No key, cloud voice or rigger. Stays on ChatGPT/Codex native login.
- **Effort (my estimate):** about 1 day for step 1; about 1–1.5 weeks in total if it passes.

## Fallback: THA3 with streaming vowel weights

Take this if step 1 fails on anime quality.

| Step | Work |
|---|---|
| 1. Benchmark | Run `separable_half` on the 3060 to resolve the 9–10 versus 40–50 FPS conflict. **If below about 20 FPS with Fusion live, stop.** |
| 2. Art | Pick an open-mouth video frame; matte it to 512×512 RGBA, about 20 minutes per character by [the Extras guide](https://github.com/SillyTavern/SillyTavern-Extras/blob/main/talkinghead/README.md). Inspect the 128 px head. |
| 3. Audio to mouth | Run wLipSync on output PCM. Calibrate Vietnamese `a i u e o` and silence on each selectable voice. Map weights to `mouth_aaa/iii/uuu/eee/ooo`. **Inference:** the labels line up directly. |
| 4. Natural motion | Drive blinks, `breathing`, small `head_x/y` and `neck_z` from idle curves and speech energy. Silence and interruption set mouth morphs to rest. |
| 5. Upscale and serve | Anime4K, then the existing stream. |

- **Unity is only needed once**, to produce the wLipSync profile, as the project has no profile builder.
- **User supplies:** approval of the chosen open-mouth art and the small head.
- **User pays:** nothing; add a CC BY attribution.
- **Effort (my estimate):** about 2 weeks.
- **Later upgrade:** a THA4 student would improve speed if the author grants commercial permission. Ask first; training
  takes about 30 hours on far stronger hardware than a 3060.

## If the GPU changes

An RTX 4090-class card makes **LeapTalk at 2 steps with a Vietnamese fine-tune** the leading whole-frame option,
at RTF 0.73 on that card. It still needs an anime test and a smaller chunk to control speech delay. A paid H200
rental for fine-tuning is a one-off training cost, not a voice service.

## Top risks

1. **Anime rendering may simply look wrong.** Ditto's motion was learned from real faces, and an anime mouth is a thin
   line with no lip volume, so the decoder must invent the interior. **Inference**; step 1 tests this.
2. **The softness complaint returns.** Whole-head output is the configuration the user reported as softer on 2026-10-30.
3. **Mouth anatomy has never been accepted.** Ditto's teeth and opening remain unaccepted
   ([evaluation](../evals/avatar-neural-throughput.md)), and bounded opening is pending review.
4. **Below target smoothness.** About 14 generated and fewer distinct poses per second.
5. **The clip's own speech** leaks through source-relative expression and may fight the audio.
6. **Licences:** InsightFace's non-commercial models affect the current 3D mode too and should be fixed regardless. A
   sparkle mark is visible at the lower right of `trend-character.jpg`; confirm rights in the AI-generated source.
7. **Shared GPU:** Ditto and Fusion together are untested under sustained live load.
8. **Vietnamese accuracy is unmeasured for every option.**

## Verified, inferred and unverified

**Verified from primary sources or local artifacts:** licences as quoted; published speeds on the stated hardware;
LeapTalk's 28-frame stream slice from source code; local Ditto rates and VRAM; Figure 10's contents by inspection.

**Third-party measurements, not independently checked:** LeapTalk #7 and #8, FlashHead #18, #21, #73, #83. Each is
few-sample; the LeapTalk comparison uses one portrait and one seed per setting.

**My inference, labelled inline:** every 3060 estimate for methods not run here, the 4–5× calibration, about 14 FPS for
full-decoder Ditto, about 3.3 GB of non-avatar VRAM, THA head resolution, and all effort estimates.

**Could not verify:**

- Any method's result on Trend's art, including Ditto. Nothing was run.
- Any RTX 3060 measurement for LeapTalk, FlashHead, IMTalker, JoyVASA, or Ditto's full decoder in live streaming.
- A true minimum VRAM for LeapTalk. FP16 is a code option, but I found no measurement.
- Which THA3 model variant the 9–10 FPS report used.
- Commercial status of the TAEHV checkpoint, as the owner's confirmation names LoRA and `audio_proj` weights only;
  and of a THA4 student.
- Anything cel-anime in LeapTalk or FlashHead. The HF Spaces were not used, since that would upload the character
  art to a third party without consent.
- Current Live2D fees, which the licence page does not list, and whether a commercial kiosk is treated as an
  event/embedded case.
- GitHub MCP tools were unavailable, so public GitHub pages and REST were used instead.
