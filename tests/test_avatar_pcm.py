import struct

from trendcoffee.avatar_pcm import AvatarPCMStream


def test_model_copy_does_not_reduce_the_playback_source_to_16khz():
    # Every original sample, including low bits and high-frequency changes, survives.
    raw = b"".join(struct.pack("<h", (i * 7919) % 65536 - 32768) for i in range(9600))
    stream = AvatarPCMStream()
    result = []
    for offset in range(0, len(raw), 1920):
        result.extend(stream.push(raw[offset : offset + 1920], 48000, 1))
    playback = b"".join(original for model, original in result)
    assert len(result) >= 9
    assert all(len(model) == 640 and len(original) == 1920 for model, original in result)
    assert playback == raw[: len(playback)]


def test_new_stream_does_not_contain_retired_guest_samples():
    old = AvatarPCMStream()
    old.push(struct.pack("<h", 20000) * 960, 48000, 1)
    new = AvatarPCMStream()
    frames = new.push(struct.pack("<h", -1000) * 1920, 48000, 1)
    assert frames
    assert all(original == struct.pack("<h", -1000) * 960 for _, original in frames)


def test_video_only_stream_emits_model_pcm_without_playback_conversion(monkeypatch):
    from av import AudioResampler

    def model_resampler(**options):
        if options["rate"] != 16000:
            raise AssertionError("video-only PCM must not resample unused RTP audio")
        return AudioResampler(**options)

    monkeypatch.setattr("trendcoffee.avatar_pcm.AudioResampler", model_resampler)
    stream = AvatarPCMStream(preserve_original=False)
    raw = struct.pack("<h", 4000) * 320
    frames = stream.push(raw, 16000, 1)
    assert frames == [(raw, None)]
    assert stream.push(raw, 16000, 1) == [(raw, None)]


def test_video_only_stream_downmixes_and_resamples_model_input():
    stream = AvatarPCMStream(preserve_original=False)
    raw = struct.pack("<hh", 6000, 2000) * 4800
    frames = []
    for offset in range(0, len(raw), 3840):
        frames.extend(stream.push(raw[offset : offset + 3840], 48000, 2))
    assert len(frames) == 4
    assert all(len(model) == 640 and original is None for model, original in frames)
    samples = struct.unpack("<320h", frames[-1][0])
    assert all(sample == 4000 for sample in samples)
