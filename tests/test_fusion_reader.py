"""The API's reader of the av_worker's replies must outlive any single bad event.

Symptom (2026-11-03/04): "Đang chờ camera thấy rõ khuôn mặt và kết nối A-V…" after 1-2 hours,
cleared only by an API restart. Every `begin` timed out after 12 s while the worker was alive
and idle and logged nothing. The reader is one task that dies on the first exception and nothing
restarts it, so every later reply (including `session_ready`) goes unread.
"""

import asyncio
import logging
from types import SimpleNamespace

import pytest

from trendcoffee.av_transport import FusionProcess


class Harness:
    """A FusionProcess wired to an in-memory worker pipe; the test plays the worker."""

    def __init__(self, on_event=None):
        self.fusion = FusionProcess(".", None)
        self.output = asyncio.StreamReader()
        self.fusion.process = SimpleNamespace(stdout=self.output, returncode=None)
        self.writes = []
        self.events = []

        async def start():
            pass

        async def write(message):
            self.writes.append(message)

        async def event(message):
            self.events.append(message)
            if on_event:
                await on_event(message)

        self.fusion.start, self.fusion._write, self.event = start, write, event
        self.fusion.ready = asyncio.get_running_loop().create_future()
        self.fusion.reader = asyncio.create_task(self.fusion._read())

    def reply(self, raw):
        self.output.feed_data(raw if isinstance(raw, bytes) else raw.encode())

    async def begin(self, generation):
        task = asyncio.create_task(self.fusion.begin(generation, "fixture", self.event))
        await asyncio.sleep(0.01)
        request = self.fusion.request_id
        self.reply(f'{{"type":"session_ready","generation":{generation},"request_id":{request}}}\n')
        await asyncio.wait_for(task, 2)

    async def close(self):
        reader = self.fusion.reader  # None once the worker was replaced
        if reader is not None:
            reader.cancel()
            await asyncio.gather(reader, return_exceptions=True)


def test_a_line_that_is_not_json_is_skipped_and_later_replies_still_arrive(caplog):
    async def run():
        harness = Harness()
        await harness.begin(1)
        harness.reply(b"WARNING: a library wrote to the protocol pipe\n")
        harness.reply(b"42\n")  # valid JSON that is not an event
        harness.reply(b"[1,2]\n")
        await asyncio.sleep(0.01)
        assert not harness.fusion.reader.done(), "the reader survived"
        await harness.begin(2)  # a later session still gets its session_ready
        await harness.close()

    with caplog.at_level(logging.WARNING, logger="trendcoffee.av_transport"):
        asyncio.run(run())
    skipped = [r.getMessage() for r in caplog.records if "not a JSON event" in r.getMessage()]
    assert len(skipped) == 3, "every skipped line is logged"


def test_an_over_long_line_is_skipped(caplog):
    async def run():
        harness = Harness()
        harness.output._limit = 64  # a line longer than the stream limit
        harness.reply(b"x" * 500 + b"\n")
        await asyncio.sleep(0.01)
        assert not harness.fusion.reader.done()
        await harness.begin(1)
        await harness.close()

    with caplog.at_level(logging.WARNING, logger="trendcoffee.av_transport"):
        asyncio.run(run())
    assert any("over-long" in r.getMessage() for r in caplog.records)


def test_a_failing_event_handler_does_not_end_the_reader(caplog):
    async def run():
        async def failing(message):
            if message.get("type") == "pcm":
                raise RuntimeError("native voice closed")

        harness = Harness(on_event=failing)
        await harness.begin(1)
        harness.reply('{"type":"pcm","generation":1,"data":"AA=="}\n')
        await asyncio.sleep(0.01)
        assert not harness.fusion.reader.done(), "one bad callback must not stop all replies"
        harness.reply('{"type":"fusion","generation":1,"verdict":"ACCEPT"}\n')
        await asyncio.sleep(0.01)
        assert [e["type"] for e in harness.events] == ["pcm", "fusion"], "later events delivered"
        await harness.begin(2)
        await harness.close()

    with caplog.at_level(logging.WARNING, logger="trendcoffee.av_transport"):
        asyncio.run(run())
    assert any("event handler failed" in r.getMessage() for r in caplog.records)


def test_a_fatal_worker_event_still_ends_the_reader_and_fails_the_wait():
    async def run():
        harness = Harness()
        waiting = asyncio.create_task(harness.fusion.begin(1, "fixture", harness.event))
        await asyncio.sleep(0.01)
        harness.reply('{"type":"fatal","error":"RuntimeError"}\n')
        with pytest.raises(RuntimeError, match="fusion_session_unavailable"):
            await asyncio.wait_for(waiting, 2)
        assert harness.fusion.reader.done()
        await harness.close()

    asyncio.run(run())


