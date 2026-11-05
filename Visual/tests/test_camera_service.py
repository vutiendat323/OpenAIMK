"""Vision stays available for remote video without a local capture device."""

from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from Visual import main as service
from Visual.presentation import ws_server


@pytest.fixture
def runtime(monkeypatch):
    cfg = SimpleNamespace(
        device="cpu", scrfd_input_size=(320, 320), depth_interval_sec=1,
        spoof_enabled=False, spoof_interval_sec=0.5, use_calibration=False,
        camera_fx=600, camera_fy=600, camera_cx=320, camera_cy=240,
        canonical_to_real_scale=0.6, metric3d_canonical_focal=1000,
        distortion=(0, 0, 0, 0, 0),
        mouth_scale=0.06, camera_id=0, camera_width=640, camera_height=480,
        remote_camera_hfov_deg=70, remote_camera_stale_secs=0.5,
        remote_camera_steady_frames=1, ws_port=9876, use_undistort=False,
    )
    monkeypatch.delenv("VISION_ASD_CAPTURE_DIR", raising=False)
    monkeypatch.setattr(service.Config, "from_yaml", lambda: cfg)
    monkeypatch.setattr(service, "build_models", lambda _: {})
    monkeypatch.setattr(service, "start_workers", lambda *args: [])
    server = SimpleNamespace(state=None, router=None, started=False)

    class Server:
        def __init__(self, state, *, router, **kwargs):
            server.state, server.router = state, router

        def start(self):
            server.started = True

    monkeypatch.setattr(ws_server, "VisionWSServer", Server)
    clock = [10.0]
    monkeypatch.setattr(service.time, "monotonic", lambda: clock[0])
    return server, clock


def test_missing_local_camera_keeps_vision_alive_to_accept_remote_frames(runtime, monkeypatch):
    server, clock = runtime
    monkeypatch.setattr(service, "open_camera", Mock(side_effect=RuntimeError("no C920")))
    remote = np.full((480, 640, 3), 123, dtype=np.uint8)

    def wait(_):
        assert server.started and server.state.running
        server.router.select_remote("page-camera")
        assert server.router.remote_frame("page-camera", remote, 100.0)
        assert server.state.frame_source() == "remote"
        np.testing.assert_array_equal(server.state.get_latest_frame(), remote)
        server.state.running = False

    monkeypatch.setattr(service.time, "sleep", wait)
    service.main()
    assert server.started


def test_local_camera_can_return_after_starting_without_one(runtime, monkeypatch):
    server, clock = runtime
    frame = np.full((480, 640, 3), 42, dtype=np.uint8)
    cap = Mock()

    def read():
        server.state.running = False
        return True, frame

    cap.read.side_effect = read
    opener = Mock(side_effect=[RuntimeError("missing"), cap])
    monkeypatch.setattr(service, "open_camera", opener)
    monkeypatch.setattr(service.time, "sleep", lambda _: clock.__setitem__(0, clock[0] + 2.1))
    service.main()
    assert opener.call_count == 2
    np.testing.assert_array_equal(server.state.get_latest_frame(), frame)
    cap.release.assert_called_once()


def test_local_disconnect_does_not_stop_vision(runtime, monkeypatch):
    server, clock = runtime
    cap = Mock()
    cap.read.return_value = False, None
    monkeypatch.setattr(service, "open_camera", Mock(return_value=cap))

    def wait(_):
        assert server.started and server.state.running
        server.state.running = False

    waiting = Mock(side_effect=wait)
    monkeypatch.setattr(service.time, "sleep", waiting)
    service.main()
    cap.release.assert_called_once()
    waiting.assert_called_once()
    assert server.started
