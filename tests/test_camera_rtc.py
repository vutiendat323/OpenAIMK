"""The guest's own camera (device mode) over WebRTC: browser video becomes JPEG for Visual."""

import asyncio

import av
import pytest
from aiortc.mediastreams import MediaStreamError
from test_kiosk_runtime import FakeCodex

from trendcoffee.camera_rtc import CameraPeer
from trendcoffee.kiosk import InteractionHost, KioskError


def decode_jpeg(jpeg):
    codec = av.CodecContext.create("mjpeg", "r")
    (frame,) = codec.decode(av.Packet(jpeg))
    return frame


def test_camera_peer_turns_browser_video_into_jpeg_frames_for_visual():
    from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack

    async def run():
        jpegs = []
        got_three = asyncio.get_running_loop().create_future()

        async def on_jpeg(jpeg):
            jpegs.append(jpeg)
            if len(jpegs) == 3 and not got_three.done():
                got_three.set_result(True)

        camera = CameraPeer(on_jpeg)
        browser = RTCPeerConnection()
        browser.addTransceiver(VideoStreamTrack(), direction="sendonly")
        await browser.setLocalDescription(await browser.createOffer())
        answer = await camera.answer(browser.localDescription.sdp)
        await browser.setRemoteDescription(RTCSessionDescription(answer, "answer"))
        try:
            await asyncio.wait_for(got_three, 15)
        finally:
            await camera.close()
            await browser.close()
        for jpeg in jpegs:
            assert jpeg[:2] == b"\xff\xd8"
            frame = decode_jpeg(jpeg)
            assert (frame.width, frame.height) == (640, 480)
        assert camera.metrics["forwarded"] >= 3
        assert camera.metrics["frames"] >= camera.metrics["forwarded"]

    asyncio.run(run())


def test_camera_peer_rejects_an_offer_without_video():
    from aiortc import RTCPeerConnection

    async def run():
        async def on_jpeg(jpeg):
            raise AssertionError("no video was offered")

        camera = CameraPeer(on_jpeg)
        browser = RTCPeerConnection()
        browser.addTransceiver("audio", direction="sendonly")
        await browser.setLocalDescription(await browser.createOffer())
        try:
            with pytest.raises(ValueError):
                await camera.answer(browser.localDescription.sdp)
        finally:
            await camera.close()
            await browser.close()

    asyncio.run(run())


class ScriptedTrack:
    """Video frames at a fixed camera rate on a fake clock, then the track ends."""

    kind = "video"

    def __init__(self, clock, count, fps):
        self.clock, self.count, self.fps = clock, count, fps

    async def recv(self):
        if self.count == 0:
            raise MediaStreamError
        self.count -= 1
        self.clock[0] += 1 / self.fps
        return av.VideoFrame(64, 48, "yuv420p")


def test_camera_peer_forwards_at_most_fifteen_frames_per_second():
    """2026-11-05: at 30 fps every device-camera connection stopped after about one second."""

    async def run():
        clock = [0.0]
        jpegs = []

        async def on_jpeg(jpeg):
            jpegs.append(jpeg)

        camera = CameraPeer(on_jpeg, clock=lambda: clock[0])
        await camera.read(ScriptedTrack(clock, count=60, fps=30))  # 2 s of a 30 fps camera
        await camera.close()
        assert camera.metrics["frames"] == 60
        assert 29 <= len(jpegs) <= 31, "15 fps, like the socket path"
        assert camera.metrics["forwarded"] == len(jpegs)
        assert decode_jpeg(jpegs[0]).width == 640, "same 640x480 canvas as the socket path"

    asyncio.run(run())


def test_a_failing_visual_send_does_not_stop_the_camera():
    async def run():
        clock = [0.0]
        calls = []

        async def on_jpeg(jpeg):
            calls.append(jpeg)
            raise ConnectionError("Visual socket closed")

        camera = CameraPeer(on_jpeg, clock=lambda: clock[0])
        await camera.read(ScriptedTrack(clock, count=10, fps=15))
        await camera.close()
        assert len(calls) == 10
        assert camera.metrics["send_errors"] == 10

    asyncio.run(run())


