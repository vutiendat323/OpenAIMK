import time

import numpy as np

from Visual.application.state import SharedState
from Visual.presentation.ws_server import VisionWSServer


def test_camera_capture_cannot_refresh_old_tracking_evidence():
    state = SharedState()
    old = time.time() - 10
    state.put_frame(np.zeros((64,64,3),dtype=np.uint8),timestamp=old)
    state.scene.observe_faces([(0,0,50,60,1,.9)], raw={1:.4}, landmarks={}, frame_seq=1, captured_at=old)
    state.scene.observe_spoof({1:(False,.9)}, captured_at=old)
    state.put_frame(np.zeros((64,64,3),dtype=np.uint8),timestamp=time.time())
    server=VisionWSServer(state,port=0)
    event=server._build_event()
    assert event["frame_seq"] == 1
    assert event["captured_at"] == old
    face=server._faces_event()
    assert face["captured_at"] == old
    assert face["tracks"][0]["is_live"] is False
