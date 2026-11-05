"""Kiosk voice threads get a readable name and are archived when they stop.

Each guest is a Codex thread. Left alone they pile up in Codex's session list under the
title `<realtime_delegation><input>...`, mixed with the operator's own sessions.
"""

import asyncio
import time
from types import SimpleNamespace

from test_speaker import speaker_host

from trendcoffee.codex_voice import CodexVoice


def voice(tmp_path, fail=()):
    codex = CodexVoice(tmp_path)
    codex.process = SimpleNamespace(returncode=None)
    sent = []

    async def request(method, params, *, timeout=None):
        sent.append(
            (method, params["threadId"], {k: v for k, v in params.items() if k != "threadId"})
        )
        if method in fail:
            raise RuntimeError("codex_request_rejected")
        return {}

    codex.request = request
    return codex, sent


def test_a_stopped_thread_is_archived_after_the_call_ends(tmp_path):
    async def run():
        codex, sent = voice(tmp_path)
        await codex.stop_voice("thread-1")
        assert [m for m, *_ in sent] == [
            "thread/realtime/stop",
            "thread/unsubscribe",
            "thread/archive",
        ], "archived last: nothing is still using the thread"
        assert {t for _, t, _ in sent} == {"thread-1"}

    asyncio.run(run())


def test_a_failing_archive_never_breaks_stopping_the_call(tmp_path):
    async def run():
        codex, sent = voice(tmp_path, fail={"thread/archive", "thread/unsubscribe"})
        await codex.stop_voice("thread-1")  # does not raise
        assert sent[-1][0] == "thread/archive", "still attempted after an earlier failure"
        assert "thread-1" not in codex.callbacks

    asyncio.run(run())


def test_naming_a_thread_sets_its_title_and_never_raises(tmp_path):
    async def run():
        codex, sent = voice(tmp_path)
        await codex.name_thread("thread-1", "Kiosk 11:41 — đang phục vụ")
        assert sent == [("thread/name/set", "thread-1", {"name": "Kiosk 11:41 — đang phục vụ"})]
        failing, _ = voice(tmp_path, fail={"thread/name/set"})
        await failing.name_thread("thread-1", "x")  # naming is cosmetic

    asyncio.run(run())


class Recording:
    """Wraps the host's fake Codex and records naming and stopping in order."""

    def __init__(self, base):
        self.base, self.calls = base, []

    def __getattr__(self, name):
        return getattr(self.base, name)

    async def name_thread(self, thread, name):
        self.calls.append(("name", thread, name))

    async def stop_voice(self, thread):
        self.calls.append(("stop", thread))
        await self.base.stop_voice(thread)


def hhmm(wall):
    return time.strftime("%H:%M", time.localtime(wall))


def test_a_guest_thread_is_named_at_the_start_and_with_its_times_at_the_end(svc):
    async def run():
        async def send(event):
            pass

        host, _ = speaker_host(svc)
        host.codex = Recording(host.codex)
        start, finish = 1_793_700_000.0, 1_793_700_000.0 + 190
        host.wall = lambda: start
        await host.attach(svc.new_session(), send)
        await host.begin(manual=True)
        await asyncio.gather(*host.cleanup_tasks)
        thread = host.thread_id
        assert host.codex.calls == [("name", thread, f"Kiosk {hhmm(start)} — đang phục vụ")]
        host.wall = lambda: finish
        await host.end("next_guest")
        await asyncio.gather(*host.cleanup_tasks)
        assert host.codex.calls[1:] == [
            ("name", thread, f"Kiosk {hhmm(start)}–{hhmm(finish)}"),
            ("stop", thread),
        ], "the final title is set before the call stops (and the thread is archived)"
        await host.close()

    asyncio.run(run())


def test_naming_does_not_hold_back_the_greeting(svc):
    async def run():
        events = []

        async def send(event):
            events.append(event["type"])

        class Slow(Recording):
            async def name_thread(self, thread, name):
                await asyncio.sleep(5)  # a hung Codex request

        host, _ = speaker_host(svc)
        host.codex = Slow(host.codex)
        await host.attach(svc.new_session(), send)
        await asyncio.wait_for(host.begin(manual=True), 2)
        assert "announcement" in events
        for task in list(host.cleanup_tasks):
            task.cancel()
        await host.close()

    asyncio.run(run())


def test_ending_a_call_keeps_the_thread_for_the_same_guest(tmp_path):
    async def run():
        codex, sent = voice(tmp_path)

        async def on_tool(params):
            pass

        async def on_event(method, params):
            pass

        codex.callbacks["thread-1"] = (on_tool, on_event)
        codex._thread_process["thread-1"] = codex.process
        await codex.end_call("thread-1")
        assert [m for m, *_ in sent] == ["thread/realtime/stop"], "no unsubscribe, no archive"
        assert "thread-1" in codex.callbacks
        assert await codex.resume_thread("thread-1", on_event, on_tool) == "thread-1"
        assert codex.callbacks["thread-1"] == (on_event, on_tool), "the new call's handlers"

    asyncio.run(run())


