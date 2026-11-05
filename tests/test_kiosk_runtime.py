"""Interaction ownership tests. No models, microphone, camera or external APIs."""

import asyncio
import struct

import pytest

from trendcoffee.kiosk import InteractionHost, KioskError, PresencePolicy


class Clock:
    value = 100.0

    def __call__(self):
        return self.value


class FakeCodex:
    def __init__(self):
        self.threads = []
        self.stopped = []
        self.callbacks = {}

    async def start(self):
        pass

    async def list_voices(self):
        return ["cove", "maple", "rio"]

    async def create_thread(self, tools, on_tool, on_event, catalog=None):
        ident = f"thread-{len(self.threads) + 1}"
        self.threads.append(ident)
        self.callbacks[ident] = (on_tool, on_event)
        return ident

    async def start_voice(self, thread_id, sdp):
        return "answer:" + sdp

    async def stop_voice(self, thread_id):
        self.stopped.append(thread_id)

    async def close(self):
        pass


def observation(seq, ts, track=7, distance=0.4):
    return {
        "event": "person_near",
        "ts": ts,
        "captured_at": ts,
        "frame_seq": seq,
        "nearest_m": distance,
        "track_id": track,
        "tracks": [{"track_id": track, "distance_m": distance}],
    }


def test_presence_needs_fresh_capture_and_does_not_count_frozen_frames():
    policy = PresencePolicy()
    assert policy.observe(observation(1, 100), 100, 100) is None
    # New delivery time cannot refresh the same captured frame.
    for value in range(101, 110):
        event = observation(1, 100)
        event["ts"] = value
        assert policy.observe(event, value, value) is None
    assert not policy.active


def test_presence_uses_continuous_evidence_and_the_owners_departure():
    policy = PresencePolicy()
    entered = []
    for seq in range(27):
        now = 100 + seq * 0.2
        result = policy.observe(observation(seq + 1, now), now, now)
        if result:
            entered.append(result)
    assert entered == ["enter"]
    assert policy.track_id == 7
    # A nearer bystander cannot retain this guest when owner 7 leaves.
    left = []
    for seq in range(27, 45):
        now = 100 + seq * 0.2
        result = policy.observe(observation(seq + 1, now, track=8), now, now)
        if result:
            left.append(result)
    assert left == ["leave"]


def test_camera_loss_ends_an_active_interaction_after_a_bounded_grace():
    policy = PresencePolicy(enter_seconds=0)
    assert policy.observe(observation(1, 100), 100, 100) == "enter"
    assert policy.tick(101) is None
    assert policy.tick(105) == "leave"


def test_presence_starts_after_two_seconds_of_fresh_continuous_frames():
    policy = PresencePolicy()
    for seq in range(10):
        now = 100 + seq * 0.2
        assert policy.observe(observation(seq + 1, now), now, now) is None
    assert policy.observe(observation(11, 102), 102, 102) == "enter"


