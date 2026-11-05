"""The API's camera link to Visual must say why it closed (it used to fail silently)."""

import asyncio
import json
import logging

from test_kiosk_runtime import FakeCodex

from trendcoffee.kiosk import InteractionHost


def test_a_refused_camera_link_is_logged_with_its_reason(svc, caplog):
    import websockets

    async def run():
        async def visual(socket):
            await socket.send(json.dumps({"event": "no_person", "ts": 0}))
            command = json.loads(await socket.recv())
            assert command["cmd"] == "video_start"
            await socket.send(
                json.dumps(
                    {"event": "video_status", "status": "busy", "stream_id": command["stream_id"]}
                )
            )
            await asyncio.sleep(1)

        async with websockets.serve(visual, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            host = InteractionHost(svc, codex=FakeCodex(), visual_url=f"ws://127.0.0.1:{port}")

            async def send(event):
                pass

            controller = await host.attach(svc.new_session(), send, camera_source="device")
            host.start_background()
            for _ in range(100):
                if any("camera link lost" in r.getMessage() for r in caplog.records):
                    break
                await asyncio.sleep(0.02)
            await host.detach(controller)
            await host.close()

    with caplog.at_level(logging.INFO, logger="trendcoffee.kiosk"):
        asyncio.run(run())
    messages = [r.getMessage() for r in caplog.records]
    assert any("camera link open" in m and "device" in m for m in messages), messages
    lost = [m for m in messages if "camera link lost" in m]
    assert lost and "busy" in lost[0], messages
