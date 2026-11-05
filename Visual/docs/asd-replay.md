# Saved A/V replay (operator opt-in)

This tool only reads existing files. It does not capture media or start services.
No labeled calibration or held-out clips have been supplied. The synthetic tests
validate code, not model quality. Do not promote their +0.20 s offset to live use.

The operator must separately capture a calibration clip and a different held-out
clip, preserving synchronized PCM16 mono 16 kHz audio and selected confirmed
face crops (112x112 uint8). Record sample-count audio timestamps and immediate
post-camera-read timestamps on the same host timeline. Keep files local. Label
per-track speech/silence intervals and scenarios: speaking, silence, head_motion,
silent_video, speaking_video. Missing face intervals remain unknown.

Example manifest (paths relative to manifest):

```json
{"version":1,"audio_wav":"audio.wav","audio_t0":1790000000.0,
 "crops_npz":"crops.npz","enhancer":"none","split":"calibration",
 "labels":[{"track_id":17,"start":1790000000.0,"end":1790000002.0,
 "speaking":true,"scenario":"speaking"}]}
```

`crops.npz` contains `timestamps[N]` (finite numeric), `track_ids[N]` (integers),
`crops[N,112,112]` (uint8), with no pickled objects. Labels use original audio time.
Positive offset means later video. Audio is never circularly shifted.

```sh
PYTHONPATH=/home/robber/Work/jarvis-pr9/asd-deps python3 tools/asd_replay.py /path/calibration/manifest.json --offset-sweep --output /path/calibration-report.json
PYTHONPATH=/home/robber/Work/jarvis-pr9/asd-deps python3 tools/asd_replay.py /path/held-out/manifest.json --offset-secs CALIBRATED_VALUE --output /path/held-out-report.json
```

Set held-out manifest `split` to `held_out`; sweeps are refused. Defaults use
`~/.cache/openjarvis/light_asd/light_asd.onnx`, CUDA EP with TF32 disabled and CPU
fallback. Use `--model PATH` and `--device cpu` only when explicitly needed.
Reports score each labeled 40 ms bin once, including unknown bins in coverage;
unknown is never silence. Inference latency includes preprocessing. Windows use
the runtime AVBuffer but are retrospective, so these numbers do not establish
live scheduling, transport age, deadline or gate performance.

For an explicit subsequent live trial, copy the operator's Vision config and set
`asd_provider: light_asd`, `asd_model_path` to the artifact above, and
`asd_audio_offset_secs` to that mode's calibration result. Keep checked-in defaults
off. Calibrate RNNoise and unenhanced media independently with identical labels.
No command here starts the stack or records microphone/camera data.