def test_greeting_waits_for_voice_ready_and_is_not_repeated_on_reconnect(svc):
    import base64

    async def run():
        connecting, connect = asyncio.Event(), asyncio.Event()
        stopping, stop = asyncio.Event(), asyncio.Event()

        class SlowCodex(FakeCodex):
            def __init__(self):
                super().__init__()
                self.audio = []

            async def start_filtered_voice(self, thread):
                connecting.set()
                await connect.wait()

            async def append_audio(self, thread, pcm):
                self.audio.append(pcm)

            async def stop_voice(self, thread):
                stopping.set()
                await stop.wait()
                await super().stop_voice(thread)

        class Fusion:
            async def begin(self, generation, session_id, callback, track_id):
                self.callback = callback

            async def playback(self, playing):
                pass

            async def end(self):
                pass

            async def close(self):
                pass

        events = []

        async def send(event):
            events.append(event)

        host = InteractionHost(svc, codex=SlowCodex(), fusion=Fusion())
        await host.attach(svc.new_session(), send)
        begin = asyncio.create_task(host.begin(manual=True))
        await asyncio.wait_for(connecting.wait(), 1)
        assert any(event["type"] == "session" for event in events)
        assert not any(event.get("announcement") for event in events)
        callback = host.codex.callbacks[host.thread_id][1]
        await callback("thread/realtime/outputAudio/delta", {"audio": {}})
        await host.fusion.callback({"type": "pcm", "data": base64.b64encode(bytes(2560)).decode()})
        assert not any(event["type"] == "audio" for event in events)
        assert not host.codex.audio
        connect.set()
        await begin
        greeting = next(event for event in events if event["type"] == "announcement")
        assert host.voice_ready and "Chào bạn" in greeting["announcement"]["text"]
        assert any(base64.b64decode(greeting["announcement"]["audio"]["data"]))
        await host.fusion.callback({"type": "pcm", "data": base64.b64encode(bytes(2560)).decode()})
        assert len(host.codex.audio) == 1
        stop.set()
        await host._disconnect_voice()
        stop.clear()
        stopping.clear()
        await host._open_voice(host.generation)
        assert sum(event["type"] == "announcement" for event in events) == 1
        end = asyncio.create_task(host.end("next_guest"))
        await asyncio.wait_for(stopping.wait(), 1)
        try:
            goodbye = next(event for event in events if event["type"] == "ended")
            assert "Tạm biệt" in goodbye["announcement"]["text"]
            assert not host.active
        finally:
            stop.set()
            await end
            await host.close()

    asyncio.run(run())


def test_guest_leaving_before_voice_ready_never_receives_greeting(svc):
    async def run():
        started = asyncio.Event()

        class SlowCodex(FakeCodex):
            async def create_thread(self, *args):
                started.set()
                await asyncio.Event().wait()

        events = []

        async def send(event):
            events.append(event)

        host = InteractionHost(svc, codex=SlowCodex())
        await host.attach(svc.new_session(), send)
        await host.command({"type": "begin"})
        await asyncio.wait_for(started.wait(), 1)
        await host.end("customer_left")
        await asyncio.sleep(0)
        assert not any(event["type"] == "announcement" for event in events)
        await host.close()

    asyncio.run(run())


def test_playback_started_during_connection_reaches_fusion_before_voice(svc):
    async def run():
        sequence = []

        class Codex(FakeCodex):
            async def start_filtered_voice(self, thread):
                sequence.append("voice")

        class Fusion:
            async def begin(self, *args):
                sequence.append("fusion")

            async def playback(self, playing):
                sequence.append(("playback", playing))

            async def end(self):
                pass

            async def close(self):
                pass

        host = InteractionHost(svc, codex=Codex(), fusion=Fusion())

        async def send(event):
            if event["type"] == "session":
                await host.command(
                    {"type": "playback", "generation": event["generation"], "playing": True}
                )

        await host.attach(svc.new_session(), send)
        await host.begin(manual=True)
        assert sequence == ["fusion", ("playback", True), "voice"]
        await host.close()

    asyncio.run(run())


def test_native_cleanup_does_not_block_the_next_customer(svc):
    async def run():
        stopped = asyncio.Event()

        class SlowCleanup(FakeCodex):
            async def stop_voice(self, thread):
                await stopped.wait()

        host = InteractionHost(svc, codex=SlowCleanup())

        async def send(event):
            pass

        await host.attach(svc.new_session(), send)
        await host.begin(manual=True)
        original = host.generation
        try:
            await asyncio.wait_for(host.end("next_guest"), 0.2)
            await asyncio.wait_for(host.begin(manual=True), 0.2)
            assert host.active and host.generation > original
        finally:
            stopped.set()
            await host.close()

    asyncio.run(run())


