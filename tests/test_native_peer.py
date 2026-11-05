import asyncio
from itertools import pairwise

import pytest
from aiortc.mediastreams import MediaStreamError

from trendcoffee.native_peer import FilteredTrack


def test_delayed_fusion_burst_preserves_first_words(monkeypatch):
    from unittest.mock import AsyncMock

    monkeypatch.setattr("trendcoffee.native_peer.asyncio.sleep", AsyncMock())

    async def run():
        track = FilteredTrack()
        try:
            # Fusion's 700ms decision window plus a short scheduling stall can
            # release more than eight 80ms approved chunks at once.
            chunks = [bytes([index, 0]) * 1280 for index in range(1, 14)]
            for chunk in chunks:
                track.push(chunk)
            received = []
            for _ in range(len(chunks) * 4):
                frame = await track.recv()
                received.append(bytes(frame.planes[0])[:640])
            assert b"".join(received) == b"".join(chunks)
        finally:
            track.stop()

    asyncio.run(run())


def test_closing_peer_cancels_pending_stun_retry_before_socket_teardown():
    from types import SimpleNamespace

    from aioice import stun

    from trendcoffee.native_peer import NativePeer

    async def run():
        async def event(*args):
            pass

        peer = NativePeer(None, "thread", event)
        sent = []
        protocol = SimpleNamespace(send_stun=lambda *args: sent.append(peer.closed))
        transaction = stun.Transaction(
            stun.Message(stun.Method.BINDING, stun.Class.REQUEST),
            ("127.0.0.1", 9),
            protocol,
        )
        task = asyncio.create_task(transaction.run())
        connection = peer.peer.sctp.transport.transport.iceGatherer._connection
        connection._check_list.append(SimpleNamespace(task=task))
        try:
            await asyncio.sleep(0)
            assert sent == [False]
            await peer.close()
            assert task.cancelled()
            await asyncio.sleep(0.55)
            assert sent == [False]
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await peer.close()

    asyncio.run(run())


def test_close_after_sdp_cancels_connect_tasks_without_restarting_closed_ice():
    from trendcoffee.native_peer import NativePeer

    async def run():
        async def event(*args):
            pass

        failures = []
        loop = asyncio.get_running_loop()
        previous = loop.get_exception_handler()
        loop.set_exception_handler(lambda _, context: failures.append(context))
        caller, callee = NativePeer(None, "caller", event), NativePeer(None, "callee", event)
        try:
            await caller.peer.setLocalDescription(await caller.peer.createOffer())
            await callee.peer.setRemoteDescription(caller.peer.localDescription)
            await callee.peer.setLocalDescription(await callee.peer.createAnswer())
            await caller.peer.setRemoteDescription(callee.peer.localDescription)
            await caller.close()
            await callee.close()
            await asyncio.sleep(0.1)
            assert not caller.connect_tasks and not callee.connect_tasks
            assert not failures, failures
        finally:
            await caller.close()
            await callee.close()
            loop.set_exception_handler(previous)

    asyncio.run(run())


