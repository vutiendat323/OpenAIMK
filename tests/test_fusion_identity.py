"""Exercise the installed Audio gate and native guard without loading models."""

import json
import os
import subprocess
from pathlib import Path

import pytest


def test_fusion_keeps_duplicate_customer_slots_without_separation():
    root = Path(__file__).resolve().parents[1]
    python = Path(os.environ.get("TREND_AV_PYTHON", root / "Visual/.venv/bin/python"))
    if not python.is_file():
        pytest.skip("Kiosk perception Python environment needed")
    result = subprocess.run(
        [
            str(python),
            "-B",
            "-c",
            """
import json
import time
from audio.domain.evidence import FaceTrackBuffer
from audio.domain.fusion import FusionGate
from audio.domain.settings import SpeakerSettings
from trendcoffee.av_transport import accepted_pcm

now = time.time()
faces = FaceTrackBuffer()
faces.set_asd_stream("fixture")
faces.use_pushed_asd(True)
for k in range(-2, 25):
    faces.add({"event": "faces", "ts": now + k * 0.1, "tracks": [
        {"track_id": 7, "distance_m": 0.5, "mouth_activity": 0.8}
    ]})
faces.add_asd({"stream_id": "fixture", "track_id": 7, "t0": now - 0.9,
               "frame_secs": 0.04, "probabilities": [0.9] * 25})
settings = SpeakerSettings(enabled=True, diarizer="sortformer", vision_faces=True,
                           vision_asd=True, identity="fusion")
gate = FusionGate(settings, faces, fsm_state=lambda: "active")
gate.lock.observe_fsm("active", now - 1)
for k in range(6):
    gate.lock.observe_row(now - 0.45 + k * 0.08, [0], anchor=7, anchor_asd_accept=True)
gate.lock.target_slots.add(1)
pcm = b"\x01\x02" * 1280
def decision(row):
    for k in range(3):
        verdict = gate.frame(row, bot_speaking=False, t=now + k * 0.001,
                             asd_stream_id="fixture")
    forwarded = accepted_pcm(pcm, verdict=verdict.value, reason="kept",
                             locked=gate.locked, fresh=True)
    return verdict.value, forwarded == pcm
duplicate = decision([0.9, 0.9, 0, 0])
other = decision([0.9, 0.9, 0.9, 0])
stale = accepted_pcm(pcm, verdict="ACCEPT", reason="kept", locked=True, fresh=False)
print(json.dumps({"duplicate": duplicate, "other": other, "stale_silenced": not any(stale)}))
""",
        ],
        cwd=root,
        env={
            **os.environ,
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": os.pathsep.join([str(root / "Audio/src"), str(root)]),
        },
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    data = json.loads(result.stdout)
    assert data["duplicate"] == ["ACCEPT", True]
    assert data["other"] == ["UNCERTAIN", False]
    assert data["stale_silenced"] is True


def test_quiet_prefix_and_tail_survive_the_complete_confirmed_owner_boundary():
    root = Path(__file__).resolve().parents[1]
    python = Path(os.environ.get("TREND_AV_PYTHON", root / "Visual/.venv/bin/python"))
    if not python.is_file():
        pytest.skip("Kiosk perception environment needed")
    result = subprocess.run(
        [
            str(python),
            "-c",
            """
from audio.application.stream import SpeakerStream
from audio.domain.fusion import FusionGate
from audio.domain.settings import SpeakerSettings
from audio.domain.evidence import FaceTrackBuffer
from audio.domain.verdict import Verdict
from trendcoffee.av_transport import FusionPreroll
class Diarizer:
    frame_secs=.08
    chunk_samples=1280
gate=FusionGate(SpeakerSettings(identity='fusion'),FaceTrackBuffer(),fsm_state=lambda:'active')
stream=SpeakerStream(diarizer=Diarizer(),gate=gate,stt_delay_secs=.7)
# Model-verdict trace for quiet 'chào bạn tôi' / 'cho tôi', a clear middle,
# then quiet 'đỡ' / 'đi'. This tests byte preservation, not an STT score.
rows=[None]*3+[Verdict.ACCEPT]*5+[None]*2
for n,row in enumerate(rows):
    stream._remember_verdict(100+n*.08,row,track_id=7 if row is Verdict.ACCEPT else None)
buffer=FusionPreroll();source=[];received=[]
for n in range(len(rows)):
    pcm=bytes([n+1,0])*1280;source.append(pcm)
    t=100+n*.08+.04
    verdict,reason=stream._stt_decision(t)
    output=buffer.push(pcm=pcm,verdict=verdict,reason=reason,
        track_id=stream._track_at(t,reason),locked_track=7 if n>=6 else None,
        owner_track=7,fresh=True,now=n*.08)
    received.extend(data for data,_ in output if any(data))
assert b''.join(source)==b''.join(received), 'word edge samples were silenced or reordered'
print('preserved all 10 chunks including prefix and tail')
""",
        ],
        cwd=root,
        env={**os.environ, "PYTHONPATH": os.pathsep.join([str(root / "Audio/src"), str(root)])},
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    assert "preserved all 10 chunks" in result.stdout