def test_new_guest_gets_new_codex_thread_and_old_tools_cannot_edit_it(svc):
    async def run():
        codex = FakeCodex()
        events = []

        async def send(event):
            events.append(event)

        host = InteractionHost(svc, codex=codex)
        await host.attach(svc.new_session(), send)
        await host.begin(manual=True)
        first = host.generation
        old_tool, _ = codex.callbacks[host.thread_id]
        old_token = host.token
        await host.end("next_guest")
        await host.begin(manual=True)
        assert host.generation > first
        assert host.token != old_token
        assert len(codex.threads) == 2
        with pytest.raises(KioskError, match="stale_interaction"):
            await old_tool(
                {
                    "tool": "kiosk_cart",
                    "callId": "old",
                    "arguments": {"action": "add", "item_id": "coffee", "quantity": 1},
                }
            )
        assert host.cart == []
        await host.close()

    asyncio.run(run())


def test_voice_cart_deduplicates_calls_without_placing_an_order(svc):
    async def run():
        codex = FakeCodex()

        async def send(event):
            pass

        host = InteractionHost(svc, codex=codex)
        await host.attach(svc.new_session(), send)
        await host.begin(manual=True)
        tool, _ = codex.callbacks[host.thread_id]
        params = {
            "tool": "kiosk_cart",
            "callId": "once",
            "arguments": {"action": "add", "item_id": "coffee", "quantity": 1},
        }
        await tool(params)
        await tool(params)
        assert host.cart[0]["quantity"] == 1
        await tool(
            {
                "tool": "kiosk_fulfillment",
                "callId": "mode",
                "arguments": {"fulfillment": "takeaway"},
            }
        )
        await tool(
            {
                "tool": "kiosk_cart",
                "callId": "another",
                "arguments": {"action": "add", "item_id": "coffee", "quantity": 1},
            }
        )
        assert host.cart[0]["quantity"] == 2
        assert svc.progress(host.token)["orders"] == []
        await host.close()

    asyncio.run(run())


def test_old_pcm_is_dropped_after_guest_reset(svc):
    class Fusion:
        def __init__(self):
            self.chunks = []

        async def audio(self, pcm):
            self.chunks.append(pcm)

        async def end(self):
            pass

        async def close(self):
            pass

    async def run():
        fusion = Fusion()
        host = InteractionHost(svc, codex=FakeCodex(), fusion=fusion)
        host.active, host.voice_active, host.generation = True, True, 4
        with pytest.raises(KioskError, match="stale_interaction"):
            await host.microphone(3, b"x" * 2560)
        assert fusion.chunks == []
        await host.microphone(4, b"x" * 2560)
        assert len(fusion.chunks) == 1
        await host.end("next_guest")
        with pytest.raises(KioskError):
            await host.microphone(4, b"x" * 2560)
        assert len(fusion.chunks) == 1
        await host.close()

    asyncio.run(run())


def test_checkout_uses_current_cart_and_price_without_second_customer_turn(svc):
    async def run():
        host = InteractionHost(svc, codex=FakeCodex())

        async def send(event):
            pass

        await host.attach(svc.new_session(), send)
        await host.begin(manual=True)
        tool, _ = host.codex.callbacks[host.thread_id]
        try:
            await tool({"tool": "kiosk_menu", "arguments": {"query": "coffee"}})
            await tool({"tool": "kiosk_cart", "arguments": {"action": "add", "item_id": "coffee"}})
            assert svc.progress(host.token)["orders"] == []
            with pytest.raises(KioskError, match="fulfillment_required"):
                await tool({"tool": "kiosk_checkout", "arguments": {}})
            with pytest.raises(KioskError, match="table_required"):
                await tool({"tool": "kiosk_checkout", "arguments": {"fulfillment": "at_table"}})
            item = next(item for item in svc.menu() if item["id"] == "coffee")
            item["price_vnd"] = 35000
            svc.ingest({"menu": {"items": [item]}})
            order = await tool({"tool": "kiosk_checkout", "arguments": {"fulfillment": "takeaway"}})
            assert order["total_vnd"] == 35000
            assert host.cart == []
            assert (await tool({"tool": "kiosk_checkout", "arguments": {}}))["id"] == order["id"]
            await tool(
                {
                    "tool": "kiosk_cart",
                    "arguments": {"action": "add", "item_id": "coffee", "quantity": 2},
                }
            )
            second = await tool({"tool": "kiosk_checkout", "arguments": {}})
            assert second["id"] != order["id"]
            assert second["total_vnd"] == 70000
            assert len(svc.progress(host.token)["orders"]) == 2
        finally:
            await host.close()

    asyncio.run(run())