def test_a_thread_from_another_codex_process_cannot_be_resumed(tmp_path):
    async def run():
        codex, _ = voice(tmp_path)

        async def handler(*args):
            pass

        for thread, process in (("unknown", None), ("old", SimpleNamespace(returncode=0))):
            if process is not None:
                codex._thread_process[thread] = process
            try:
                await codex.resume_thread(thread, handler, handler)
            except RuntimeError as error:
                assert str(error) == "voice_thread_not_resumable"
            else:
                raise AssertionError(thread)

    asyncio.run(run())


def resumable_host(svc, *, resume_fails=False, fusion_failures=0, voice_failures=0):
    """A host whose fake Codex can end a call and resume a thread, counting each."""
    host, _ = speaker_host(svc)
    codex = host.codex
    log = []

    async def create_thread(tools, on_tool, on_event, catalog=None):
        log.append("create")
        return await type(codex).create_thread(codex, tools, on_tool, on_event, catalog)

    async def resume_thread(thread, on_tool, on_event):
        log.append(("resume", thread))
        if resume_fails:
            raise RuntimeError("voice_thread_not_resumable")
        codex.callbacks[thread] = (on_tool, on_event)
        return thread

    async def end_call(thread):
        log.append(("end_call", thread))

    failures = {"voice": voice_failures}

    async def start_filtered_voice(thread):
        if failures["voice"]:
            failures["voice"] -= 1
            raise RuntimeError("codex_voice_unavailable")

    async def stop_voice(thread):
        log.append(("stop", thread))
        codex.stopped.append(thread)

    codex.create_thread, codex.resume_thread, codex.end_call = (
        create_thread,
        resume_thread,
        end_call,
    )
    codex.start_filtered_voice, codex.stop_voice = start_filtered_voice, stop_voice
    fusion_begin, fusion_left = host.fusion.begin, [fusion_failures]

    async def begin(*args):
        if fusion_left[0]:
            fusion_left[0] -= 1
            raise TimeoutError
        await fusion_begin(*args)

    host.fusion.begin = begin
    return host, log


async def until(condition, seconds=3):
    for _ in range(int(seconds / 0.02)):
        if condition():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("condition not reached")


async def guest(host, svc):
    async def send(event):
        pass

    await host.attach(svc.new_session(), send)
    await host.begin(manual=True)


def test_a_voice_drop_reconnects_on_the_same_thread(svc, caplog):
    caplog.set_level("WARNING", logger="trendcoffee.kiosk")

    async def run():
        host, log = resumable_host(svc)
        await guest(host, svc)
        thread = host.thread_id
        assert host.voice_ready and log == ["create"]
        on_event = host.codex.callbacks[thread][1]
        await on_event("thread/realtime/closed", {"threadId": thread})
        await until(lambda: host.voice_ready)
        assert host.thread_id == thread, "the conversation stays one thread"
        assert log == ["create", ("end_call", thread), ("resume", thread)]
        drops = [r.getMessage() for r in caplog.records if "Voice call dropped" in r.getMessage()]
        assert len(drops) == 1 and "closed" in drops[0], "each mid-session drop is logged"
        await host.end("next_guest")
        await asyncio.gather(*host.cleanup_tasks)
        assert log[-1] == ("stop", thread), "stopped (and archived) once, at the end"
        await host.close()

    asyncio.run(run())


def test_a_failed_av_wait_keeps_the_thread_instead_of_making_empty_ones(svc):
    async def run():
        host, log = resumable_host(svc, fusion_failures=2)
        await guest(host, svc)
        await until(lambda: host.voice_ready)
        assert log.count("create") == 1
        assert [entry[0] for entry in log if entry != "create"] == [
            "end_call",
            "resume",
            "end_call",
            "resume",
        ]
        await host.close()

    asyncio.run(run())


def test_a_thread_that_cannot_carry_a_call_is_replaced(svc):
    async def run():
        host, log = resumable_host(svc, voice_failures=1)
        await guest(host, svc)
        await until(lambda: host.voice_ready)
        first, second = [i for i, entry in enumerate(log) if entry == "create"]
        assert ("stop", host.codex.threads[0]) in log[first:second], "the failed one is retired"
        assert host.thread_id == host.codex.threads[1]
        await host.close()

    asyncio.run(run())


def test_a_thread_that_cannot_be_resumed_is_replaced(svc):
    async def run():
        host, log = resumable_host(svc, resume_fails=True)
        await guest(host, svc)
        old = host.thread_id
        await host.codex.callbacks[old][1]("thread/realtime/closed", {"threadId": old})
        await until(lambda: host.voice_ready and host.thread_id != old)
        assert ("stop", old) in log and log.count("create") == 2
        await host.close()

    asyncio.run(run())
