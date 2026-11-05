"""VisionWSServer: what it emits, given a scene.

Which face is nearest, how distances are smoothed and how events are
classified is the Scene's job and is tested in test_scene.py.  These tests
check the server passes that through faithfully and handles its own concerns:
telemetry shape, live config writes, and serving the console page.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from Visual.application.state import SharedState
from Visual.presentation.ws_server import VisionWSServer

KPS = [[1.0, 1.0]] * 5


def _cfg():
    return SimpleNamespace(face_ipd_m=0.063, distance_threshold=1.0,
                           camera_id=0, camera_width=640, camera_height=480)


def _server(state=None, cfg=None):
    return VisionWSServer(state or SharedState(), host="127.0.0.1", port=9876, cfg=cfg)


class TestPresenceEvent:
    def test_empty_scene_is_no_person(self):
        event = _server()._build_event()
        assert event["event"] == "no_person" and isinstance(event["ts"], float)

    def test_event_is_the_scenes_verdict_with_a_timestamp(self):
        state = SharedState()
        state.scene.observe_faces([(0, 0, 50, 60, 1, 0.9), (100, 0, 150, 60, 2, 0.8)],
                                  raw={1: 2.5, 2: 0.7}, landmarks={1: KPS, 2: KPS}, t=0.0)
        state.scene.observe_bodies([{"box": (90, 0, 200, 400), "dist": 0.8}])
        event = _server(state)._build_event()
        expected = state.scene.snapshot().event(ts=event["ts"])
        expected.update(frame_seq=-1, captured_at=None)
        assert event == expected
        assert event["nearest_m"] == 0.7 and event["track_id"] == 2

    def test_connect_event_is_no_person(self):
        assert _server()._connect_event()["event"] == "no_person"


class TestConsoleTelemetry:
    def _state(self):
        state = SharedState()
        state.put_frame(np.zeros((4, 4, 3), dtype=np.uint8))
        state.scene.observe_faces(
            [(40, 10, 60, 40, 1, 0.9), (200, 20, 260, 90, 2, 0.8), (300, 20, 340, 70, 3, 0.7)],
            raw={1: 0.6}, landmarks={1: KPS, 2: KPS}, t=0.0)
        state.scene.observe_spoof({2: (True, 0.82)})
        state.scene.observe_bodies([{"box": (0, 0, 100, 400), "dist": 0.83}])
        state.set_timing("track", 5.4)
        state.set_timing("spoof", 61.0)
        return state

    def test_nearest_is_named_by_the_server_not_guessed_by_the_page(self):
        assert _server(self._state())._monitor_event()["nearest_id"] == 1

    def test_rows_carry_what_the_console_draws(self):
        rows = {r["id"]: r for r in _server(self._state())._monitor_event()["tracks"]}
        assert rows[1]["dist"] == 0.6 and rows[1]["raw"] == 0.6 and rows[1]["gate"] is True
        assert rows[1]["body_m"] == 0.83 and rows[1]["kps"] == KPS
        assert rows[2]["gate"] is False and rows[2]["spoof"] == 0.82 and rows[2]["spoof_flag"] is True
        assert rows[3]["gate"] is None and rows[3]["dist"] == -1.0 and rows[3]["kps"] is None

    def test_bodies_and_timings_ride_along(self):
        event = _server(self._state())._monitor_event()
        assert event["bodies"] == [{"box": [0.0, 0.0, 100.0, 400.0], "dist": 0.83}]
        assert event["timing_ms"] == {"track": 5.4, "spoof": 61.0}


class TestLiveConfig:
    def test_set_applies_in_range_value(self):
        cfg = _cfg()
        result = _server(cfg=cfg)._apply_set({"key": "face_ipd_m", "value": 0.066})
        assert result["ok"] and cfg.face_ipd_m == 0.066

    def test_set_rejects_bad_writes(self):
        cfg = _cfg()
        server = _server(cfg=cfg)
        for data in ({"key": "face_ipd_m", "value": 0.5},
                     {"key": "face_ipd_m", "value": "nan"},
                     {"key": "face_ipd_m", "value": "abc"},
                     {"key": "camera_id", "value": 1}):
            assert server._apply_set(data)["ok"] is False
        assert cfg.face_ipd_m == 0.063 and cfg.camera_id == 0

    def test_info_names_the_camera_and_live_values(self):
        info = _server(cfg=_cfg())._info_event()
        assert info["camera"] == "Camera 0 (640 x 480)"
        assert info["live"] == {"face_ipd_m": 0.063, "distance_threshold": 1.0}


class TestConsolePage:
    def test_http_get_serves_the_console_page(self):
        from websockets.datastructures import Headers
        from websockets.http11 import Request, Response
        conn = MagicMock()
        conn.respond.side_effect = lambda status, text: Response(
            status, "OK", Headers([("Content-Type", "text/plain; charset=utf-8")]), text.encode())
        server = _server()
        page = server._process_request(conn, Request("/", Headers()))
        assert page.status_code == 200 and page.headers["Content-Type"].startswith("text/html")
        assert server._process_request(conn, Request("/", Headers([("Upgrade", "websocket")]))) is None
        assert server._process_request(conn, Request("/nope", Headers())).status_code == 404

    def test_http_get_serves_the_console_assets_by_type(self):
        from websockets.datastructures import Headers
        from websockets.http11 import Request, Response
        conn = MagicMock()
        conn.respond.side_effect = lambda status, text: Response(
            status, "OK", Headers([("Content-Type", "text/plain; charset=utf-8")]), text.encode())
        server = _server()
        css = server._process_request(conn, Request("/css/console.css", Headers()))
        js = server._process_request(conn, Request("/js/console.js", Headers()))
        assert css.status_code == 200 and css.headers["Content-Type"].startswith("text/css")
        assert js.status_code == 200 and "javascript" in js.headers["Content-Type"]
        assert b"connect()" in js.body
        assert js.headers["Content-Length"] == str(len(js.body))
        logo = server._process_request(conn, Request("/img/metek-wordmark.png", Headers()))
        assert logo.status_code == 200 and logo.headers["Content-Type"] == "image/png"
        assert logo.body.startswith(b"\x89PNG")
        # Only files inside the console folder, never the server's own source.
        for path in ("/../ws_server.py", "/%2e%2e/ws_server.py", "/js/../../ws_server.py"):
            assert server._process_request(conn, Request(path, Headers())).status_code == 404


class TestFacesEvent:
    def test_faces_event_lists_every_track_with_its_mouth(self):
        state = SharedState()
        track = [(100, 0, 200, 60, 3, 0.9)]
        for i in range(10):
            t = i / 15
            state.scene.observe_faces(track, raw={3: 0.8}, landmarks={3: KPS}, t=t)
            state.scene.observe_mouths({3: 0.3 if i % 2 else 0.0}, t=t)
        event = _server(state, _cfg())._faces_event()

        assert event["event"] == "faces" and isinstance(event["ts"], float)
        (face,) = event["tracks"]
        assert face["track_id"] == 3 and face["facing"] is True
        assert face["distance_m"] == pytest.approx(0.8, abs=0.05)
        assert face["cx_norm"] == pytest.approx(150 / 640)
        assert face["mouth_activity"] == 1.0
        assert face["active_speaker_probability"] is None

    def test_empty_scene_still_sends_faces_so_clients_know_vision_is_alive(self):
        assert _server()._faces_event()["tracks"] == []


# ---------------------------------------------------------------------------
# ASD audio receiver (spec 6.1) and the faces event's asd fields (spec 7).
# ---------------------------------------------------------------------------

import asyncio
import base64
import json
import time

from Visual.domain.active_speaker import AsdResult


class _Sock:
    """A fake websocket: records what it was sent; iterates *incoming*."""

    def __init__(self, incoming=()):
        self.sent = []
        self._incoming = list(incoming)

    async def send(self, message):
        self.sent.append(message)

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for m in self._incoming:
            yield m

    def events(self):
        return [json.loads(m) for m in self.sent]


def _send(server, sock, *messages):
    for m in messages:
        asyncio.run(server._on_message(sock, m))


def _disconnect(server, sock):
    asyncio.run(server._handler(sock))  # no more messages: runs the cleanup


def _start_msg(stream_id="s1", **over):
    msg = {"cmd": "asd_audio_start", "version": 1, "session_id": "voice-1",
           "stream_id": stream_id, "sample_rate": 16000, "channels": 1}
    msg.update(over)
    return json.dumps(msg)


def _pcm(n=1280, value=3):
    return np.full(n, value, dtype="<i2")


def _audio_msg(stream_id="s1", seq=0, t0=1000.0, pcm=None, **over):
    pcm = _pcm() if pcm is None else pcm
    msg = {"cmd": "asd_audio", "stream_id": stream_id, "seq": seq, "t0": t0,
           "pcm16_b64": base64.b64encode(pcm.tobytes()).decode()}
    msg.update(over)
    return json.dumps(msg)


def _stop_msg(stream_id="s1"):
    return json.dumps({"cmd": "asd_audio_stop", "stream_id": stream_id})


def _ready_server():
    state = SharedState()
    state.asd_status = "ready"
    return state, _server(state, _cfg())


def _spy_push(monkeypatch, state):
    calls = []
    real = state.asd.push_audio

    def spy(stream_id, seq, t0, pcm16):
        calls.append((stream_id, seq, t0, pcm16))
        return real(stream_id, seq, t0, pcm16)

    monkeypatch.setattr(state.asd, "push_audio", spy)
    return calls


class TestAsdAudioStart:
    def test_valid_start_is_ready_and_owns_the_stream(self):
        state, server = _ready_server()
        a = _Sock()
        _send(server, a, _start_msg())
        assert a.events() == [{"event": "asd_audio_status", "stream_id": "s1", "status": "ready"}]
        assert state.asd.active

    @pytest.mark.parametrize("status", ["disabled", "unavailable"])
    def test_provider_status_is_reported_and_no_stream_starts(self, status):
        state = SharedState()
        if status != "disabled":
            state.asd_status = status
        a = _Sock()
        _send(_server(state, _cfg()), a, _start_msg())
        assert a.events()[-1]["status"] == status
        assert not state.asd.active

    @pytest.mark.parametrize("over", [
        {"version": 3}, {"version": "1"}, {"version": True}, {"version": None},
        {"sample_rate": 48000}, {"sample_rate": 16000.0}, {"channels": 2},
        {"session_id": ""}, {"session_id": 5}, {"session_id": None},
        {"stream_id": ""}, {"stream_id": 5},
    ])
    def test_wrong_version_or_format_is_invalid(self, over):
        state, server = _ready_server()
        a = _Sock()
        _send(server, a, _start_msg(**over))
        assert a.events()[-1]["status"] == "invalid"
        assert not state.asd.active

    def test_a_second_socket_is_busy_and_cannot_touch_the_first_stream(self, monkeypatch):
        state, server = _ready_server()
        a, b = _Sock(), _Sock()
        _send(server, a, _start_msg("s1"))
        calls = _spy_push(monkeypatch, state)

        _send(server, b, _start_msg("s2"), _audio_msg("s1"), _stop_msg("s1"))
        assert b.events() == [{"event": "asd_audio_status", "stream_id": "s2", "status": "busy"}]
        assert calls == [] and state.asd.active

        _send(server, a, _audio_msg("s1"))
        assert len(calls) == 1 and calls[0][0] == "s1"

    def test_the_owner_may_replace_its_own_stream(self):
        state, server = _ready_server()
        a = _Sock()
        _send(server, a, _start_msg("s1"), _start_msg("s2"))
        assert [e["status"] for e in a.events()] == ["ready", "ready"]
        assert state.asd._stream_id == "s2"


class TestAsdAudioPackets:
    def test_valid_packet_reaches_the_buffer_as_a_copied_int16_array(self, monkeypatch):
        state, server = _ready_server()
        a = _Sock()
        _send(server, a, _start_msg())
        calls = _spy_push(monkeypatch, state)
        samples = np.arange(1280, dtype="<i2")
        _send(server, a, _audio_msg(seq=0, t0=1000.0, pcm=samples))
        (stream_id, seq, t0, pcm), = calls
        assert (stream_id, seq, t0) == ("s1", 0, 1000.0)
        assert pcm.dtype == np.int16 and pcm.shape == (1280,)
        np.testing.assert_array_equal(pcm, samples)
        assert pcm.flags.owndata and pcm.flags.writeable
        assert a.events() == [{"event": "asd_audio_status", "stream_id": "s1", "status": "ready"}]

    @pytest.mark.parametrize("message", [
        _audio_msg(pcm16_b64="!!!not base64!!!"),
        _audio_msg(pcm16_b64=base64.b64encode(_pcm().tobytes()).decode() + "\n"),
        _audio_msg(pcm16_b64=5),
        _audio_msg(t0=float("nan")),
        _audio_msg(t0=float("inf")),
        _audio_msg(t0="1000.0"),
        _audio_msg(t0=True),
        _audio_msg(seq=-1),
        _audio_msg(seq=1.0),
        _audio_msg(seq=True),
        _audio_msg(pcm=_pcm(1279)),
        _audio_msg(pcm=_pcm(1281)),
        _audio_msg(pcm=np.zeros(2561, dtype=np.uint8)),
        _audio_msg(stream_id="other"),
        _audio_msg(padding="x" * 8192),             # over the 8 KiB bound
        _audio_msg().encode()[:-1],                   # truncated JSON
    ], ids=["bad-b64", "b64-newline", "b64-not-str", "t0-nan", "t0-inf", "t0-str",
            "t0-bool", "seq-negative", "seq-float", "seq-bool", "1279-samples",
            "1281-samples", "2561-bytes", "foreign-stream", "over-8KiB", "truncated-json"])
    def test_malformed_packets_never_reach_the_buffer(self, monkeypatch, message):
        state, server = _ready_server()
        a = _Sock()
        _send(server, a, _start_msg())
        calls = _spy_push(monkeypatch, state)
        _send(server, a, message)
        assert calls == []

    def test_a_valid_packet_just_under_the_bound_is_accepted(self, monkeypatch):
        state, server = _ready_server()
        a = _Sock()
        _send(server, a, _start_msg())
        calls = _spy_push(monkeypatch, state)
        base = _audio_msg()
        message = _audio_msg(padding="x" * (8192 - len(base) - len(', "padding": ""')))
        assert len(message) == 8192
        _send(server, a, message)
        assert len(calls) == 1

    def test_a_sequence_gap_invalidates_evidence_and_restarts_accumulation(self):
        state, server = _ready_server()
        a = _Sock()
        _send(server, a, _start_msg(), *[_audio_msg(seq=i, t0=1000.0 + 0.08 * i) for i in range(3)])
        assert len(state.asd._audio) == 3
        _send(server, a, _audio_msg(seq=5, t0=1000.4))       # gap: seq 3, 4 lost
        assert len(state.asd._audio) == 1
        _send(server, a, _audio_msg(seq=6, t0=1000.48))
        assert len(state.asd._audio) == 2


class TestAsdAudioStopAndDisconnect:
    def test_stop_clears_and_is_idempotent(self):
        state, server = _ready_server()
        a, b = _Sock(), _Sock()
        _send(server, a, _start_msg("s1"), _stop_msg("s1"), _stop_msg("s1"))
        assert not state.asd.active
        _send(server, b, _start_msg("s2"))
        assert b.events()[-1]["status"] == "ready"

    def test_disconnect_clears_only_its_own_stream(self):
        state, server = _ready_server()
        a, b = _Sock(), _Sock()
        _send(server, a, _start_msg("s1"))
        _disconnect(server, b)                  # a non-owner leaving changes nothing
        assert state.asd.active
        _disconnect(server, a)
        assert not state.asd.active
        _send(server, b, _start_msg("s2"))
        assert b.events()[-1]["status"] == "ready"

    def test_old_cleanup_cannot_clear_a_later_owner(self):
        state, server = _ready_server()
        a, b = _Sock(), _Sock()
        _send(server, a, _start_msg("s1"), _stop_msg("s1"))
        _send(server, b, _start_msg("s2"))
        _send(server, a, _stop_msg("s2"))       # a's stale stop
        _disconnect(server, a)                  # a's late disconnect
        assert state.asd.active
        _send(server, b, _audio_msg("s2"))
        assert len(state.asd._audio) == 1


class TestExistingCommandsUnchanged:
    def test_monitor_faces_and_set_still_work(self):
        cfg = _cfg()
        server = _server(SharedState(), cfg)
        a = _Sock()
        _send(server, a, json.dumps({"cmd": "monitor"}), json.dumps({"cmd": "faces"}),
              json.dumps({"cmd": "set", "key": "face_ipd_m", "value": 0.065}))
        info, result = a.events()
        assert info["event"] == "info" and a in server._monitors and a in server._faces_clients
        assert result == {"event": "set_result", "ok": True, "key": "face_ipd_m", "value": 0.065}

    def test_presence_client_gets_the_connect_event_and_is_released(self):
        server = _server()
        a = _Sock()
        _disconnect(server, a)
        assert a.events()[0]["event"] == "no_person"
        assert a not in server._clients


def _two_track_state_with_result(audio_t0=None):
    """Tracks 3 and 4 in the scene; a published 25 x 0.8 result for track 3."""
    state = SharedState()
    state.scene.observe_faces([(100, 0, 200, 60, 3, 0.9), (300, 0, 360, 60, 4, 0.9)],
                              raw={3: 0.8, 4: 1.5}, landmarks={3: KPS, 4: KPS}, t=0.0)
    asd = state.asd
    asd.start_stream("s1")
    audio_t0 = time.time() - 1.1 if audio_t0 is None else audio_t0
    first = audio_t0 - 0.04
    for i in range(13):
        asd.push_audio("s1", i, first + i * 0.08, np.zeros(1280, dtype=np.int16))
    asd.select_track(3)
    for k in range(25):
        asd.push_crop(3, audio_t0 + 0.02 + 0.04 * k, np.zeros((112, 112), np.uint8))
    window = asd.next_window(offset_secs=0.0, now=time.time())
    assert window is not None
    assert asd.publish(AsdResult("s1", 3, window.audio_t0, np.full(25, 0.8, np.float32)))
    return state, window


class TestFacesEventAsd:
    def test_current_result_is_attached_to_its_track_only(self):
        state, window = _two_track_state_with_result()
        event = _server(state, _cfg())._faces_event()
        tracks = {t["track_id"]: t for t in event["tracks"]}
        track = tracks[3]
        assert track["asd"]["stream_id"] == "s1"
        assert track["asd"]["t0"] == window.audio_t0
        assert track["asd"]["frame_secs"] == 0.04
        assert len(track["asd"]["probabilities"]) == 25
        assert track["active_speaker_probability"] == pytest.approx(0.8)
        assert tracks[4]["asd"] is None and tracks[4]["active_speaker_probability"] is None
        json.dumps(event)  # the event is plain JSON

    def test_t0_is_not_restamped_by_later_events(self):
        state, window = _two_track_state_with_result()
        server = _server(state, _cfg())
        first = server._faces_event()
        time.sleep(0.05)
        second = server._faces_event()
        assert second["ts"] > first["ts"]
        assert [t["asd"]["t0"] for t in second["tracks"] if t["track_id"] == 3] == [window.audio_t0]

    def test_result_older_than_one_second_past_its_support_is_unknown(self, monkeypatch):
        import Visual.presentation.ws_server as ws_module
        state, window = _two_track_state_with_result()
        future = window.audio_t0 + 1.0 + 1.0 + 0.01   # > 1 s beyond support end
        server = _server(state, _cfg())
        monkeypatch.setattr(ws_module, "time", SimpleNamespace(time=lambda: future))
        event = server._faces_event()
        assert event["ts"] == future  # a fresh event ...
        for track in event["tracks"]:  # ... but no stale evidence in it
            assert track["asd"] is None and track["active_speaker_probability"] is None

    def test_no_result_means_both_fields_are_null(self):
        state = SharedState()
        state.scene.observe_faces([(100, 0, 200, 60, 3, 0.9)], raw={3: 0.8},
                                  landmarks={3: KPS}, t=0.0)
        (track,) = _server(state, _cfg())._faces_event()["tracks"]
        assert track["asd"] is None and track["active_speaker_probability"] is None


def _publish(state, track_id=3, stream_id="s1"):
    """One real window for *stream_id* and a published result for it."""
    asd = state.asd
    first = time.time() - 1.2
    for i in range(13):
        asd.push_audio(stream_id, i, first + i * 0.08, np.zeros(1280, dtype=np.int16))
    asd.select_track(track_id)
    audio_t0 = first + 13 * 0.08 - 1.0
    for k in range(25):
        asd.push_crop(track_id, audio_t0 + 0.02 + 0.04 * k, np.zeros((112, 112), np.uint8))
    window = asd.next_window(offset_secs=0.0, now=time.time())
    asd.publish(AsdResult(window.stream_id, window.track_id, window.audio_t0,
                          np.full(25, 0.9, np.float32)))
    return window


def _v2_owner():
    state, server = _ready_server()
    owner = _Sock()
    _send(server, owner, _start_msg(version=2))
    return state, server, owner


def _track_msg(track_id, stream_id="s1"):
    return json.dumps({"cmd": "asd_track", "stream_id": stream_id, "track_id": track_id})


class TestAsdProtocolV2Start:
    def test_version_two_is_ready(self):
        state, server = _ready_server()
        a = _Sock()
        _send(server, a, _start_msg(version=2))
        assert a.events()[-1]["status"] == "ready"
        assert state.asd.active


class TestAsdTrack:
    def test_owner_pins_and_clears(self):
        state, server, owner = _v2_owner()
        _send(server, owner, _track_msg(9))
        assert owner.events()[-1] == {"event": "asd_track_status", "stream_id": "s1",
                                      "track_id": 9, "status": "pinned"}
        assert state.asd.pinned_track == 9
        _send(server, owner, _track_msg(None))
        assert owner.events()[-1]["status"] == "cleared"
        assert state.asd.pinned_track is None

    @pytest.mark.parametrize("message", [
        _track_msg(9, stream_id="other"),
        _track_msg("9"),
        _track_msg(True),
        _track_msg(-1),
    ])
    def test_bad_pins_are_invalid(self, message):
        state, server, owner = _v2_owner()
        _send(server, owner, message)
        assert owner.events()[-1]["status"] == "invalid"
        assert state.asd.pinned_track is None

    def test_a_non_owner_cannot_pin(self):
        state, server, owner = _v2_owner()
        other = _Sock()
        _send(server, other, _track_msg(9))
        assert other.events()[-1]["status"] == "invalid"
        assert state.asd.pinned_track is None

    def test_a_v1_stream_cannot_pin(self):
        state, server = _ready_server()
        owner = _Sock()
        _send(server, owner, _start_msg(version=1), _track_msg(9))
        assert owner.events()[-1]["status"] == "invalid"

    def test_a_new_stream_drops_the_pin(self):
        state, server, owner = _v2_owner()
        _send(server, owner, _track_msg(9), _start_msg("s2", version=2))
        assert state.asd.pinned_track is None


class TestAsdPush:
    def test_event_carries_the_newest_result_once(self):
        state, server, owner = _v2_owner()
        window = _publish(state)
        event = server._asd_event()
        assert event["event"] == "asd" and event["stream_id"] == "s1"
        assert event["track_id"] == 3 and event["t0"] == window.audio_t0
        assert event["frame_secs"] == 0.04 and len(event["probabilities"]) == 25
        assert server._asd_event() is None  # never the same t0 twice

    def test_a_v1_owner_gets_no_push(self):
        state, server = _ready_server()
        owner = _Sock()
        _send(server, owner, _start_msg(version=1))
        _publish(state)
        assert server._asd_event() is None

    def test_push_goes_to_the_owner_only_and_coalesces(self):
        state, server, owner = _v2_owner()
        watcher = _Sock()
        _send(server, watcher, json.dumps({"cmd": "faces"}))

        async def scenario():
            server._asd_published = asyncio.Event()
            task = asyncio.create_task(server._asd_push_loop())
            _publish(state)
            server._asd_published.set()
            server._asd_published.set()
            await asyncio.sleep(0.05)
            task.cancel()

        asyncio.run(scenario())
        assert [e["event"] for e in owner.events()].count("asd") == 1
        assert watcher.sent == []

    def test_a_worker_thread_publish_wakes_the_push_loop(self):
        state, server, owner = _v2_owner()

        async def scenario():
            server._asd_published = asyncio.Event()
            state.asd.set_publish_listener(server._publish_listener(asyncio.get_running_loop()))
            task = asyncio.create_task(server._asd_push_loop())
            await asyncio.to_thread(_publish, state)
            await asyncio.sleep(0.05)
            task.cancel()

        asyncio.run(scenario())
        assert [e["event"] for e in owner.events()].count("asd") == 1

    def test_an_event_error_does_not_stop_later_pushes(self):
        state, server, owner = _v2_owner()
        real = server._asd_event
        calls = []

        def flaky():
            calls.append(1)
            if len(calls) == 1:
                raise ValueError("bad window")
            return real()

        server._asd_event = flaky

        async def scenario():
            server._asd_published = asyncio.Event()
            task = asyncio.create_task(server._asd_push_loop())
            server._asd_published.set()
            await asyncio.sleep(0.02)
            _publish(state)
            server._asd_published.set()
            await asyncio.sleep(0.05)
            alive = not task.done()
            task.cancel()
            return alive

        assert asyncio.run(scenario())
        assert len(calls) == 2
        assert [e["event"] for e in owner.events()].count("asd") == 1