def test_command_waiting_for_lock_rechecks_guest_generation(svc):
    async def run():
        host = InteractionHost(svc, codex=FakeCodex())

        async def send(event):
            pass

        await host.attach(svc.new_session(), send)
        await host.begin(manual=True)
        await host.lock.acquire()
        command = asyncio.create_task(
            host.command(
                {
                    "type": "action",
                    "generation": host.generation,
                    "action": {"type": "add", "item": {"id": "coffee"}, "quantity": 1},
                }
            )
        )
        await asyncio.sleep(0)
        host.generation += 1
        host.token = svc.new_session()
        host.lock.release()
        with pytest.raises(KioskError, match="stale_interaction"):
            await command
        assert host.cart == []
        await host.close()

    asyncio.run(run())


def test_touch_and_voice_actions_preserve_per_item_and_order_notes(svc):
    async def run():
        codex = FakeCodex()
        host = InteractionHost(svc, codex=codex)
        await host.attach(svc.new_session(), lambda event: asyncio.sleep(0))
        await host.begin(manual=True)
        tool, _ = codex.callbacks[host.thread_id]
        for call_id, note in (("note-a", "ít đá"), ("note-b", "không đường")):
            await tool(
                {
                    "tool": "kiosk_cart",
                    "callId": call_id,
                    "arguments": {
                        "action": "add",
                        "item_id": "coffee",
                        "quantity": 1,
                        "options": {},
                        "note": note,
                    },
                }
            )
        assert [line["note"] for line in host.cart] == ["ít đá", "không đường"]
        first_key = host.cart[0]["key"]
        await host.command(
            {
                "type": "action",
                "generation": host.generation,
                "action": {"type": "line_note", "key": first_key, "value": "ít đá nhé"},
            }
        )
        await tool(
            {
                "tool": "kiosk_order_note",
                "callId": "order-note",
                "arguments": {"note": "gọi khi đến nơi"},
            }
        )
        assert host.order_note == "gọi khi đến nơi"
        assert next(line for line in host.cart if line["key"] == first_key)["note"] == "ít đá nhé"
        assert len({line["key"] for line in host.cart}) == 2
        await host.close()

    asyncio.run(run())


def test_cart_item_id_mutations_are_unambiguous_and_keep_row_order(svc):
    async def run():
        codex = FakeCodex()
        host = InteractionHost(svc, codex=codex)
        await host.attach(svc.new_session(), lambda event: asyncio.sleep(0))
        await host.begin(manual=True)
        tool, _ = codex.callbacks[host.thread_id]

        async def call(call_id, arguments):
            return await tool({"tool": "kiosk_cart", "callId": call_id, "arguments": arguments})

        await call("add-single", {"action": "add", "item_id": "coffee", "quantity": 1})
        await call("set-by-id", {"action": "set", "item_id": "coffee", "quantity": 4})
        assert len(host.cart) == 1
        assert host.cart[0]["quantity"] == 4
        await call("remove-by-id", {"action": "remove", "item_id": "coffee"})
        assert host.cart == []

        await call(
            "add-less-ice", {"action": "add", "item_id": "coffee", "quantity": 1, "note": "ít đá"}
        )
        await call(
            "add-no-sugar",
            {"action": "add", "item_id": "coffee", "quantity": 1, "note": "không đường"},
        )
        keys_before = [line["key"] for line in host.cart]
        with pytest.raises(KioskError, match="ambiguous_cart_line"):
            await call("ambiguous-remove", {"action": "remove", "item_id": "coffee"})
        first = host.cart[0]
        await call(
            "edit-first",
            {
                "action": "set",
                "line_key": first["key"],
                "quantity": 2,
                "note": "ít đá nhé",
            },
        )
        assert [line["key"] for line in host.cart] == keys_before
        assert host.cart[0]["note"] == "ít đá nhé"
        assert host.cart[0]["quantity"] == 2
        with pytest.raises(KioskError, match="cart_line_not_found"):
            await call("stale-key", {"action": "set", "line_key": "stale", "quantity": 3})
        assert [line["key"] for line in host.cart] == keys_before
        await host.close()

    asyncio.run(run())