class FakeCamera:
    def __init__(self, on_jpeg):
        self.on_jpeg = on_jpeg
        self.calls = []
        self.delivering = False
        self.stalled_now = False
        self.metrics = {"frames": 0, "forwarded": 0}

    async def answer(self, sdp):
        self.calls.append("answer")
        if sdp == "broken":
            raise ValueError("bad sdp")
        return "camera-answer"

    def receiving(self):
        return self.delivering

    def stalled(self, now):
        return self.stalled_now

    async def close(self):
        self.calls.append("close")


def camera_host(svc):
    cameras = []

    def factory(on_jpeg):
        cameras.append(FakeCamera(on_jpeg))
        return cameras[-1]

    return InteractionHost(svc, codex=FakeCodex(), camera_factory=factory), cameras


async def _send(event):
    pass


def test_device_camera_offer_is_answered_and_closed_with_the_connection(svc):
    async def run():
        host, cameras = camera_host(svc)
        controller = await host.attach(svc.new_session(), _send, camera_source="device")
        result = await host.command({"type": "camera_offer", "sdp": "offer"})
        assert result == {"sdp": "camera-answer"}
        assert host.audio_metrics["camera_transport"] is cameras[0].metrics
        await host.begin(manual=True)  # a new guest resets per-guest numbers only
        assert host.audio_metrics["camera_transport"] is cameras[0].metrics
        await host.command({"type": "camera_offer", "sdp": "offer"})  # renegotiation
        assert cameras[0].calls == ["answer", "close"]
        await host.detach(controller)
        assert cameras[1].calls == ["answer", "close"]
        assert host.camera_peer is None
        await host.close()

    asyncio.run(run())


def test_camera_offers_are_refused_for_the_kiosk_camera_and_bad_sdp(svc):
    async def run():
        host, cameras = camera_host(svc)
        controller = await host.attach(svc.new_session(), _send, camera_source="local")
        with pytest.raises(KioskError) as error:
            await host.command({"type": "camera_offer", "sdp": "offer"})
        assert error.value.code == "invalid_camera_offer"
        assert cameras == []
        await host.detach(controller)
        await host.attach(svc.new_session(), _send, camera_source="device")
        for sdp in (None, "", "x" * 20000, "broken"):
            with pytest.raises(KioskError) as error:
                await host.command({"type": "camera_offer", "sdp": sdp})
            assert error.value.code == "invalid_camera_offer"
        assert host.camera_peer is None
        assert cameras[-1].calls == ["answer", "close"]
        await host.close()

    asyncio.run(run())


def test_webrtc_frames_reach_visual_and_socket_jpegs_wait_as_fallback(svc):
    async def run():
        host, cameras = camera_host(svc)
        forwarded = []

        async def camera_frame(jpeg):
            forwarded.append(jpeg)

        host.camera_frame = camera_frame
        await host.attach(svc.new_session(), _send, camera_source="device")
        await host.camera(b"\xff\xd8socket-1")  # before WebRTC: the socket path works
        await host.command({"type": "camera_offer", "sdp": "offer"})
        await cameras[0].on_jpeg(b"\xff\xd8rtc-1")
        cameras[0].delivering = True
        await host.camera(b"\xff\xd8socket-2")  # duplicate while WebRTC delivers
        cameras[0].delivering = False
        await host.camera(b"\xff\xd8socket-3")  # WebRTC stalled: fallback again
        assert forwarded == [b"\xff\xd8socket-1", b"\xff\xd8rtc-1", b"\xff\xd8socket-3"]
        await host.close()

    asyncio.run(run())


class StallingTrack:
    """A few frames, then nothing: the browser's video stopped arriving (2026-11-05)."""

    kind = "video"

    def __init__(self, clock, count):
        self.clock, self.count = clock, count
        self.never = asyncio.Event()

    async def recv(self):
        if self.count == 0:
            await self.never.wait()
        self.count -= 1
        self.clock[0] += 1 / 30
        return av.VideoFrame(64, 48, "yuv420p")


