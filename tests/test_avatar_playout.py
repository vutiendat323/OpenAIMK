from trendcoffee.avatar_playout import AvatarPlayout


def test_video_onset_releases_original_audio_then_clock_never_repeats_old_samples():
    playout = AvatarPlayout()
    playout.reset(1)
    first = b"a" * 1920
    second = b"b" * 1920
    playout.push(1, 0, first)
    playout.push(1, 1, second)
    assert playout.read() == bytes(1920)
    playout.activate(1, 0)
    assert playout.read() == first
    assert playout.read() == second
    assert playout.read() == bytes(1920)
    assert playout.read() == bytes(1920)


def test_retired_video_cannot_release_a_new_utterance_or_guest():
    playout = AvatarPlayout()
    playout.reset(1)
    playout.push(1, 5, b"x" * 1920)
    playout.activate(1, 4)
    assert playout.read() == bytes(1920)
    playout.reset(2)
    playout.push(1, 5, b"z" * 1920)
    playout.push(2, 0, b"y" * 1920)
    playout.activate(1, 5)
    assert playout.read() == bytes(1920)
    playout.activate(2, 0)
    assert playout.read() == b"y" * 1920


def test_packet_gap_in_same_turn_does_not_require_gpu_to_release_speech_again():
    playout = AvatarPlayout()
    playout.reset(1)
    playout.push(1, 0, b"a" * 1920)
    playout.activate(1, 0)
    assert playout.read() == b"a" * 1920
    for _ in range(20):
        assert playout.read() == bytes(1920)
    playout.push(1, 1, b"b" * 1920)
    assert playout.read() == b"b" * 1920
    playout.reset(2)
    playout.push(2, 0, b"c" * 1920)
    assert playout.read() == bytes(1920)