def test_voice_timeout_reconnects_without_new_guest_or_cart_loss(svc):
    async def run():
        events = []

        class Codex(FakeCodex):
            async def start_filtered_voice(self, thread):
                if len(self.threads) <= 3:
                    raise TimeoutError("ICE negotiation stalled")

        class Fusion:
            async def begin(self, *args):
                pass

            async def playback(self, *args):
                pass

            async def end(self):
                pass

            async def close(self):
                pass

        async def send(event):
            events.append(event)

        codex = Codex()
        host = InteractionHost(svc, codex=codex, fusion=Fusion())
        await host.attach(svc.new_session(), send)
        await host.begin(manual=True)
        assert host.voice_ready
        assert len(codex.threads) == 4
        assert sum(e["type"] == "session" for e in events) == 1
        tool, old_event = codex.callbacks[host.thread_id]
        await tool(
            {
                "tool": "kiosk_cart",
                "arguments": {"action": "add", "item_id": "coffee", "quantity": 1},
            }
        )
        original_cart = list(host.cart)
        original_token, generation = host.token, host.generation
        await old_event("thread/realtime/closed", {})
        for _ in range(30):
            if len(codex.threads) == 5 and host.voice_ready:
                break
            await asyncio.sleep(0.02)
        assert len(codex.threads) == 5 and host.voice_ready
        assert host.cart == original_cart and host.token == original_token
        assert host.generation == generation
        # The retired connection cannot knock the recovered session offline.
        await old_event("thread/realtime/closed", {})
        assert host.voice_ready
        assert sum(e["type"] == "session" for e in events) == 1
        await host.close()

    asyncio.run(run())


@pytest.mark.parametrize("manual", [False, True])
@pytest.mark.parametrize("departure", ["frames", "sensor_loss"])
def test_departure_closes_every_guest_and_revokes_state(svc, manual, departure):
    async def run():
        clock = Clock()
        native = FakeCodex()
        events = []

        async def send(event):
            events.append(event)

        host = InteractionHost(svc, codex=native, clock=clock, wall=clock)
        await host.attach(svc.new_session(), send)
        try:
            if manual:
                await host.begin(manual=True)
            for seq in range(11):
                clock.value = 100 + seq * 0.2
                await host.observe(observation(seq + 1, clock.value))
            if host.start_task:
                await host.start_task
            assert host.active and host.policy.track_id == 7
            thread = host.thread_id
            old_tool = native.callbacks[thread][0]
            host.cart = [{"item": {"id": "coffee"}, "quantity": 1}]
            host.fulfillment, host.table_label, host.order_note = "at_table", "7", "old guest"
            if departure == "frames":
                # A bystander must not keep the departed owner's call alive.
                for seq in range(12, 30):
                    clock.value = 100 + seq * 0.2
                    await host.observe(observation(seq, clock.value, track=8))
            else:
                host.start_background()
                clock.value = 107
                async with asyncio.timeout(1):
                    while host.active:
                        await asyncio.sleep(0.01)
            await asyncio.gather(*host.cleanup_tasks)
            assert not host.active and not host.voice_ready and not host.voice_active
            assert host.thread_id is None and host.token == ""
            assert host.cart == [] and host.quote is None
            assert (host.fulfillment, host.table_label, host.order_note) == ("", "", "")
            assert native.stopped == [thread]
            assert any(e["type"] == "ended" for e in events)
            with pytest.raises(KioskError, match="stale_interaction"):
                await old_tool({"tool": "kiosk_menu", "arguments": {}})
        finally:
            await host.close()

    asyncio.run(run())


