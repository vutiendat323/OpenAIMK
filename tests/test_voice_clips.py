"""Prepared native speech must be complete, intelligible and voice-specific."""

import base64
import hashlib
import json
import wave

import pytest

from trendcoffee.kiosk import BOUNDARY_TEXT, VOICE_CLIPS


def packet(pcm=b"\x00\x01" * 480):
    return {"data": base64.b64encode(pcm).decode(), "sampleRate": 48000, "numChannels": 1}


def test_rendered_clip_requires_the_complete_expected_sentence():
    from scripts.prepare_voice_clips import validate_capture

    text = BOUNDARY_TEXT["greeting"]
    assert validate_capture(text, text, [packet()]) == b"\x00\x01" * 480
    for transcript in ("", "Chào bạn", text + " Bạn có khỏe không?"):
        with pytest.raises(ValueError, match="transcript"):
            validate_capture(text, transcript, [packet()])


@pytest.mark.parametrize(
    "packets",
    [
        [],
        [packet(bytes(960))],
        [packet(b"x")],
        [packet(), {**packet(), "sampleRate": 24000}],
        [packet(b"\x00\x01" * 240000)],
    ],
)
def test_rendered_clip_rejects_empty_silent_or_inconsistent_audio(packets):
    from scripts.prepare_voice_clips import validate_capture

    text = BOUNDARY_TEXT["greeting"]
    with pytest.raises(ValueError, match="audio"):
        validate_capture(text, text, packets)


def test_preparation_does_not_reuse_an_oversized_existing_clip(tmp_path, monkeypatch):
    from scripts import prepare_voice_clips as prepare

    monkeypatch.setattr(prepare, "VOICE_CLIPS", tmp_path)
    directory = tmp_path / "maple"
    directory.mkdir()
    pcm = b"\x00\x01" * 240000
    with wave.open(str(directory / "greeting.wav"), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(48000)
        target.writeframes(pcm)
    record = {"text": BOUNDARY_TEXT["greeting"], "sha256": hashlib.sha256(pcm).hexdigest()}
    assert not prepare.existing_clip("maple", "greeting", record)


def test_all_available_voices_have_verified_native_boundary_recordings():
    voices = {
        "default",
        "juniper",
        "maple",
        "spruce",
        "ember",
        "vale",
        "breeze",
        "arbor",
        "sol",
        "cove",
        "aube",
        "bubbie",
        "haetsal",
        "hanul",
        "himari",
        "leher",
        "miko",
        "neer",
        "porto",
        "rindo",
        "rio",
        "rivage",
        "selva",
        "sonna",
        "tinta",
        "viola",
    }
    manifest = json.loads((VOICE_CLIPS / "catalog.json").read_text())
    assert set(manifest["voices"]) == voices
    assert set(manifest["native_catalog"]) == voices - {"default"}
    assert set(manifest["unavailable"]) == {"porto", "selva"}
    for name, clips in manifest["voices"].items():
        if name in manifest["unavailable"]:
            assert set(clips) != set(BOUNDARY_TEXT)
            assert manifest["unavailable"][name]["reason"]
            continue
        assert set(clips) == set(BOUNDARY_TEXT)
        for kind, record in clips.items():
            assert record["voice"] == (None if name == "default" else name)
            assert record["version"] == "v3"
            assert record["text"] == BOUNDARY_TEXT[kind]
            assert record["transcript"] == BOUNDARY_TEXT[kind]
            with wave.open(str(VOICE_CLIPS / name / f"{kind}.wav")) as source:
                assert source.getframerate() == 48000
                assert source.getnchannels() == 1 and source.getsampwidth() == 2
                assert 0.5 < source.getnframes() / source.getframerate() < 12
                pcm = source.readframes(source.getnframes())
                assert any(pcm)
                assert len(base64.b64encode(pcm)) <= 600000
                assert hashlib.sha256(pcm).hexdigest() == record["sha256"]
    for kind in BOUNDARY_TEXT:
        assert (
            manifest["voices"]["maple"][kind]["sha256"] != manifest["voices"]["rio"][kind]["sha256"]
        )
