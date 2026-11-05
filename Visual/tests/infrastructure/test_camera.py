"""Camera selection: C920 first, then the configured index, then any camera."""

from Visual.infrastructure.camera import camera_candidates


def _by_id(tmp_path, *names):
    for name in names:
        (tmp_path / name).write_text("")
    return str(tmp_path)


def test_c920_first_then_configured_index_then_others(tmp_path, monkeypatch):
    monkeypatch.delenv("VISION_CAMERA_PATH", raising=False)
    monkeypatch.delenv("VISION_CAMERA_INDEX", raising=False)
    by_id = _by_id(
        tmp_path,
        "usb-SunplusIT_Inc_HD_Webcam-video-index0",
        "usb-SunplusIT_Inc_HD_Webcam-video-index1",
        "usb-046d_HD_Pro_Webcam_C920_BD67D6EF-video-index0",
        "usb-046d_HD_Pro_Webcam_C920_BD67D6EF-video-index1",
    )
    assert camera_candidates(0, by_id) == [
        f"{by_id}/usb-046d_HD_Pro_Webcam_C920_BD67D6EF-video-index0",
        0,
        f"{by_id}/usb-SunplusIT_Inc_HD_Webcam-video-index0",
    ]


def test_without_c920_falls_back_to_configured_index(tmp_path, monkeypatch):
    monkeypatch.delenv("VISION_CAMERA_PATH", raising=False)
    monkeypatch.delenv("VISION_CAMERA_INDEX", raising=False)
    assert camera_candidates(0, str(tmp_path)) == [0]


def test_env_override_pins_one_camera(tmp_path, monkeypatch):
    by_id = _by_id(tmp_path, "usb-046d_HD_Pro_Webcam_C920_X-video-index0")
    monkeypatch.setenv("VISION_CAMERA_INDEX", "4")
    assert camera_candidates(0, by_id) == [4]
    monkeypatch.setenv("VISION_CAMERA_PATH", "/dev/video7")
    assert camera_candidates(0, by_id) == ["/dev/video7"]