def test_manual_guest_leaves_during_connection_cancels_call(svc):
    async def run():
        entered = asyncio.Event()
        cancelled = asyncio.Event()

        class Native(FakeCodex):
            async def create_thread(self, *args):
                entered.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()

        clock = Clock()
        events = []

        async def send(event):
            events.append(event)

        host = InteractionHost(svc, codex=Native(), clock=clock, wall=clock)
        await host.attach(svc.new_session(), send)
        try:
            await host.command({"type": "begin"})
            await entered.wait()
            # A manual start binds the first fresh customer observation.
            await host.observe(observation(1, clock.value))
            for seq in range(2, 20):
                clock.value = 100 + seq * 0.2
                await host.observe(observation(seq, clock.value, distance=1.2))
            await asyncio.wait_for(cancelled.wait(), 1)
            assert not host.active and host.token == ""
            assert not any(e["type"] == "announcement" for e in events)
        finally:
            await host.close()

    asyncio.run(run())


def test_manual_start_with_fresh_empty_camera_ends_without_waiting_for_idle(svc):
    async def run():
        clock = Clock()
        native = FakeCodex()
        host = InteractionHost(svc, codex=native, clock=clock, wall=clock)
        try:
            await host.begin(manual=True)
            for seq in range(20):
                clock.value = 100 + seq * 0.2
                await host.observe(observation(seq + 1, clock.value, distance=1.2))
            await asyncio.gather(*host.cleanup_tasks)
            assert not host.active and native.stopped == native.threads
        finally:
            await host.close()

    asyncio.run(run())


def test_explicit_restart_can_bind_the_same_customer_after_idle():
    policy = PresencePolicy(enter_seconds=0, block_seconds=10.0)
    assert policy.observe(observation(1, 100), 100, 100) == "enter"
    policy.reset(block=True)
    assert policy.observe(observation(2, 101), 101, 101) is None
    assert policy.observe(observation(3, 102), 102, 102, authorized=True) == "enter"
    assert policy.track_id == 7


def test_browser_greeting_requires_microphone_and_confirmed_av_before_and_after_native(svc):
    async def run():
        av_entered, av_release = asyncio.Event(), asyncio.Event()
        checked, stable = asyncio.Event(), asyncio.Event()
        native_started = []
        events = []

        class Native(FakeCodex):
            async def start_filtered_voice(self, thread):
                native_started.append(thread)

        class Fusion:
            async def begin(self, *args):
                av_entered.set()
                await av_release.wait()

            async def check_ready(self):
                checked.set()
                await stable.wait()

            async def playback(self, playing):
                pass

            async def end(self):
                pass

            async def close(self):
                pass

        async def send(event):
            events.append(event)

        host = InteractionHost(svc, codex=Native(), fusion=Fusion())
        await host.attach(svc.new_session(), send, require_microphone=True)
        start = asyncio.create_task(host.begin(manual=True))
        try:
            await asyncio.sleep(0)
            assert host.active and not host.codex.threads
            await host.microphone(host.generation, b"invalid")
            assert not host.microphone_ready.is_set()
            await host.microphone(host.generation, bytes(2560))
            await asyncio.wait_for(av_entered.wait(), 1)
            assert not native_started
            assert not any(e["type"] == "announcement" for e in events)
            av_release.set()
            await asyncio.wait_for(checked.wait(), 1)
            assert native_started and not host.voice_ready
            assert not any(e["type"] == "announcement" for e in events)
            stable.set()
            await asyncio.wait_for(start, 1)
            assert host.voice_ready
            assert sum(e["type"] == "announcement" for e in events) == 1
        finally:
            start.cancel()
            await asyncio.gather(start, return_exceptions=True)
            await host.close()

    asyncio.run(run())


