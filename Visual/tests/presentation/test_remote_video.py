"""Remote WebRTC video reaches the camera router through the WS server.

The backend opens one socket per voice session, sends ``video_start`` and then
binary frames: an 8-byte little-endian float64 capture time, then a JPEG.
Closing the socket (or ``video_stop``) hands the frames back to the C920.
"""

import json
import struct

import cv2
import numpy as np

from tests.presentation.test_ws_server import _cfg, _disconnect, _send, _Sock
from Visual.application.camera_router import CameraRouter
from Visual.application.state import SharedState
from Visual.presentation.ws_server import VisionWSServer


def _setup():
    state = SharedState()
    router = CameraRouter(state, width=640, height=480, remote_hfov_deg=70.0,
                          steady_frames=1)
    server = VisionWSServer(state, host="127.0.0.1", port=9876, cfg=_cfg(), router=router)
    return state, router, server


def _start(stream_id="v1"):
    return json.dumps({"cmd": "video_start", "session_id": "voice-1", "stream_id": stream_id})


def _jpeg_frame(value=200, ts=1234.5, w=640, h=480):
    image = np.full((h, w, 3), value, dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", image)
    assert ok
    return struct.pack("<d", ts) + buf.tobytes()


def test_video_start_selects_the_remote_camera():
    _, router, server = _setup()
    sock = _Sock()

    _send(server, sock, _start())

    assert sock.events()[-1] == {"event": "video_status", "status": "ready", "stream_id": "v1"}


def test_owner_frames_are_decoded_and_published_with_their_timestamp():
    state, router, server = _setup()
    sock = _Sock()
    _send(server, sock, _start(), _jpeg_frame(200, ts=1234.5))

    frame, seq, ts = state.get_frame_snapshot()
    assert frame.shape == (480, 640, 3) and abs(int(frame[0, 0, 0]) - 200) <= 3
    assert (seq, ts) == (1, 1234.5)
    assert router.source == "remote"


def test_frames_from_a_socket_that_did_not_start_video_are_ignored():
    state, _, server = _setup()
    _send(server, _Sock(), _start())

    _send(server, _Sock(), _jpeg_frame())

    assert state.get_frame_snapshot() is None


def test_a_second_session_is_refused_while_one_owns_the_video():
    _, _, server = _setup()
    _send(server, _Sock(), _start("v1"))
    other = _Sock()

    _send(server, other, _start("v2"))

    assert other.events()[-1]["status"] == "busy"


def test_malformed_frames_are_dropped():
    state, _, server = _setup()
    sock = _Sock()
    _send(server, sock, _start(), b"\x00\x01", struct.pack("<d", 1.0) + b"not a jpeg")

    assert state.get_frame_snapshot() is None


def test_disconnect_falls_back_to_the_local_camera():
    state, router, server = _setup()
    sock = _Sock()
    _send(server, sock, _start(), _jpeg_frame())

    _disconnect(server, sock)

    assert router.source == "local"
    assert router.local_frame(np.zeros((480, 640, 3), dtype=np.uint8), 2000.0)


def test_video_stop_falls_back_and_frees_the_video():
    _, router, server = _setup()
    sock = _Sock()
    _send(server, sock, _start(), _jpeg_frame(),
          json.dumps({"cmd": "video_stop", "stream_id": "v1"}))

    assert router.source == "local"
    other = _Sock()
    _send(server, other, _start("v2"))
    assert other.events()[-1]["status"] == "ready"


def test_without_a_router_remote_video_is_unavailable():
    server = VisionWSServer(SharedState(), host="127.0.0.1", port=9876, cfg=_cfg())
    sock = _Sock()

    _send(server, sock, _start())

    assert sock.events()[-1]["status"] == "unavailable"


def test_presence_reports_whether_the_server_camera_has_live_frames():
    state, router, server = _setup()
    assert server._build_event()['local_camera_available'] is False
    router.local_frame(np.zeros((480,640,3),dtype=np.uint8),1234.5)
    assert server._build_event()['local_camera_available'] is True


def test_explicit_device_selection_reaches_local_priority_router():
    state = SharedState()
    router = CameraRouter(state, width=640, height=480, remote_hfov_deg=70,
                          steady_frames=1, prefer_local=True)
    server = VisionWSServer(state, host="127.0.0.1", port=9876, cfg=_cfg(), router=router)
    router.local_frame(np.zeros((480, 640, 3), dtype=np.uint8), 1000)
    owner = _Sock()
    request = json.loads(_start())
    request["prefer_remote"] = True
    _send(server, owner, json.dumps(request), _jpeg_frame(200))
    assert router.source == "remote"
    assert int(state.get_frame_snapshot()[0][0, 0, 0]) >= 197
    _disconnect(server, owner)
    assert router.source == "local"


def test_invalid_camera_preference_does_not_claim_video():
    _, router, server = _setup()
    request = json.loads(_start())
    request["prefer_remote"] = "true"
    invalid = _Sock()
    _send(server, invalid, json.dumps(request))
    assert invalid.events()[-1]["status"] == "invalid"
    valid = _Sock()
    _send(server, valid, _start("valid"))
    assert valid.events()[-1]["status"] == "ready"


def test_explicit_camera_selection_rejects_previous_camera_results():
    state, router, server = _setup()
    sock = _Sock()
    request = json.loads(_start())
    request['camera_source'] = 'device'
    _send(server, sock, json.dumps(request))
    barrier = server._video_selected_at
    tracks = [(0, 0, 50, 50, 7, 0.9)]
    state.scene.observe_faces(tracks, {7: 0.4}, {}, frame_seq=10, captured_at=barrier - 0.1)
    assert server._build_event()['frame_seq'] == -1
    assert server._faces_event()['tracks'] == []
    state.scene.observe_faces(tracks, {7: 0.4}, {}, frame_seq=11, captured_at=barrier + 0.1)
    assert server._build_event()['frame_seq'] == 11
    assert server._faces_event()['tracks'][0]['track_id'] == 7
