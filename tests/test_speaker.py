"""Trend's speech to the kiosk browser over WebRTC: backend playout and transport."""

import asyncio
from array import array

from trendcoffee.speaker import FRAME_BYTES, SpeakerPeer, SpeakerTrack

SILENCE = bytes(FRAME_BYTES)


def frames(*levels):
    return b"".join(
        level.to_bytes(2, "little", signed=True) * (FRAME_BYTES // 2) for level in levels
    )


def tone(seconds, level=8000):
    import math

    count = int(48000 * seconds)
    wave = array("h", (int(level * math.sin(2 * math.pi * 440 * i / 48000)) for i in range(count)))
    return wave.tobytes()


def samples(frame):
    return array("h", frame)


def run_ticks(track, schedule, ticks, start=0.0):
    """Drive the 20 ms send clock; `schedule` maps tick index -> pcm pushed before it."""
    sent = []
    for tick in range(ticks):
        if tick in schedule:
            track.push(schedule[tick])
        sent.append(track.next_frame(start + tick * 0.02))
    return sent


SPEECH = [frames(1000 + i) for i in range(200)]  # each frame distinct and audible
QUIET = frames(10)  # native's idle comfort level


def test_a_reply_waits_for_half_a_second_then_plays_every_frame_unchanged():
    track = SpeakerTrack(lambda playing: None)
    schedule = {i: SPEECH[i] for i in range(100)}  # native delivers in real time
    sent = run_ticks(track, schedule, 140)
    assert sent[:25] == [SILENCE] * 25, "500 ms buffered before the reply starts"
    assert [f for f in sent if f != SILENCE] == SPEECH[:100]


def test_a_short_reply_starts_half_a_second_after_its_first_word():
    track = SpeakerTrack(lambda playing: None)
    sent = run_ticks(track, {0: b"".join(SPEECH[:10])}, 40)  # a 200 ms "Dạ."
    assert sent[:25] == [SILENCE] * 25
    assert sent[25:35] == SPEECH[:10]


def test_idle_native_silence_does_not_delay_the_reply_beyond_a_short_preroll():
    track = SpeakerTrack(lambda playing: None)
    schedule = {i: QUIET for i in range(150)}  # 3 s of native idle frames
    schedule.update({150 + i: SPEECH[i] for i in range(30)})
    sent = run_ticks(track, schedule, 220)
    first_word = sent.index(SPEECH[0])
    assert 150 + 25 <= first_word <= 150 + 25 + 1, "about 500 ms after native sent it"


def test_slow_native_delivery_never_cuts_or_changes_speech():
    track = SpeakerTrack(lambda playing: None)
    # Native runs 4% slow: 100 speech frames arrive over 104 ticks, in two phrases
    # separated by a 300 ms pause of quiet frames.
    pcm = SPEECH[:50] + [QUIET] * 15 + SPEECH[50:100]
    schedule = {round(i * 1.04): f for i, f in enumerate(pcm)}
    schedule.update({120 + i: QUIET for i in range(80)})  # native keeps sending quiet frames
    sent = run_ticks(track, schedule, 200)
    speech = [f for f in sent if f in SPEECH]
    assert speech == SPEECH[:100], "every word, in order, unchanged"
    first, last = sent.index(SPEECH[0]), sent.index(SPEECH[49])
    assert sent[first : last + 1] == SPEECH[:50], "no gap inside the first phrase"
    assert track.metrics["underruns"] == 0


def test_the_buffer_is_corrected_only_inside_pauses():
    track = SpeakerTrack(lambda playing: None)
    # A 2 s clip arrives at once, then native's quiet frames continue in real time.
    schedule = {0: b"".join(SPEECH[:40]) + QUIET * 10 + b"".join(SPEECH[40:100])}
    schedule.update({i: QUIET for i in range(1, 400)})
    sent = run_ticks(track, schedule, 400)
    assert [f for f in sent if f in SPEECH] == SPEECH[:100]
    assert track.metrics["dropped_quiet"] > 0, "excess buffer removed in silence"
    assert track.buffered_ms() <= 620, "back near the 500 ms target"


def test_a_stall_inside_speech_is_silence_then_a_short_rebuffer():
    track = SpeakerTrack(lambda playing: None)
    schedule = {i: SPEECH[i] for i in range(30)}
    schedule.update({30 + 40 + i: SPEECH[30 + i] for i in range(30)})  # native stalls 800 ms
    schedule.update({100 + i: QUIET for i in range(100)})  # then its quiet frames resume
    sent = run_ticks(track, schedule, 200)
    assert [f for f in sent if f in SPEECH] == SPEECH[:60]
    assert track.metrics["underruns"] == 1


def test_playing_follows_audible_speech_not_native_idle_noise():
    async def run():
        events = []
        track = SpeakerTrack(events.append)
        run_ticks(track, {i: QUIET for i in range(40)}, 40)
        assert events == [], "idle noise must not duck the guest's microphone"
        run_ticks(track, {i: SPEECH[i] for i in range(30)}, 60, start=1.0)
        assert events == [True]
        await asyncio.sleep(0.45)
        assert events == [True, False], "stops 400 ms after the last audible frame"
        track.stop()

    asyncio.run(run())


def test_interruption_and_a_new_guest_drop_queued_speech():
    async def run():
        events = []
        track = SpeakerTrack(events.append)
        run_ticks(track, {0: b"".join(SPEECH[:40])}, 30)
        track.interrupt()
        assert events == [True, False] and track.buffered_ms() == 0
        track.push(SPEECH[0])  # the cancelled reply's remaining audio
        assert track.buffered_ms() == 0
        track.resume()
        track.push(b"".join(SPEECH[:40]))
        track.clear()
        assert track.buffered_ms() == 0
        track.stop()

    asyncio.run(run())


def test_the_track_sends_a_steady_contiguous_clock():
    async def run():
        clock = [100.0]
        slept = []

        async def sleep(seconds):
            slept.append(seconds)
            clock[0] += seconds

        track = SpeakerTrack(lambda playing: None, clock=lambda: clock[0], sleep=sleep)
        pts = [(await track.recv()).pts for _ in range(5)]
        assert pts == [0, 960, 1920, 2880, 3840]
        assert abs(clock[0] - 100.08) < 1e-9, "one frame every 20 ms"
        track.stop()

    asyncio.run(run())


def test_speaker_track_captures_and_logs_the_frames_it_sends(tmp_path):
    import wave

    from trendcoffee.speaker import SpeechCapture

    track = SpeakerTrack(lambda playing: None, capture=SpeechCapture(tmp_path / "out.wav"))
    run_ticks(track, {0: b"".join(SPEECH[:30])}, 3)
    track.stop()
    with wave.open(str(tmp_path / "out.wav")) as wav:
        assert wav.getnframes() == 3 * 960
    assert len((tmp_path / "out.csv").read_text().splitlines()) == 3


def test_speech_capture_records_only_what_it_is_given_up_to_its_limit(tmp_path):
    import wave

    from trendcoffee.speaker import SpeechCapture

    capture = SpeechCapture(tmp_path / "speaker.wav", max_seconds=0.05)
    capture.write(frames(1000, 2000))
    capture.write(frames(3000))
    capture.close()
    with wave.open(str(tmp_path / "speaker.wav")) as wav:
        assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (48000, 1, 2)
        assert wav.getnframes() == 2400, "stops at 50 ms"


def test_speech_capture_is_off_unless_a_directory_is_configured(tmp_path, monkeypatch):
    from trendcoffee.speaker import speech_capture

    monkeypatch.delenv("TREND_SPEECH_CAPTURE_DIR", raising=False)
    assert speech_capture("native") is None
    monkeypatch.setenv("TREND_SPEECH_CAPTURE_DIR", str(tmp_path))
    capture = speech_capture("native")
    capture.close()
    assert sorted(p.suffix for p in tmp_path.iterdir()) == [".csv", ".wav"]
    assert {p.name.split("-")[0] for p in tmp_path.iterdir()} == {"native"}


def test_speaker_peer_delivers_pushed_speech_to_a_webrtc_receiver():
    from aiortc import RTCPeerConnection, RTCSessionDescription
    from aiortc.mediastreams import MediaStreamError

    async def run():
        events = []
        speaker = SpeakerPeer(events.append)
        browser = RTCPeerConnection()
        browser.addTransceiver("audio", direction="recvonly")
        received = asyncio.get_running_loop().create_future()

        @browser.on("track")
        def on_track(track):
            received.set_result(track)

        await browser.setLocalDescription(await browser.createOffer())
        answer = await speaker.answer(browser.localDescription.sdp)
        await browser.setRemoteDescription(RTCSessionDescription(answer, "answer"))
        track = await asyncio.wait_for(received, 10)
        speaker.push(tone(seconds=2))
        peak = 0
        try:
            for _ in range(150):
                frame = await asyncio.wait_for(track.recv(), 5)
                peak = max(peak, max(abs(v) for v in array("h", bytes(frame.planes[0]))))
                if peak > 4000:
                    break
        except MediaStreamError:
            pass
        await speaker.close()
        await browser.close()
        assert peak > 4000, "the receiver heard Trend's speech"
        assert events[0] is True

    asyncio.run(run())


def test_speaker_peer_rejects_an_offer_without_receivable_audio():
    from aiortc import RTCPeerConnection

    async def run():
        speaker = SpeakerPeer(lambda playing: None)
        browser = RTCPeerConnection()
        browser.addTransceiver("video", direction="recvonly")
        await browser.setLocalDescription(await browser.createOffer())
        try:
            await speaker.answer(browser.localDescription.sdp)
        except ValueError:
            pass
        else:
            raise AssertionError("an offer without audio must be rejected")
        finally:
            await speaker.close()
            await browser.close()

    asyncio.run(run())


class FakeSpeaker:
    def __init__(self, on_playing):
        self.on_playing = on_playing
        self.connected = True
        self.pushed = []
        self.calls = []
        self.queued_ms = 0
        self.metrics = {"underruns": 0}

    async def answer(self, sdp):
        if sdp == "broken":
            raise ValueError("speaker_offer_without_audio")
        return "answer:" + sdp

    def push(self, pcm):
        self.calls.append("push")
        self.pushed.append(pcm)

    def interrupt(self):
        self.calls.append("interrupt")

    def buffered_ms(self):
        return self.queued_ms

    def resume(self):
        self.calls.append("resume")

    def clear(self):
        self.calls.append("clear")

    async def close(self):
        self.calls.append("close")


def speaker_host(svc):
    from test_kiosk_runtime import FakeCodex

    from trendcoffee.kiosk import InteractionHost

    class Codex(FakeCodex):
        continuous = {}

        def set_output_continuous(self, thread, value):
            self.continuous[thread] = value

        async def start_filtered_voice(self, thread):
            pass

        async def append_audio(self, thread, pcm):
            pass

    class Fusion:
        def __init__(self):
            self.playback_states = []

        async def begin(self, generation, session_id, callback, track_id):
            self.callback = callback

        async def playback(self, playing):
            self.playback_states.append(playing)

        async def end(self):
            pass

        async def close(self):
            pass

    speakers = []

    def factory(on_playing):
        speakers.append(FakeSpeaker(on_playing))
        return speakers[-1]

    host = InteractionHost(svc, codex=Codex(), fusion=Fusion(), speaker_factory=factory)
    return host, speakers


def native_audio(pcm):
    import base64

    return {
        "audio": {"data": base64.b64encode(pcm).decode(), "sampleRate": 48000, "numChannels": 1}
    }


def test_webrtc_speaker_carries_trend_speech_greeting_and_goodbye(svc):
    async def run():
        events = []

        async def send(event):
            events.append(event)

        host, speakers = speaker_host(svc)
        await host.attach(svc.new_session(), send)
        assert await host.command({"type": "speaker_offer", "sdp": "offer"}) == {
            "sdp": "answer:offer"
        }
        speaker = speakers[0]
        await host.begin(manual=True)
        greeting = next(e for e in events if e["type"] == "announcement")["announcement"]
        assert "Chào bạn" in greeting["text"] and greeting["audio"] is None
        assert len(speaker.pushed) == 1 and any(speaker.pushed[0]), "greeting clip is spoken"
        on_event = host.codex.callbacks[host.thread_id][1]
        await on_event("thread/realtime/outputAudio/delta", native_audio(b"\x10\x00" * 960))
        assert speaker.pushed[-1] == b"\x10\x00" * 960
        assert not any(e["type"] == "audio" for e in events), "no PCM on the WebSocket"
        speaker.queued_ms = 480
        await on_event("thread/realtime/userTurn/started", {"turnId": "u1"})
        await on_event("thread/realtime/assistantTurn/started", {"turnId": "a1"})
        assert speaker.calls[-2:] == ["interrupt", "resume"]
        turns = [e for e in host.audio_metrics["fusion_recent"] if "turn" in e]
        assert [(e["turn"], e.get("dropped_ms")) for e in turns][-2:] == [
            ("user", 480),
            ("assistant", None),
        ], "how much of Trend's reply an interruption discarded"
        assert host.codex.continuous == {host.thread_id: True}, "native feeds every frame"
        speaker.calls.clear()
        await host.end("next_guest")
        assert speaker.calls[:2] == ["clear", "push"], "old speech is dropped, then goodbye"
        ended = next(e for e in events if e["type"] == "ended")
        assert ended["announcement"]["audio"] is None
        await host.close()
        assert speaker.calls[-1] == "close"

    asyncio.run(run())


def test_speaker_playback_reaches_fusion_and_the_screen_after_the_echo_tail(svc):
    async def run():
        events = []

        async def send(event):
            events.append(event)

        host, speakers = speaker_host(svc)
        await host.attach(svc.new_session(), send)
        await host.command({"type": "speaker_offer", "sdp": "offer"})
        await host.begin(manual=True)
        speaker = speakers[0]
        speaker.on_playing(True)
        await asyncio.sleep(0.01)
        assert host.playing and host.fusion.playback_states[-1] is True
        speaker.on_playing(False)
        speaker.on_playing(True)  # an underrun shorter than the echo tail
        await asyncio.sleep(0.01)
        speaker.on_playing(False)
        await asyncio.sleep(0.05)
        assert host.playing, "the browser is still playing NetEQ's buffer"
        await asyncio.sleep(0.2)
        assert not host.playing and host.fusion.playback_states[-2:] == [True, False]
        speaking = [e["playing"] for e in events if e["type"] == "speaking"]
        assert speaking == [True, False]
        await host.close()

    asyncio.run(run())


def test_websocket_audio_returns_when_the_speaker_connection_is_lost(svc):
    async def run():
        events = []

        async def send(event):
            events.append(event)

        host, speakers = speaker_host(svc)
        await host.attach(svc.new_session(), send)
        await host.command({"type": "speaker_offer", "sdp": "offer"})
        await host.begin(manual=True)
        speakers[0].connected = False
        on_event = host.codex.callbacks[host.thread_id][1]
        await on_event("thread/realtime/outputAudio/delta", native_audio(b"\x10\x00" * 960))
        assert any(e["type"] == "audio" for e in events)
        await host.close()

    asyncio.run(run())


def test_invalid_speaker_offers_are_rejected_without_a_speaker(svc):
    from trendcoffee.kiosk import KioskError

    async def run():
        async def send(event):
            pass

        host, speakers = speaker_host(svc)
        await host.attach(svc.new_session(), send)
        for sdp in (None, "", "x" * 20000, "broken"):
            try:
                await host.command({"type": "speaker_offer", "sdp": sdp})
            except KioskError as error:
                assert error.code == "invalid_speaker_offer"
            else:
                raise AssertionError(sdp)
        assert host.speaker is None
        assert speakers[-1].calls == ["close"]
        await host.close()

    asyncio.run(run())


def test_browser_speaker_statistics_are_kept_as_numbers_only(svc):
    async def run():
        async def send(event):
            pass

        host, speakers = speaker_host(svc)
        await host.attach(svc.new_session(), send)
        stats = {
            "concealedSamples": 4800,
            "totalSamplesReceived": 96000,
            "insertedSamplesForDeceleration": 120,
            "jitterBufferDelay": 3.5,
            "transcript": "not a number",
            "unknown": 1,
        }
        assert await host.command({"type": "speaker_stats", "stats": stats}) == {}
        assert host.audio_metrics["browser_speaker"] == {
            "concealedSamples": 4800,
            "totalSamplesReceived": 96000,
            "insertedSamplesForDeceleration": 120,
            "jitterBufferDelay": 3.5,
        }
        await host.close()

    asyncio.run(run())


def test_speech_capture_can_log_frame_timing_next_to_the_audio(tmp_path):
    from trendcoffee.speaker import SpeechCapture

    capture = SpeechCapture(tmp_path / "native.wav")
    capture.log(12.5, 960, 1000)
    capture.log(12.52, 1920, 0)
    capture.close()
    assert (tmp_path / "native.csv").read_text().splitlines() == [
        "12.500000,960,1000",
        "12.520000,1920,0",
    ]
