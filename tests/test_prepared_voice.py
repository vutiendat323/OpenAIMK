"""An unused call can be adopted once; customer threads are never recycled."""

import asyncio
from types import SimpleNamespace

import pytest

from trendcoffee.codex_voice import CodexVoice


@pytest.fixture
def prepared_native(monkeypatch):
    from trendcoffee import native_peer

    class Peer:
        starts = 0

        def __init__(self, native, thread, callback):
            self.on_event = callback
            self.failed = False
            self.closed = False
            self.ready = asyncio.get_running_loop().create_future()
            self.peer = SimpleNamespace(connectionState="connected")
            self.channel = SimpleNamespace(readyState="open")

        async def start(self):
            Peer.starts += 1
            self.ready.set_result(True)

        async def close(self):
            self.closed = True

    monkeypatch.setattr(native_peer, "NativePeer", Peer)
    native = CodexVoice(".")
    requests = []

    async def start():
        pass

    async def request(method, params):
        requests.append((method, params))
        return {"thread": {"id": f"thread-{len(requests)}"}}

    native.start, native.request = start, request
    return native, Peer, requests


def test_prepared_call_denies_tools_until_adopted_and_is_used_only_once(prepared_native):
    async def run():
        native, Peer, requests = prepared_native
        events = []

        async def callback(*args):
            events.append(args)

        try:
            catalog = [{"id": "coffee", "name": "Cà phê"}]
            await native.prepare_voice([], catalog)
            assert native.prepared_voice_ready
            standby = native.prepared[0]
            guard = native.callbacks[standby][0]
            with pytest.raises(RuntimeError, match="guest_not_attached"):
                await guard({})
            peer = native.peers[standby]
            await peer.on_event("thread/realtime/transcript/delta", {"delta": "old"})
            assert not events
            thread = await native.create_thread([], callback, callback, catalog)
            assert not native.prepared_voice_ready
            await native.start_filtered_voice(thread)
            assert thread == standby and Peer.starts == 1 and len(requests) == 1
            await peer.on_event("thread/realtime/transcript/delta", {"delta": "new"})
            assert events[-1][1]["delta"] == "new"
            assert native.callbacks[thread] == (callback, callback)
            await native.stop_voice(thread)
            following = await native.create_thread([], callback, callback, catalog)
            assert following != thread and peer.closed
        finally:
            await native.close()

    asyncio.run(run())


def test_prepared_call_is_not_adopted_with_a_different_voice(prepared_native):
    async def run():
        native, Peer, requests = prepared_native
        try:
            native.voice = "cove"
            await native.prepare_voice([], [])
            old = native.prepared[0]
            peer = native.peers[old]
            native.voice = "maple"
            thread = await native.create_thread([], None, None, [])
            assert thread != old and peer.closed
        finally:
            await native.close()

    asyncio.run(run())


def test_arriving_guest_joins_pending_handshake_instead_of_starting_a_second_call(prepared_native):
    async def run():
        native, Peer, requests = prepared_native
        entered, release = asyncio.Event(), asyncio.Event()
        original_start = Peer.start

        async def delayed_start(self):
            entered.set()
            await release.wait()
            await original_start(self)

        async def callback(*args):
            pass

        Peer.start = delayed_start
        warm = asyncio.create_task(native.prepare_voice([], []))
        await entered.wait()
        guest = asyncio.create_task(native.create_thread([], callback, callback, []))
        try:
            await asyncio.sleep(1.1)
            assert not guest.done()
            assert len(requests) == 1
            release.set()
            await warm
            thread = await guest
            assert native.callbacks[thread] == (callback, callback)
            assert Peer.starts == 1
        finally:
            release.set()
            await asyncio.gather(warm, guest, return_exceptions=True)
            await native.close()

    asyncio.run(run())


@pytest.mark.parametrize("invalid", ["menu_changed", "transport_failed"])
def test_invalid_prepared_call_is_retired_before_a_guest_gets_a_new_thread(
    prepared_native, invalid
):
    async def run():
        native, Peer, requests = prepared_native

        async def callback(*args):
            pass

        try:
            await native.prepare_voice([], [])
            old = native.prepared[0]
            peer = native.peers[old]
            if invalid == "transport_failed":
                peer.failed = True
            catalog = [{"id": "new"}] if invalid == "menu_changed" else []
            thread = await native.create_thread([], callback, callback, catalog)
            assert thread != old and peer.closed
            assert old not in native.callbacks
        finally:
            await native.close()

    asyncio.run(run())


def test_idle_preparation_recovers_a_closed_call_without_waiting_for_a_guest(prepared_native):
    async def run():
        native, Peer, requests = prepared_native
        try:
            await native.prepare_voice([], [])
            old = native.prepared[0]
            native.peers[old].failed = True
            await native.prepare_voice([], [])
            assert native.prepared[0] != old
            assert old not in native.callbacks
            assert Peer.starts == 2
        finally:
            await native.close()

    asyncio.run(run())


def test_kiosk_never_prepares_native_voice_while_waiting_or_after_guest(svc):
    from test_kiosk_runtime import Clock, FakeCodex, observation

    from trendcoffee.kiosk import InteractionHost

    class Native(FakeCodex):
        def __init__(self):
            super().__init__()
            self.preparations = 0

        async def prepare_voice(self, *args):
            self.preparations += 1

    async def run():
        native = Native()
        clock = Clock()
        host = InteractionHost(svc, codex=native, clock=clock, wall=clock)

        async def send(event):
            pass

        try:
            assert await host.warmup()
            await host.attach(svc.new_session(), send)
            await host.observe(observation(1, clock.value))
            await asyncio.sleep(0)
            assert not native.threads and native.preparations == 0
            await host.begin(manual=True)
            assert len(native.threads) == 1
            await host.end("next_guest")
            await asyncio.gather(*host.cleanup_tasks)
            await asyncio.sleep(0)
            assert native.preparations == 0 and native.stopped == native.threads
        finally:
            await host.close()

    asyncio.run(run())
