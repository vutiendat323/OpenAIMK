"""Camera reconnect/release lifecycle without opening hardware or loading models."""

from types import SimpleNamespace

import pytest

from trendcoffee.visual_worker import run_local_camera


def test_local_camera_retries_after_open_failure_and_dropped_capture(monkeypatch):
    from trendcoffee import visual_worker

    state = SimpleNamespace(running=True)
    cfg = SimpleNamespace(camera_id=0, camera_width=640, camera_height=480)
    attempts, frames, released = [], [], []
    clock = SimpleNamespace(value=0)
    monkeypatch.setattr(visual_worker.time, "monotonic", lambda: clock.value)
    monkeypatch.setattr(
        visual_worker.time, "sleep", lambda _: setattr(clock, "value", clock.value + 1)
    )

    class Capture:
        def __init__(self, number):
            self.number = number

        def read(self):
            if self.number == 2:
                return False, None
            state.running = False
            return True, "local-frame"

        def release(self):
            released.append(self.number)

    def open_source(*args):
        attempts.append(args)
        if len(attempts) == 1:
            raise RuntimeError("unplugged")
        return Capture(len(attempts))

    router = SimpleNamespace(local_frame=lambda frame, ts: frames.append(frame))
    run_local_camera(state, cfg, router, open_source)
    assert attempts == [(0, 640, 480)] * 3
    assert released == [2, 3]
    assert frames == ["local-frame"]


@pytest.mark.parametrize("camera_source", ["local", "device"])
def test_visual_availability_is_forwarded_once_per_source_change(svc, camera_source):
    import asyncio
    import json

    import websockets
    from test_kiosk_runtime import FakeCodex

    from trendcoffee.kiosk import InteractionHost

    async def run():
        events = []
        delivered = asyncio.Event()

        async def visual(socket):
            registration = json.loads(await socket.recv())
            assert registration["prefer_remote"] is (camera_source == "device")
            assert registration["camera_source"] == camera_source
            for available in (True, True, False):
                await socket.send(
                    json.dumps({"event": "no_person", "local_camera_available": available})
                )
            await delivered.wait()

        async def send(event):
            if event["type"] == "camera":
                events.append(event["local_available"])
                if len(events) == 2:
                    delivered.set()

        async with websockets.serve(visual, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            host = InteractionHost(svc, codex=FakeCodex(), visual_url=f"ws://127.0.0.1:{port}")
            await host.attach(svc.new_session(), send, camera_source=camera_source)
            host.start_background()
            await asyncio.wait_for(delivered.wait(), 2)
            assert events == [True, False]
            await host.close()

    asyncio.run(run())