def test_connection_cannot_greet_if_browser_audio_stops_during_handshake(svc):
    async def run():
        clock = Clock()
        native_connected = asyncio.Event()
        events = []

        class Native(FakeCodex):
            async def start_filtered_voice(self, thread):
                clock.value += 2
                native_connected.set()

        class Fusion:
            async def begin(self, *args):
                pass

            async def audio(self, pcm):
                pass

            async def playback(self, playing):
                pass

            async def end(self):
                pass

            async def close(self):
                pass

        async def send(event):
            events.append(event)

        host = InteractionHost(svc, codex=Native(), fusion=Fusion(), clock=clock)
        await host.attach(svc.new_session(), send, require_microphone=True)
        start = asyncio.create_task(host.begin(manual=True))
        try:
            await asyncio.sleep(0)
            await host.microphone(host.generation, bytes(2560))
            await asyncio.wait_for(native_connected.wait(), 1)
            await asyncio.sleep(0)
            assert not start.done() and not host.voice_ready
            assert not any(e["type"] == "announcement" for e in events)
            await host.microphone(host.generation, bytes(2560))
            await asyncio.wait_for(start, 1)
            assert host.voice_ready
            assert sum(e["type"] == "announcement" for e in events) == 1
        finally:
            start.cancel()
            await asyncio.gather(start, return_exceptions=True)
            await host.close()

    asyncio.run(run())


@pytest.mark.parametrize("input_failure", [False, True])
def test_fusion_failure_reconnects_without_repeating_greeting(svc, input_failure):
    async def run():
        events = []

        class Native(FakeCodex):
            async def start_filtered_voice(self, thread):
                pass

        class Fusion:
            failed = False

            async def begin(self, generation, session_id, callback, track_id):
                self.callback = callback

            async def audio(self, pcm):
                if not self.failed:
                    self.failed = True
                    raise RuntimeError("fixture_input_stopped")

            async def playback(self, playing):
                pass

            async def end(self):
                pass

            async def close(self):
                pass

        async def send(event):
            events.append(event)

        host = InteractionHost(svc, codex=Native(), fusion=Fusion())
        await host.attach(svc.new_session(), send)
        try:
            await host.begin(manual=True)
            assert host.voice_ready
            if input_failure:
                await host.microphone(host.generation, bytes(2560))
            else:
                await host.fusion.callback({"type": "error"})
            assert host.recovery_task is not None
            await asyncio.wait_for(host.recovery_task, 1)
            assert host.voice_ready and len(host.codex.threads) == 2
            assert sum(e["type"] == "announcement" for e in events) == 1
        finally:
            await host.close()

    asyncio.run(run())


def test_microphone_level_is_reported_as_numbers_only(svc):
    host = InteractionHost(svc, codex=FakeCodex())
    silence, speech = bytes(2560), struct.pack("<1280h", *([3000, -3000] * 640))
    for pcm in (silence, speech, silence):
        host.audio_level(pcm)
    level = host.audio_metrics["microphone_level"]
    assert level == {"last_rms": 0, "peak_rms": 3000, "speech_packets": 1, "packets": 3}


def test_browser_playback_underruns_are_counted_separately_from_turn_ends(svc):
    async def run():
        now = [100.0]
        host = InteractionHost(svc, codex=FakeCodex(), clock=lambda: now[0])

        async def send(event):
            pass

        await host.attach(svc.new_session(), send)
        await host.begin(manual=True)

        async def playback(at, playing):
            now[0] = at
            await host.command(
                {"type": "playback", "generation": host.generation, "playing": playing}
            )

        await playback(100.0, True)
        await playback(101.0, False)  # buffer ran dry mid-sentence
        await playback(101.2, True)
        await playback(103.0, False)  # end of Trend's reply
        await playback(106.0, True)  # next reply
        assert host.audio_metrics["browser_playback"] == {
            "starts": 3,
            "stops": 2,
            "restarts_within_500ms": 1,
        }
        await host.close()

    asyncio.run(run())


