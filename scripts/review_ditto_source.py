"""Evaluate Ditto directly from an original clip, without MuseTalk inputs."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def wait_for_idle():
    while True:
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:8080/api/kiosk/status", timeout=2
            ) as response:
                active = json.load(response).get("session_active", False)
        except OSError:
            active = False
        if not active:
            return
        time.sleep(1)


def validate_render(video, audio):
    """Upstream muxing ignores exit status; reject missing or truncated outputs."""
    import wave

    with wave.open(str(audio), "rb") as wav:
        duration = wav.getnframes() / wav.getframerate()
    probe = json.loads(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(video)]
        )
    )
    video_stream = next((s for s in probe["streams"] if s["codec_type"] == "video"), None)
    audio_stream = next((s for s in probe["streams"] if s["codec_type"] == "audio"), None)
    if not video_stream or not audio_stream:
        raise RuntimeError(f"Missing video/audio stream: {video}")
    frames = int(video_stream.get("nb_frames", 0))
    if abs(frames / 25 - duration) > 0.08:
        raise RuntimeError(f"Truncated video: {frames} frames for {duration}s audio")
    if abs(float(audio_stream.get("duration", 0)) - duration) > 0.08:
        raise RuntimeError(f"Truncated audio: {video}")
    return dict(frames=frames, audio_seconds=duration)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--relative-motion", action="store_true")
    parser.add_argument("--silence-control", action="store_true")
    parser.add_argument("--emotion", type=int, choices=range(8), default=4)
    parser.add_argument("--case", choices=("source", "greeting"), action="append")
    parser.add_argument("--torch-optimized", action="store_true")
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    checkout = ROOT / ".runtime/Ditto"
    sys.path[:0] = [str(ROOT / ".runtime/ditto-packages"), str(checkout)]
    wait_for_idle()
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(source),
            "-an",
            "-vf",
            "fps=25",
            "-c:v",
            "ffv1",
            str(output / "original-25fps.mkv"),
        ],
        check=True,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(source),
            "-vn",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(output / "original.wav"),
        ],
        check=True,
    )
    import torch

    torch.set_num_threads(4)
    torch.set_grad_enabled(False)
    import onnxruntime as ort

    original_session = ort.InferenceSession

    def limited_session(*args, **kwargs):
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        options.add_session_config_entry("session.intra_op.allow_spinning", "0")
        kwargs.setdefault("sess_options", options)
        return original_session(*args, **kwargs)

    ort.InferenceSession = limited_session
    os.chdir(checkout)
    from inference import run, seed_everything
    from stream_pipeline_offline import StreamSDK

    seed_everything(17)
    started = time.monotonic()
    sdk = StreamSDK(
        str(checkout / "checkpoints/ditto_cfg/v0.4_hubert_cfg_pytorch.pkl"),
        str(checkout / "checkpoints/ditto_pytorch"),
    )
    initialization_seconds = time.monotonic() - started
    renderer = None
    if args.torch_optimized:
        from ditto_torch import install_fused_renderer

        renderer = install_fused_renderer(sdk)
    # Remove the upstream example actor's reference expressions/eye trajectory.
    # Video source retains its original pose; only expressions are audio-driven.
    setup = dict(
        max_size=1280,
        ch_info=None,
        delta_eye_arr=None,
        overall_ctrl_info={},
        ctrl_info={},
        emo=args.emotion,
        drive_eye=False,
        use_d_keys=("exp",),
        relative_d=args.relative_motion,
        online_mode=False,
    )
    results = []
    cases = [
        ("source", output / "original.wav"),
        ("greeting", ROOT / "frontend/public/voice/default/greeting.wav"),
    ]
    if args.case:
        cases = [(label, audio) for label, audio in cases if label in args.case]
    if args.silence_control:
        import wave

        silence = output / "silence.wav"
        with wave.open(str(silence), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(bytes(16000 * 2 * 4))
        cases.append(("silence", silence))
    for label, audio in cases:
        wait_for_idle()
        if renderer:
            renderer.frame_ms.clear()
        started = time.monotonic()
        run(
            sdk,
            str(audio),
            str(output / "original-25fps.mkv"),
            str(output / f"{label}-ditto.mp4"),
            more_kwargs={"setup_kwargs": dict(setup)},
        )
        wall_seconds = time.monotonic() - started
        validation = validate_render(output / f"{label}-ditto.mp4", audio)
        result = dict(audio=label, wall_seconds=wall_seconds, **validation)
        if renderer:
            result["renderer"] = renderer.statistics()
        results.append(result)
    # Close the native worker while Python modules are still alive.
    sdk.avatar_registrar.source2info.landmark478.model.detector.close()
    (output / "render.json").write_text(
        json.dumps(
            dict(
                source=str(source),
                source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                engine="Ditto / LivePortrait-derived renderer",
                muse_inputs=False,
                torch_optimized=args.torch_optimized,
                initialization_seconds=initialization_seconds,
                results=results,
                settings=setup,
                activated=False,
            ),
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
