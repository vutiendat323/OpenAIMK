from trendcoffee.av_transport import FusionPreroll


def packet(value, track=7, **changes):
    values = dict(
        pcm=bytes([value, 0]) * 1280,
        verdict="ACCEPT",
        reason="kept",
        track_id=track,
        locked_track=None,
        owner_track=7,
        fresh=True,
    )
    values.update(changes)
    return values


def test_first_approved_words_wait_for_the_same_owners_lock_then_arrive_in_order():
    buffer = FusionPreroll()
    for n in (1, 2, 3):
        output = buffer.push(now=n * 0.08, **packet(n))
        assert not any(pcm for pcm, _ in output if any(pcm))
    current = packet(4)
    current["locked_track"] = 7
    output = buffer.push(now=0.32, **current)
    assert [pcm for pcm, _ in output] == [bytes([n, 0]) * 1280 for n in (1, 2, 3, 4)]


def test_other_face_rejected_or_stale_audio_cannot_be_replayed_as_the_customer():
    buffer = FusionPreroll()
    buffer.push(now=0, **packet(1, track=9))
    blocked = packet(2)
    blocked.update(verdict="REJECT", reason="silenced_reject")
    buffer.push(now=0.08, **blocked)
    buffer.push(now=0.16, **packet(3))
    current = packet(4)
    current["locked_track"] = 7
    output = buffer.push(now=3, **current)
    assert [pcm for pcm, _ in output if any(pcm)] == [current["pcm"]]


def test_reset_discards_preceding_guest_prefix():
    buffer = FusionPreroll()
    buffer.push(now=0, **packet(1))
    buffer.clear()
    current = packet(2)
    current["locked_track"] = 7
    assert buffer.push(now=0.08, **current) == [(current["pcm"], "kept")]


def quiet(track=7, **changes):
    values = dict(verdict="NONE", reason="silenced_no_voice", pcm=bytes(2560))
    values.update(changes)
    return packet(0, track=track, **values)


def say(buffer, rows, start=0.0, track=7, owner=7, ends=True):
    """Feed `rows` confirmed 80 ms rows, then 320 ms of silence; return all output."""
    out, t = [], start
    for n in range(rows):
        out += buffer.push(now=t, **packet(n + 1, track=track, owner_track=owner))
        t += 0.08
    for _ in range(4 if ends else 1):
        out += buffer.push(now=t, **quiet(track=track, owner_track=owner))
        t += 0.08
    return [pcm for pcm, _ in out if any(pcm)], out


def test_a_short_first_answer_from_the_guest_is_released_when_it_ends():
    buffer = FusionPreroll()
    words, out = say(buffer, 3)  # "dạ": 240 ms of the guest's confirmed speech
    assert words == [bytes([n, 0]) * 1280 for n in (1, 2, 3)]
    assert {reason for pcm, reason in out if any(pcm)} == {"kept_short_first"}


def test_fewer_than_three_confirmed_rows_stay_blocked():
    buffer = FusionPreroll()
    words, _ = say(buffer, 2)
    assert words == []
    words, _ = say(buffer, 0, start=3.0)
    assert words == [], "the two rows age out instead of being released later"


def test_the_short_answer_waits_for_the_end_of_the_utterance():
    buffer = FusionPreroll()
    words, _ = say(buffer, 3, ends=False)  # only 80 ms of silence so far
    assert words == []


def test_another_face_speaking_in_the_same_utterance_blocks_the_release():
    buffer = FusionPreroll()
    out = []
    for n, track in enumerate((7, 9, 7, 7)):  # the companion (track 9) talks too
        out += buffer.push(now=n * 0.08, **packet(n + 1, track=track))
    for k in range(4):
        out += buffer.push(now=0.32 + k * 0.08, **quiet())
    assert not [pcm for pcm, _ in out if any(pcm)]


def test_only_the_companion_speaking_is_never_released():
    buffer = FusionPreroll()
    words, _ = say(buffer, 4, track=9, owner=7)
    assert words == []


def test_only_the_first_short_answer_is_relaxed_until_the_next_guest():
    buffer = FusionPreroll()
    assert say(buffer, 3)[0]
    assert say(buffer, 3, start=1.0)[0] == [], "later short turns need the normal lock"
    buffer.clear()  # the next guest
    assert say(buffer, 3, start=2.0)[0]


def test_without_a_presence_owner_one_single_face_is_required():
    buffer = FusionPreroll()
    assert say(buffer, 3, owner=None)[0], "manual start: the one speaking face"
    buffer.clear()
    out = []
    for n, track in enumerate((7, 7, 9)):
        out += buffer.push(now=n * 0.08, **packet(n + 1, track=track, owner_track=None))
    for k in range(4):
        out += buffer.push(now=0.24 + k * 0.08, **quiet(owner_track=None))
    assert not [pcm for pcm, _ in out if any(pcm)], "two faces: no release"


def test_stale_camera_discards_rows_without_spending_the_first_release():
    buffer = FusionPreroll()
    buffer.push(now=0, **packet(1))
    buffer.push(now=0.08, **packet(2, fresh=False))
    assert say(buffer, 3, start=0.16)[0], "the first release is still available"


def mouth_only(value, owner=7):
    """An ACCEPT row decided by mouth activity: ASD not yet confident, so no face id."""
    return packet(value, track=None, owner_track=owner)


def finish(buffer, start, owner=7):
    out = []
    for k in range(4):
        out += buffer.push(now=start + k * 0.08, **quiet(owner_track=owner))
    return out


def test_a_word_whose_asd_confidence_ramps_up_is_released_whole():
    # Measured "dạ" on 2026-11-03: ASD 0.40 0.44 0.60 0.63 0.67 0.72 0.96, mouth open throughout.
    buffer = FusionPreroll()
    out = []
    for n in range(5):
        out += buffer.push(now=n * 0.08, **mouth_only(n + 1))
    for n in (5, 6):
        out += buffer.push(now=n * 0.08, **packet(n + 1))
    out += finish(buffer, 0.56)
    assert [pcm for pcm, _ in out if any(pcm)] == [bytes([n, 0]) * 1280 for n in range(1, 8)]


def test_one_asd_confirmed_row_is_not_enough_to_identify_the_guest():
    buffer = FusionPreroll()
    out = []
    for n in range(5):
        out += buffer.push(now=n * 0.08, **mouth_only(n + 1))
    out += buffer.push(now=0.4, **packet(6))
    out += finish(buffer, 0.48)
    assert not [pcm for pcm, _ in out if any(pcm)]


def test_mouth_only_rows_with_the_companions_face_confirmed_stay_blocked():
    buffer = FusionPreroll()
    out = []
    for n in range(3):
        out += buffer.push(now=n * 0.08, **mouth_only(n + 1))
    for n in (3, 4):
        out += buffer.push(now=n * 0.08, **packet(n + 1, track=9))
    out += finish(buffer, 0.4)
    assert not [pcm for pcm, _ in out if any(pcm)]


def test_the_normal_lock_still_replays_only_rows_carrying_the_locked_face():
    buffer = FusionPreroll()
    buffer.push(now=0, **mouth_only(1))
    buffer.push(now=0.08, **packet(2))
    current = packet(3)
    current["locked_track"] = 7
    output = buffer.push(now=0.16, **current)
    assert [pcm for pcm, _ in output if any(pcm)] == [bytes([2, 0]) * 1280, current["pcm"]]
