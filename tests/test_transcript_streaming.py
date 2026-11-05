import asyncio

from test_kiosk_runtime import FakeCodex

from trendcoffee.kiosk import InteractionHost


def test_transcript_deltas_emit_cumulative_partial_then_final(svc):
    async def run():
        class ReadyCodex(FakeCodex):
            async def start_filtered_voice(self, thread):
                pass

        class Fusion:
            async def begin(self, *args):
                pass

            async def playback(self, playing):
                pass

            async def end(self):
                pass

            async def close(self):
                pass

        codex = ReadyCodex()
        host = InteractionHost(svc, codex=codex, fusion=Fusion())
        events = []

        async def send(event):
            events.append(event)

        host.send = send
        host.generation = 3
        host.active = True
        await host._open_voice(3)
        assert host.voice_ready and host.greeted
        on_event = codex.callbacks["thread-1"][1]

        await on_event(
            "thread/realtime/transcript/delta",
            {"role": "user", "delta": "Cho mình ", "turnId": "turn-1"},
        )
        await on_event(
            "thread/realtime/transcript/delta",
            {"role": "user", "delta": "cà phê", "turnId": "turn-1"},
        )
        await on_event(
            "thread/realtime/transcript/done",
            {"role": "user", "text": "Cho mình cà phê muối", "turnId": "turn-1"},
        )

        transcript = [event for event in events if event["type"] == "transcript"]
        assert [(event["text"], event["partial"]) for event in transcript] == [
            ("Cho mình ", True),
            ("Cho mình cà phê", True),
            ("Cho mình cà phê muối", False),
        ]
        assert all(event["turnId"] == "turn-1" for event in transcript)
        await host.close()

    asyncio.run(run())