def test_a_camera_whose_frames_stop_is_reported_stalled():
    """2026-11-05: 34 frames arrived, then none for minutes while the connection stayed up."""

    async def run():
        clock = [0.0]

        async def on_jpeg(jpeg):
            pass

        camera = CameraPeer(on_jpeg, clock=lambda: clock[0])
        assert not camera.stalled(clock[0]), "no video track yet: still negotiating"
        camera.reader = asyncio.create_task(camera.read(StallingTrack(clock, count=34)))
        for _ in range(20):
            await asyncio.sleep(0.01)
        assert camera.metrics["frames"] == 34
        assert not camera.stalled(clock[0] + 1.0)
        assert camera.stalled(clock[0] + 2.5)
        await camera.close()

    asyncio.run(run())


def test_a_camera_track_that_never_delivers_a_frame_is_stalled():
    async def run():
        clock = [10.0]

        async def on_jpeg(jpeg):
            pass

        camera = CameraPeer(on_jpeg, clock=lambda: clock[0])
        camera.reader = asyncio.create_task(camera.read(StallingTrack(clock, count=0)))
        await asyncio.sleep(0.01)
        assert not camera.stalled(11.0)
        assert camera.stalled(12.5)
        await camera.close()

    asyncio.run(run())


def test_a_camera_track_that_ended_is_replaced_too():
    async def run():
        clock = [0.0]

        async def on_jpeg(jpeg):
            pass

        camera = CameraPeer(on_jpeg, clock=lambda: clock[0])
        camera.reader = asyncio.create_task(camera.read(ScriptedTrack(clock, count=3, fps=30)))
        await camera.reader
        assert camera.metrics["track_ended"]
        assert not camera.stalled(clock[0] + 1)
        assert camera.stalled(clock[0] + 2.5)
        await camera.close()

    asyncio.run(run())


def test_a_stalled_device_camera_is_dropped_and_the_browser_reconnects_it(svc, caplog):
    async def run():
        host, cameras = camera_host(svc)
        events = []

        async def send(event):
            events.append(event)

        forwarded = []

        async def camera_frame(jpeg):
            forwarded.append(jpeg)

        host.camera_frame = camera_frame
        await host.attach(svc.new_session(), send, camera_source="device")
        await host.command({"type": "camera_offer", "sdp": "offer"})
        cameras[0].metrics["frames"] = 34
        await host._watch_camera(host.clock())
        assert host.camera_peer is cameras[0], "still delivering: kept"
        cameras[0].stalled_now = True
        with caplog.at_level("WARNING", logger="trendcoffee.kiosk"):
            await host._watch_camera(host.clock())
        assert "Device camera stalled" in caplog.text and "34 frames" in caplog.text
        assert cameras[0].calls == ["answer", "close"]
        assert host.camera_peer is None
        assert host.audio_metrics["camera_stalls"] == 1
        assert [e for e in events if e["type"] == "camera_reset"]
        await host.camera(b"\xff\xd8socket-1")  # the socket JPEGs carry the camera meanwhile
        assert forwarded == [b"\xff\xd8socket-1"]
        await host.close()

    asyncio.run(run())


def test_browser_camera_numbers_are_kept_for_diagnosis(svc):
    async def run():
        host, _ = camera_host(svc)
        await host.attach(svc.new_session(), _send, camera_source="device")
        stats = {
            "framesSent": 34,
            "framesEncoded": 35,
            "framesPerSecond": 0,
            "qualityLimitationReason": "cpu",
            "ssrc": 1234,
            "remoteId": "x",
        }
        assert await host.command({"type": "camera_stats", "stats": stats}) == {}
        assert host.audio_metrics["browser_camera"] == {
            "framesSent": 34,
            "framesEncoded": 35,
            "framesPerSecond": 0,
            "qualityLimitationReason": "cpu",
        }
        await host.close()

    asyncio.run(run())