def test_recent_fusion_rows_skip_silence_and_stay_bounded(svc):
    import base64

    async def run():
        class Fusion:
            async def begin(self, generation, session_id, callback, track_id):
                self.callback = callback

            async def playback(self, playing):
                pass

            async def end(self):
                pass

            async def close(self):
                pass

        async def send(event):
            pass

        now = [100.0]

        class Codex(FakeCodex):
            async def start_filtered_voice(self, thread):
                pass

            async def append_audio(self, thread, pcm):
                pass

        host = InteractionHost(svc, codex=Codex(), fusion=Fusion(), clock=lambda: now[0])
        await host.attach(svc.new_session(), send)
        await host.begin(manual=True)
        diagnostics = {"asd_probability": 0.8123456, "mouth": 1.0, "labels": ["TARGET"]}

        async def pcm(reason, accepted=False):
            await host.fusion.callback(
                {
                    "type": "pcm",
                    "data": base64.b64encode(bytes(2560)).decode(),
                    "accepted": accepted,
                    "reason": reason,
                }
            )

        for _ in range(250):
            now[0] += 0.08
            await host.fusion.callback(
                {
                    "type": "fusion",
                    "verdict": "ACCEPT",
                    "locked": False,
                    "source": "asd",
                    "diagnostics": diagnostics,
                }
            )
        for _ in range(500):  # a long silence must not push the interesting rows out
            await pcm("silenced_no_voice")
        await pcm("speaker_unlocked")
        await pcm("kept", accepted=True)
        recent = host.audio_metrics["fusion_recent"]
        assert len(recent) == 200, "bounded"
        assert all(e.get("out") != "silenced_no_voice" for e in recent)
        assert recent[-1] == {"t": 120.0, "out": "kept", "heard": True}
        assert recent[-2] == {"t": 120.0, "out": "speaker_unlocked", "heard": False}
        assert recent[-3] == {"t": 120.0, "v": "ACCEPT", "lock": False, "p": 0.81, "mouth": 1.0}
        await host.close()

    asyncio.run(run())


def test_recent_fusion_log_times_the_guests_transcript_and_native_backlog(svc):
    import base64

    async def run():
        class Fusion:
            async def begin(self, generation, session_id, callback, track_id):
                self.callback = callback

            async def playback(self, playing):
                pass

            async def end(self):
                pass

            async def close(self):
                pass

        class Codex(FakeCodex):
            async def start_filtered_voice(self, thread):
                pass

            async def append_audio(self, thread, pcm):
                pass

            def input_diagnostics(self, thread):
                return {"buffer_ms": 480, "max_buffer_ms": 960}

        async def send(event):
            pass

        now = [100.0]
        host = InteractionHost(svc, codex=Codex(), fusion=Fusion(), clock=lambda: now[0])
        await host.attach(svc.new_session(), send)
        await host.begin(manual=True)
        await host.fusion.callback(
            {
                "type": "pcm",
                "data": base64.b64encode(b"\x10\x00" * 1280).decode(),
                "accepted": True,
                "reason": "kept",
            }
        )
        on_event = host.codex.callbacks[host.thread_id][1]
        now[0] = 101.5
        await on_event(
            "thread/realtime/transcript/delta",
            {"role": "user", "delta": "dạ", "turnId": "u1"},
        )
        now[0] = 101.9
        await on_event(
            "thread/realtime/transcript/done",
            {"role": "user", "text": "dạ", "turnId": "u1"},
        )
        recent = host.audio_metrics["fusion_recent"]
        assert recent[-3] == {"t": 100.0, "out": "kept", "heard": True, "q": 480}
        assert recent[-2] == {"t": 101.5, "tr": "user", "final": False}
        assert recent[-1] == {"t": 101.9, "tr": "user", "final": True}
        assert all("dạ" not in str(entry) for entry in recent), "no transcript text"
        await host.close()

    asyncio.run(run())