def test_a_reader_that_ended_while_the_worker_lives_restarts_the_worker(caplog):
    """Safety net: never keep a worker whose replies nobody reads."""

    async def run():
        fusion = FusionProcess(".", None)
        killed, spawned = [], []

        class Process:
            returncode = None

            def terminate(self):
                killed.append("terminate")

            async def wait(self):
                self.returncode = -15

            def kill(self):
                killed.append("kill")

        fusion.process = Process()
        fusion.ready = asyncio.get_running_loop().create_future()
        fusion.ready.set_result(True)

        async def dead_reader():
            return

        fusion.reader = asyncio.create_task(dead_reader())
        await asyncio.sleep(0)

        async def spawn(*args, **kwargs):
            spawned.append(args)
            raise RuntimeError("stop here: a new worker was requested")

        import asyncio as asyncio_module

        original = asyncio_module.create_subprocess_exec
        asyncio_module.create_subprocess_exec = spawn
        try:
            with pytest.raises(RuntimeError, match="new worker was requested"):
                await fusion.start()
        finally:
            asyncio_module.create_subprocess_exec = original
        assert killed == ["terminate"], "the old worker was stopped"
        assert len(spawned) == 1, "and a new one was started"

    with caplog.at_level(logging.WARNING, logger="trendcoffee.av_transport"):
        asyncio.run(run())
    assert any("reader had ended" in r.getMessage() for r in caplog.records)


def test_the_reader_leaves_a_log_line_when_it_ends(caplog):
    async def run():
        harness = Harness()
        harness.output.feed_eof()
        await asyncio.wait_for(harness.fusion.reader, 2)

    with caplog.at_level(logging.WARNING, logger="trendcoffee.av_transport"):
        asyncio.run(run())
    assert any("reader ended" in r.getMessage() for r in caplog.records)


class Worker:
    """A worker process stand-in that records being stopped."""

    returncode = None

    def __init__(self):
        self.stopped = []

    def terminate(self):
        self.stopped.append("terminate")

    async def wait(self):
        self.returncode = -15

    def kill(self):
        self.stopped.append("kill")


def silent_worker_harness():
    harness = Harness()
    harness.fusion.reply_timeout = 0.05
    harness.worker = Worker()
    harness.fusion.process = SimpleNamespace(
        stdout=harness.output,
        returncode=None,
        terminate=harness.worker.terminate,
        wait=harness.worker.wait,
        kill=harness.worker.kill,
    )
    return harness


def test_a_worker_that_does_not_answer_twice_in_a_row_is_replaced(caplog):
    async def run():
        harness = silent_worker_harness()
        for generation in (1, 2):
            with pytest.raises(TimeoutError):
                await harness.fusion.begin(generation, "fixture", harness.event)
            if generation == 1:
                assert harness.worker.stopped == [], "one silent miss is tolerated"
        assert harness.worker.stopped == ["terminate"], "two in a row: the worker is stopped"
        assert harness.fusion.process is None, "the next begin starts a fresh worker"
        await harness.close()

    with caplog.at_level(logging.WARNING, logger="trendcoffee.av_transport"):
        asyncio.run(run())
    assert any("did not answer" in r.getMessage() for r in caplog.records)


def test_an_answer_resets_the_silence_count():
    async def run():
        harness = silent_worker_harness()
        with pytest.raises(TimeoutError):
            await harness.fusion.begin(1, "fixture", harness.event)
        harness.fusion.reply_timeout = 2
        await harness.begin(2)  # the worker answers
        harness.fusion.reply_timeout = 0.05
        with pytest.raises(TimeoutError):
            await harness.fusion.begin(3, "fixture", harness.event)
        assert harness.worker.stopped == [], "misses were not consecutive"
        await harness.close()

    asyncio.run(run())


def test_a_worker_that_answers_with_an_error_is_never_replaced():
    """`error` is the worker saying no face yet: it is alive and reading."""

    async def run():
        harness = silent_worker_harness()
        harness.fusion.reply_timeout = 2
        for generation in (1, 2, 3):
            task = asyncio.create_task(harness.fusion.begin(generation, "fixture", harness.event))
            await asyncio.sleep(0.01)
            request = harness.fusion.request_id
            harness.reply(f'{{"type":"error","generation":{generation},"request_id":{request}}}\n')
            with pytest.raises(RuntimeError, match="fusion_session_unavailable"):
                await asyncio.wait_for(task, 2)
        assert harness.worker.stopped == []
        await harness.close()

    asyncio.run(run())
