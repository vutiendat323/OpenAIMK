"""CPU-only local transport contract; no model checkout or GPU is loaded."""

import asyncio
import unittest

import numpy as np
from aiohttp.test_utils import TestClient, TestServer
from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import MediaStreamError

from scripts.ditto_server import DittoTransport, create_app


class FakeEngine:
    def __init__(self):
        self.epoch = 0
        self.frame = np.full((32, 32, 3), 80, dtype=np.uint8)
        self.pushed = []
        self.closed = False
        self.status = {"ready": True, "actions": ["idle"], "model": "ditto"}

    def reset(self, epoch):
        self.epoch = epoch

    def push(self, epoch, samples):
        self.pushed.append((epoch, samples.copy()))

    def latest_frame(self):
        return self.epoch, self.frame, 1

    def action(self, name):
        return name == "idle"

    def close(self):
        self.closed = True


class DittoTransportTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = FakeEngine()
        self.transport = DittoTransport(self.engine)
        self.client = TestClient(TestServer(create_app(self.transport)))
        await self.client.start_server()
        self.peers = []

    async def asyncTearDown(self):
        await self.client.close()
        for peer in self.peers:
            await peer.close()

    async def offer(
        self, kinds=("audio", "video"), audio_direction="recvonly", video_direction="recvonly"
    ):
        peer = RTCPeerConnection(RTCConfiguration(iceServers=[]))
        self.peers.append(peer)
        for kind in kinds:
            peer.addTransceiver(
                kind, direction=audio_direction if kind == "audio" else video_direction
            )
        await peer.setLocalDescription(await peer.createOffer())
        response = await self.client.post(
            "/offer", json={"type": "offer", "sdp": peer.localDescription.sdp}
        )
        if response.status == 200:
            # These contracts read tracks directly; complete ICE without RTP
            # consuming the same track concurrently with the assertions.
            for sender in self.transport.session.pc.getSenders():
                sender.replaceTrack(None)
            answer = await response.json()
            await peer.setRemoteDescription(RTCSessionDescription(answer["sdp"], answer["type"]))
            async with asyncio.timeout(2):
                while peer.connectionState != "connected":
                    await asyncio.sleep(0.01)
        return response

    async def open_session(self, kinds=("audio", "video"), **directions):
        response = await self.offer(kinds, **directions)
        self.assertEqual(response.status, 200)
        answer = await response.json()
        self.assertEqual(answer["type"], "answer")
        if "audio" in kinds:
            self.assertIn("m=audio", answer["sdp"])
        else:
            self.assertNotIn("m=audio", answer["sdp"])
        self.assertIn("m=video", answer["sdp"])
        return answer["sessionid"]

    async def reset(self, sid, epoch):
        return await self.client.post("/trend/reset", json={"sessionid": sid, "epoch": epoch})

    async def pcm(self, sid, epoch, raw=None, rate=48000, channels=1):
        return await self.client.post(
            "/trend/pcm",
            data=raw if raw is not None else np.full(3840, 10000, dtype="<i2").tobytes(),
            headers={
                "X-Session-ID": sid,
                "X-Epoch": str(epoch),
                "X-Sample-Rate": str(rate),
                "X-Channels": str(channels),
            },
        )

    async def test_original_audio_is_audible_and_reset_retires_both_media(self):
        sid = await self.open_session()
        self.assertEqual((await self.reset(sid, 1)).status, 200)
        self.assertEqual((await self.pcm(sid, 1)).status, 200)
        session = self.transport.session
        old_generation = self.engine.epoch
        frame = await session.audio.recv()
        self.assertEqual(frame.sample_rate, 48000)
        self.assertTrue(np.all(frame.to_ndarray() == 10000))
        self.assertTrue(self.engine.pushed)
        self.assertEqual(self.engine.pushed[0][1].shape, (320,))
        self.assertEqual(self.engine.pushed[0][1].dtype, np.float32)
        first_video = await session.video.recv()
        self.assertEqual(int(first_video.to_ndarray(format="rgb24")[0, 0, 0]), 80)
        self.assertEqual((await self.reset(sid, 2)).status, 200)
        self.assertGreater(self.engine.epoch, old_generation)
        self.assertEqual((await self.pcm(sid, 1)).status, 409)
        silent = await session.audio.recv()
        self.assertFalse(silent.to_ndarray().any())
        # Even a model worker completing old work after reset must not leak its frame.
        self.engine.epoch = old_generation
        pending = asyncio.create_task(session.video.recv())
        await asyncio.sleep(0.12)
        self.assertFalse(pending.done())
        self.engine.epoch = session.generation
        self.engine.frame[:] = 120
        current = await asyncio.wait_for(pending, 1)
        self.assertEqual(int(current.to_ndarray(format="rgb24")[0, 0, 0]), 120)
        self.assertGreater(current.pts, first_video.pts)

    async def test_video_only_pcm_never_waits_for_unconsumed_rtp_audio(self):
        sid = await self.open_session(("video",))
        self.assertEqual((await self.reset(sid, 1)).status, 200)
        session = self.transport.session
        self.assertIsNone(session.audio)
        async with asyncio.timeout(1):
            for _ in range(40):
                self.assertEqual((await self.pcm(sid, 1)).status, 200)
        self.assertGreater(len(self.engine.pushed), 100)
        self.assertEqual(len(session.audio_queue), 0)
        self.assertTrue(all(samples.shape == (320,) for _, samples in self.engine.pushed))
        frame = await session.video.recv()
        self.assertEqual(int(frame.to_ndarray(format="rgb24")[0, 0, 0]), 80)

    async def test_video_only_reset_and_reconnect_retire_old_work(self):
        sid = await self.open_session(("video",))
        await self.reset(sid, 1)
        old = self.transport.session
        generation = old.generation
        await self.pcm(sid, 1)
        self.assertEqual((await self.reset(sid, 2)).status, 200)
        self.assertEqual((await self.pcm(sid, 1)).status, 409)
        self.assertEqual(len(old.audio_queue), 0)
        self.engine.epoch = generation
        pending = asyncio.create_task(old.video.recv())
        await asyncio.sleep(0.02)
        self.assertFalse(pending.done())
        await self.client.post("/trend/close", json={"sessionid": sid})
        with self.assertRaises(MediaStreamError):
            await pending
        new_sid = await self.open_session(("video",))
        await self.reset(new_sid, 1)
        self.assertGreater(self.transport.session.generation, generation)
        self.assertIsNone(self.transport.session.audio)
        self.assertEqual((await self.pcm(sid, 1)).status, 404)

    async def test_inactive_audio_is_not_queued_for_an_unused_rtp_sender(self):
        sid = await self.open_session(audio_direction="inactive")
        await self.reset(sid, 1)
        self.assertIsNone(self.transport.session.audio)
        async with asyncio.timeout(1):
            for _ in range(10):
                self.assertEqual((await self.pcm(sid, 1)).status, 200)
        self.assertEqual(len(self.transport.session.audio_queue), 0)

    async def test_offer_requires_receivable_video(self):
        self.assertEqual((await self.offer(("audio",))).status, 400)
        self.assertIsNone(self.transport.session)
        self.assertEqual((await self.offer(("video",), video_direction="inactive")).status, 400)
        self.assertIsNone(self.transport.session)

    async def test_single_session_close_and_reconnect_use_fresh_generation(self):
        sid = await self.open_session()
        self.assertEqual((await self.offer()).status, 409)
        await self.reset(sid, 1)
        old = self.transport.session
        generation = old.generation
        self.assertEqual(
            (await self.client.post("/trend/close", json={"sessionid": sid})).status, 200
        )
        with self.assertRaises(MediaStreamError):
            await old.audio.recv()
        new_sid = await self.open_session()
        await self.reset(new_sid, 1)
        self.assertGreater(self.transport.session.generation, generation)
        self.assertEqual((await self.pcm(sid, 1)).status, 404)

    async def test_malformed_inputs_and_unsupported_action_have_defined_errors(self):
        for value in (None, [], {"type": "offer", "sdp": 1}, {"type": "answer", "sdp": "x"}):
            response = await self.client.post("/offer", json=value)
            self.assertEqual(response.status, 400)
        self.assertEqual(
            (await self.client.post("/offer", json={"type": "offer", "sdp": "bad"})).status, 400
        )
        sid = await self.open_session()
        for epoch in (True, 0, -1, "1"):
            self.assertEqual((await self.reset(sid, epoch)).status, 400)
        self.assertEqual((await self.pcm(sid, 0)).status, 409)
        await self.reset(sid, 1)
        for raw, rate, channels in (
            (b"", 48000, 1),
            (b"a", 48000, 1),
            (bytes(40000), 48000, 1),
            (bytes(2), 1, 1),
            (bytes(6), 48000, 3),
        ):
            self.assertEqual((await self.pcm(sid, 1, raw, rate, channels)).status, 400)
        self.assertEqual((await self.pcm(sid, 1)).status, 200)
        self.assertEqual((await self.pcm(sid, 1, bytes(1280), 16000)).status, 400)
        for kind, expected in ((True, 400), (99, 400), (2, 409), (1, 200)):
            response = await self.client.post(
                "/set_audiotype", json={"sessionid": sid, "audiotype": kind}
            )
            self.assertEqual(response.status, expected)

    async def test_audio_backlog_is_bounded_and_waiting_packet_cannot_cross_reset(self):
        sid = await self.open_session()
        await self.reset(sid, 1)
        for _ in range(6):
            self.assertEqual((await self.pcm(sid, 1)).status, 200)
        pending = asyncio.create_task(self.pcm(sid, 1))
        await asyncio.sleep(0.05)
        self.assertFalse(pending.done())
        self.assertLessEqual(len(self.transport.session.audio_queue), 25)
        await self.reset(sid, 2)
        self.assertEqual((await pending).status, 409)
        self.assertEqual(len(self.transport.session.audio_queue), 0)

    async def test_clock_skips_expired_audio_slots_after_stall(self):
        sid = await self.open_session()
        await self.reset(sid, 1)
        await self.pcm(sid, 1)
        track = self.transport.session.audio
        first = await track.recv()
        # Simulate 200 ms of elapsed clock time without delaying the test.
        track.started -= 0.2
        current = await track.recv()
        self.assertGreaterEqual(current.pts - first.pts, 9600)
        self.assertFalse(current.to_ndarray().any())
        self.assertEqual(len(self.transport.session.audio_queue), 0)

    async def test_health_reports_worker_failure_and_callable_status(self):
        self.engine.status = lambda: {
            "ready": False,
            "frames_rendered": 17,
            "error": "worker failed",
        }
        response = await self.client.get("/trend/health")
        result = await response.json()
        self.assertFalse(result["ready"])
        self.assertEqual(result["frames_rendered"], 17)
        self.assertEqual(result["error"], "worker failed")

    async def test_health_reports_engine_readiness(self):
        response = await self.client.get("/trend/health")
        result = await response.json()
        self.assertTrue(result["ready"])
        self.assertEqual(result["actions"], ["idle"])
        self.assertEqual(result["model"], "ditto")
        self.assertEqual(result["video_fps"], 24)

    async def test_video_timestamps_follow_the_actual_presentation_rate(self):
        await self.open_session(kinds=("video",))
        track = self.transport.session.video
        first = await track.recv()
        second = await track.recv()
        self.assertEqual(track.rate, 24)
        self.assertEqual(float((second.pts - first.pts) * second.time_base), 1 / 24)


if __name__ == "__main__":
    unittest.main()