def test_candidate_route_preference_is_local_and_keeps_unmatched_addresses(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock

    from trendcoffee.native_peer import NativePeer

    async def run():
        original = AsyncMock(return_value=["candidate"])
        connection = SimpleNamespace(get_component_candidates=original)
        transport = SimpleNamespace(iceGatherer=SimpleNamespace(_connection=connection))

        # A single fake transport also represents bundled media/data ICE.
        class Transport:
            iceGatherer = transport.iceGatherer

        ice = Transport()
        peer = SimpleNamespace(
            sctp=SimpleNamespace(transport=SimpleNamespace(transport=ice)),
            getTransceivers=lambda: [],
        )
        route = MagicMock()
        route.__enter__.return_value.getsockname.return_value = ("192.168.1.47", 1234)
        # Patch only the synchronous route lookup, never the event loop's socket creation.
        with monkeypatch.context() as patch:
            patch.setattr("trendcoffee.native_peer.socket.socket", lambda *args: route)
            NativePeer.prefer_default_route(SimpleNamespace(peer=peer))
        result = await connection.get_component_candidates(
            1, ["172.17.0.1", "192.168.1.47", "100.1.2.3"], 4
        )
        assert result == ["candidate"]
        original.assert_awaited_with(1, ["192.168.1.47"], 4)
        await connection.get_component_candidates(1, ["::1"], 4)
        original.assert_awaited_with(1, ["::1"], 4)

    asyncio.run(run())


def test_filtered_track_has_bounded_audio_and_drops_tail_on_close():
    async def run():
        track = FilteredTrack()
        frame = await track.recv()
        assert not any(bytes(frame.planes[0]))
        track.push(b"\x01\x00" * 1280)
        frame = await track.recv()
        assert bytes(frame.planes[0])[:640] == b"\x01\x00" * 320
        for _ in range(track.MAX_PENDING):
            track.push(b"\x02\x00" * 1280)
        with pytest.raises(BufferError, match="native_input_backlog"):
            track.push(b"\x03\x00" * 1280)
        assert len(track.pending) == track.MAX_PENDING
        track.stop()
        assert not track.pending
        with pytest.raises(MediaStreamError):
            await track.recv()

    asyncio.run(run())


def test_native_v3_turn_done_is_the_confirmation_source():
    from trendcoffee.native_peer import NativePeer

    async def run():
        received = []

        async def event(method, params):
            received.append((method, params))

        peer = NativePeer(None, "thread", event)
        peer.handle_event(
            {
                "type": "input_transcript.added",
                "item": {"type": "input_transcript", "text": "Tôi xác nhận"},
            }
        )
        peer.handle_event({"type": "session.input_transcript.delta", "delta": "Tôi xác nhận"})
        await asyncio.sleep(0.7)
        assert not any(method.endswith("transcript/done") for method, _ in received)
        peer.handle_event(
            {
                "type": "turn.done",
                "turn": {"id": "one", "role": "user", "transcript": "Tôi xác nhận"},
            }
        )
        await asyncio.sleep(0)
        assert any(
            params.get("text") == "Tôi xác nhận" and params.get("role") == "user"
            for method, params in received
            if method.endswith("transcript/done")
        )
        await peer.close()

    asyncio.run(run())


def test_native_output_keeps_quiet_words_and_every_packet_under_backpressure():
    import base64

    from av import AudioFrame

    from trendcoffee.native_peer import NativePeer

    async def run():
        received = []

        async def event(method, params):
            if method.endswith("outputAudio/delta"):
                await asyncio.sleep(0.001)
                received.append(base64.b64decode(params["audio"]["data"]))

        class Track:
            position = 0

            async def recv(self):
                if self.position == 100:
                    raise MediaStreamError
                # Low-level consonants must survive, including a quiet opening.
                pcm = (30 if self.position < 10 else 1000).to_bytes(2, "little") * 960
                frame = AudioFrame(format="s16", layout="mono", samples=960)
                frame.planes[0].update(pcm)
                frame.sample_rate = 48000
                self.position += 1
                return frame

        peer = NativePeer(None, "fixture", event)
        peer.handle_event({"type": "turn.created", "turn": {"role": "assistant"}})
        try:
            await peer.receive_audio(Track())
            await asyncio.sleep(0.2)
            assert len(received) == 100
            assert received[:10] == [b"\x1e\x00" * 960] * 10
        finally:
            await peer.close()

    asyncio.run(run())


def test_input_scheduler_recovers_without_discarding_approved_words():
    async def run():
        track = FilteredTrack()
        await track.recv()
        track.push(b"\x01\x00" * 1280)
        track.origin -= 0.3
        frame = await track.recv()
        assert bytes(frame.planes[0])[:640] == b"\x01\x00" * 320
        track.stop()

    asyncio.run(run())


def test_native_idle_comfort_noise_does_not_keep_the_microphone_ducked():
    from av import AudioFrame

    from trendcoffee.native_peer import NativePeer

    async def run():
        received = []

        async def event(method, params):
            received.append(method)

        class Track:
            position = 0

            async def recv(self):
                if self.position == 20:
                    raise MediaStreamError
                frame = AudioFrame(format="s16", layout="mono", samples=960)
                frame.planes[0].update(b"\x01\x00" * 960)
                frame.sample_rate = 48000
                self.position += 1
                return frame

        peer = NativePeer(None, "fixture", event)
        try:
            await peer.receive_audio(Track())
            assert not received
        finally:
            await peer.close()

    asyncio.run(run())


def test_transcript_fragments_before_turn_created_keep_the_same_bubble_id():
    from trendcoffee.native_peer import NativePeer

    async def run():
        events = []

        async def event(method, params):
            events.append((method, params))

        peer = NativePeer(None, "thread", event)
        try:
            peer.handle_event({"type": "input_transcript.added", "item": {"text": "Cho mình "}})
            peer.handle_event({"type": "turn.created", "turn": {"role": "user", "id": "real-id"}})
            peer.handle_event({"type": "input_transcript.added", "item": {"text": "cà phê"}})
            peer.handle_event(
                {
                    "type": "turn.done",
                    "turn": {"role": "user", "id": "real-id", "transcript": "Cho mình cà phê"},
                }
            )
            await asyncio.sleep(0)
            transcripts = [p for m, p in events if "/transcript/" in m]
            assert len(transcripts) == 3
            assert len({p["turnId"] for p in transcripts}) == 1
            peer.handle_event({"type": "input_transcript.added", "item": {"text": "Mang đi"}})
            await asyncio.sleep(0)
            assert events[-1][1]["turnId"] != transcripts[0]["turnId"]
        finally:
            await peer.close()

    asyncio.run(run())


def test_initial_masked_silence_does_not_delay_the_first_approved_words():
    async def run():
        track = FilteredTrack()
        # Fusion releases packets in batches once evidence covers them. Native
        # already receives generated silence while these startup packets wait.
        for _ in range(6):
            track.push(bytes(2560))
        speech = b"\x01\x02" * 1280
        track.push(speech)
        first = await track.recv()
        assert bytes(first.planes[0])[:640] == speech[:640]
        # Once speech has started, ordinary pauses must retain their duration.
        track.push(bytes(2560))
        track.push(b"\x03\x04" * 1280)
        remaining = [bytes((await track.recv()).planes[0])[:640] for _ in range(11)]
        assert remaining[:3] == [speech[:640]] * 3
        assert remaining[3:7] == [bytes(640)] * 4
        assert remaining[7:] == [b"\x03\x04" * 320] * 4
        track.stop()

    asyncio.run(run())


def test_native_output_preserves_a_natural_pause_inside_an_assistant_turn(monkeypatch):
    import base64

    from av import AudioFrame

    from trendcoffee.native_peer import NativePeer

    async def run():
        received = []
        clock = [100.0]
        monkeypatch.setattr("trendcoffee.native_peer.time.monotonic", lambda: clock[0])

        async def event(method, params):
            if method.endswith("outputAudio/delta"):
                received.append(base64.b64decode(params["audio"]["data"]))

        class Track:
            position = 0

            async def recv(self):
                if self.position == 100:
                    raise MediaStreamError
                # A spoken clause, 800ms thinking/breath pause, then the next clause.
                level = 0 if 20 <= self.position < 60 else 1000
                frame = AudioFrame(format="s16", layout="mono", samples=960)
                frame.planes[0].update(level.to_bytes(2, "little") * 960)
                frame.sample_rate = 48000
                self.position += 1
                clock[0] += 0.02
                return frame

        peer = NativePeer(None, "fixture", event)
        peer.handle_event({"type": "turn.created", "turn": {"role": "assistant"}})
        try:
            await peer.receive_audio(Track())
            assert len(received) == 100, "The browser must receive the entire turn's media clock"
            assert received[20:60] == [bytes(1920)] * 40
        finally:
            await peer.close()

    asyncio.run(run())


def _rtp(seq, data=b"opus"):
    from aiortc.rtp import RtpPacket

    packet = RtpPacket(
        payload_type=111,
        sequence_number=seq & 0xFFFF,
        timestamp=(seq * 960) & 0xFFFFFFFF,
    )
    packet._data = data
    return packet


def _native_audio_buffer(peer):
    (receiver,) = [r for r in peer.peer.getReceivers() if r._RTCRtpReceiver__kind == "audio"]
    return receiver._RTCRtpReceiver__jitter_buffer


def test_native_output_packet_loss_never_holds_or_discards_received_audio():
    from trendcoffee.native_peer import NativePeer

    async def run():
        async def event(method, params):
            pass

        peer = NativePeer(None, "fixture", event)
        try:
            buffer = _native_audio_buffer(peer)
            lost = {65550, 65551, 65570}
            # Crosses the 16-bit sequence wrap. aiortc's default audio buffer held
            # every packet behind one loss for 320 ms, then discarded good packets.
            for seq in range(65530, 65590):
                if seq in lost:
                    continue
                _, frame = buffer.add(_rtp(seq))
                assert frame is not None, f"packet {seq} must decode on arrival"
                assert frame.timestamp == (seq * 960) & 0xFFFFFFFF
            # A packet arriving after its successors were played, or a duplicate.
            assert buffer.add(_rtp(65550))[1] is None
            assert buffer.add(_rtp(65589))[1] is None
            assert buffer.add(_rtp(65590, data=b""))[1] is None
            assert {k: buffer.metrics[k] for k in ("packets", "lost", "late")} == {
                "packets": 57,
                "lost": 3,
                "late": 2,
            }
        finally:
            await peer.close()

    asyncio.run(run())


def _assistant_output(frames):
    import base64
    from array import array
    from fractions import Fraction

    from av import AudioFrame

    from trendcoffee.native_peer import NativePeer

    async def run():
        received = []

        async def event(method, params):
            if method.endswith("outputAudio/delta"):
                received.append(base64.b64decode(params["audio"]["data"]))

        class Track:
            position = 0

            async def recv(self):
                if self.position == len(frames):
                    raise MediaStreamError
                pts, level = frames[self.position]
                frame = AudioFrame(format="s16", layout="mono", samples=960)
                frame.planes[0].update(level.to_bytes(2, "little", signed=True) * 960)
                frame.sample_rate = 48000
                frame.pts, frame.time_base = pts, Fraction(1, 48000)
                self.position += 1
                return frame

        peer = NativePeer(None, "fixture", event)
        peer.handle_event({"type": "turn.created", "turn": {"role": "assistant"}})
        try:
            await peer.receive_audio(Track())
            return array("h", b"".join(received)), dict(peer.output_buffer.metrics)
        finally:
            await peer.close()

    return asyncio.run(run())


def test_native_output_replaces_a_lost_packet_with_a_smooth_gap_of_equal_length():
    # The packet at pts 1920 was lost on the network.
    samples, metrics = _assistant_output([(0, 1000), (960, 1000), (2880, -1000), (3840, -1000)])
    # The browser keeps its media clock: 20 ms is replaced, not removed, so the
    # playback buffer does not drain by one packet for every loss.
    assert len(samples) == 5 * 960
    assert samples[1920] < 1000 and set(samples[1920 + 240 : 2880]) == {0}
    assert samples[-1] == -1000, "audio after the loss is otherwise unchanged"
    steps = [abs(b - a) for a, b in pairwise(samples)]
    assert max(steps) <= 10, "no click where the lost packet starts or ends"
    assert metrics["concealed_ms"] == 20


def test_native_output_does_not_fill_a_long_pause_between_phrases():
    # A one-second jump is a codec pause or a new phrase, not a network loss.
    samples, metrics = _assistant_output([(0, 1000), (48960, 1000)])
    assert len(samples) == 2 * 960
    assert set(samples) == {1000}
    assert metrics["concealed_ms"] == 0


def test_native_output_records_arrival_gaps_while_trend_speaks(monkeypatch):
    from av import AudioFrame

    from trendcoffee.native_peer import NativePeer

    async def run():
        clock = [100.0]
        monkeypatch.setattr("trendcoffee.native_peer.time.monotonic", lambda: clock[0])

        async def event(method, params):
            pass

        class Track:
            position = 0

            async def recv(self):
                if self.position == 10:
                    raise MediaStreamError
                # Packets every 20 ms, except one 150 ms network delay.
                clock[0] += 0.15 if self.position == 5 else 0.02
                frame = AudioFrame(format="s16", layout="mono", samples=960)
                frame.planes[0].update(b"\xe8\x03" * 960)
                frame.sample_rate = 48000
                self.position += 1
                return frame

        peer = NativePeer(None, "fixture", event)
        peer.handle_event({"type": "turn.created", "turn": {"role": "assistant"}})
        try:
            await peer.receive_audio(Track())
            metrics = peer.output_buffer.metrics
            assert metrics["arrival_gaps_over_100ms"] == 1
            assert metrics["max_arrival_gap_ms"] == 150
            assert metrics["max_send_ms"] == 0, "the browser socket did not hold Trend's audio"
        finally:
            await peer.close()

    asyncio.run(run())


def test_continuous_output_forwards_every_native_frame_for_the_webrtc_speaker():
    from av import AudioFrame

    from trendcoffee.native_peer import NativePeer

    async def run():
        received = []

        async def event(method, params):
            received.append(method)

        class Track:
            position = 0

            async def recv(self):
                if self.position == 20:
                    raise MediaStreamError
                frame = AudioFrame(format="s16", layout="mono", samples=960)
                frame.planes[0].update(b"\x01\x00" * 960)
                frame.sample_rate = 48000
                self.position += 1
                return frame

        peer = NativePeer(None, "fixture", event)
        peer.continuous = True
        try:
            await peer.receive_audio(Track())
            # The speaker keeps native's 20 ms clock, pauses and idle noise included.
            assert received == ["thread/realtime/outputAudio/delta"] * 20
        finally:
            await peer.close()

    asyncio.run(run())


def test_filtered_track_reports_its_current_backlog():
    async def run():
        track = FilteredTrack()
        track.push(b"\x01\x00" * 1280)
        track.push(b"\x01\x00" * 1280)
        assert track.metrics["buffer_ms"] == 160
        await track.recv()
        assert track.metrics["buffer_ms"] == 140
        track.stop()

    asyncio.run(run())
