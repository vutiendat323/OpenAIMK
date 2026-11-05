"""Bounded IPC to the copied Audio stack. Native voice never gets raw PCM."""

import asyncio
import base64
import contextlib
import json
import logging
import os
from collections import deque
from pathlib import Path


def accepted_pcm(pcm, *, verdict, reason, locked, fresh):
    safe = (
        locked
        and fresh
        and (
            (verdict.upper() == "ACCEPT" and reason == "kept")
            or (reason in ("kept_onset", "kept_tail") and verdict.upper() in ("NONE", "ACCEPT"))
            or (reason in ("kept_target_onset", "kept_target_tail") and verdict.upper() == "ACCEPT")
            or (verdict.upper() in ("ACCEPT", "UNCERTAIN") and reason == "separated")
        )
    )
    return pcm if safe else bytes(len(pcm))


# A guest's first answer is often one short word ("dạ", "có") that ends before the
# six-row speaker lock. Light-ASD confidence ramps up over a word (measured "dạ":
# 0.40 ... 0.96), so most of its rows are ACCEPTed on mouth activity without a face
# id. User decision 2026-11-03: release that first answer when it has at least three
# ACCEPT rows, at least two of them ASD-confirmed on the guest's own face.
SHORT_FIRST_ROWS = 3
SHORT_FIRST_ASD_ROWS = 2
SHORT_FIRST_END_ROWS = 4  # 320 ms without accepted speech ends the utterance


class FusionPreroll:
    """Retain approved word onsets until their recorded face is locked."""

    def __init__(self):
        self.pending = deque()
        self.short_first_used = False

    def clear(self):
        """A new guest: discard held words and allow one short first answer again."""
        self.pending.clear()
        self.short_first_used = False

    def _short_first(self, owner_track):
        """Release a finished short first answer from the guest's face, or None."""
        if self.short_first_used or len(self.pending) < SHORT_FIRST_END_ROWS:
            return None
        rows = list(self.pending)
        tail = rows[-SHORT_FIRST_END_ROWS:]
        if any(any(data) or any(loose) for _, _, data, _, _, loose in tail):
            return None  # still speaking: the normal lock may still arrive
        # Every face with ASD-confirmed speech in this utterance, including faces whose
        # audio was already silenced as not the guest's (a companion talking).
        speakers = {
            track
            for _, track, _, _, verdict, _ in rows
            if verdict == "ACCEPT" and track is not None
        }
        owner = owner_track if owner_track is not None else next(iter(speakers), None)
        if owner is None or speakers != {owner}:
            return None
        confirmed = sum(1 for _, track, data, _, _, _ in rows if track == owner and any(data))
        accepted = confirmed + sum(1 for _, _, _, _, _, loose in rows if any(loose))
        if confirmed < SHORT_FIRST_ASD_ROWS or accepted < SHORT_FIRST_ROWS:
            return None
        self.pending.clear()
        self.short_first_used = True
        return [
            (data if track == owner else loose, "kept_short_first")
            for _, track, data, _, _, loose in rows
        ]

    def push(self, *, pcm, verdict, reason, track_id, locked_track, owner_track, fresh, now):
        silence = bytes(len(pcm))
        while self.pending and now - self.pending[0][0] > 2:
            self.pending.popleft()
        if not fresh:
            self.pending.clear()
            return [(silence, "visual_stale")]
        candidate = track_id is not None and (owner_track is None or track_id == owner_track)
        approved = accepted_pcm(pcm, verdict=verdict, reason=reason, locked=candidate, fresh=True)
        # An ACCEPT row without a face id (mouth activity, ASD not yet confident) is
        # kept aside: only a short first answer may use it, never the lock replay.
        loose = (
            accepted_pcm(pcm, verdict=verdict, reason=reason, locked=True, fresh=True)
            if track_id is None and verdict.upper() == "ACCEPT"
            else bytes(len(pcm))
        )
        if locked_track is None:
            if self.pending or any(approved) or verdict.upper() == "ACCEPT":
                self.pending.append((now, track_id, approved, reason, verdict.upper(), loose))
                while len(self.pending) > 24:
                    self.pending.popleft()
            return self._short_first(owner_track) or [(silence, "speaker_unlocked")]
        if owner_track is not None and locked_track != owner_track:
            self.pending.clear()
            return [(silence, "owner_mismatch")]
        result = [
            (data if track == locked_track else bytes(len(data)), why)
            for _, track, data, why, _, _ in self.pending
        ]
        self.pending.clear()
        current = accepted_pcm(
            pcm,
            verdict=verdict,
            reason=reason,
            locked=track_id == locked_track,
            fresh=True,
        )
        result.append(
            (current, reason if track_id == locked_track or not any(pcm) else "owner_mismatch")
        )
        return result


class FusionProcess:
    # The worker waits up to 10 s for a face before it answers `error`; this is the API's
    # patience for any answer at all. Silence means the worker or the pipe is broken.
    reply_timeout = 15
    silent_limit = 2  # consecutive silent commands before the worker is replaced

    def __init__(self, root, visual_url):
        self.root, self.url = Path(root).resolve(), visual_url
        self.process = self.reader = self.ready = None
        self.on_event = None
        self.generation = None
        self.session_ready = None
        self.request_id = 0
        self.silent = 0
        self.lock = asyncio.Lock()

    async def _stop_process(self):
        process, self.process = self.process, None
        if process is not None and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 3)
            except TimeoutError:
                process.kill()
                await process.wait()

    async def start(self):
        async with self.lock:
            if self.process is not None and self.process.returncode is None:
                if self.reader is not None and self.reader.done():
                    # Alive but unheard: every `begin` would wait 12 s for a reply nobody
                    # reads. Replace the worker (its models reload) instead of staying stuck.
                    logging.getLogger(__name__).warning(
                        "av_worker reader had ended while the worker was alive; restarting it"
                    )
                    await self._stop_process()
                else:
                    if self.ready:
                        await asyncio.wait_for(asyncio.shield(self.ready), 180)
                    return
            self.ready = asyncio.get_running_loop().create_future()
            python = os.environ.get("TREND_AV_PYTHON", str(self.root / "Visual/.venv/bin/python"))
            env = {
                **os.environ,
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONPATH": str(self.root / "Audio/src") + os.pathsep + str(self.root),
                "TREND_VISUAL_URL": self.url or "ws://127.0.0.1:9877",
                "HF_HOME": str(self.root / ".runtime/huggingface"),
                "NEMO_CACHE_DIR": str(self.root / ".runtime/torch/NeMo"),
                "TORCH_HOME": str(self.root / ".runtime/torch"),
            }
            (self.root / ".runtime").mkdir(exist_ok=True)
            diagnostic = (self.root / ".runtime/av-worker.log").open("ab")
            self.process = await asyncio.create_subprocess_exec(
                python,
                "-B",
                "-m",
                "trendcoffee.av_worker",
                cwd=self.root,
                env=env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=diagnostic,
                limit=2 * 1024 * 1024,
            )
            diagnostic.close()
            self.reader = asyncio.create_task(self._read())
            await asyncio.wait_for(asyncio.shield(self.ready), 180)

    async def _write(self, message):
        if self.process is None or self.process.returncode is not None:
            raise RuntimeError("fusion_worker_unavailable")
        data = (json.dumps(message, ensure_ascii=False) + "\n").encode()
        self.process.stdin.write(data)
        await asyncio.wait_for(self.process.stdin.drain(), 1)

    async def _read(self):
        log = logging.getLogger(__name__)
        try:
            while True:
                try:
                    raw = await self.process.stdout.readline()
                except ValueError:
                    # A line over the stream limit: asyncio dropped it; keep reading.
                    log.warning("av_worker wrote an over-long line to its protocol pipe; skipped")
                    continue
                if not raw:
                    break
                try:
                    event = json.loads(raw)
                except ValueError:
                    event = None
                if not isinstance(event, dict):
                    # A library wrote to the pipe that carries the JSON lines.
                    log.warning(
                        "av_worker wrote %d bytes that are not a JSON event; skipped", len(raw)
                    )
                    continue
                try:
                    if event.get("type") == "ready":
                        if not self.ready.done():
                            self.ready.set_result(True)
                    elif event.get("type") == "fatal":
                        raise RuntimeError("fusion_models_unavailable")
                    elif event.get("generation") == self.generation and event.get("type") in (
                        "session_ready",
                        "error",
                    ):
                        if event.get("request_id") != self.request_id:
                            continue
                        self.silent = 0  # the worker is alive and its replies are read
                        if self.session_ready and not self.session_ready.done():
                            if event["type"] == "session_ready":
                                self.session_ready.set_result(True)
                            else:
                                self.session_ready.set_exception(
                                    RuntimeError("fusion_session_unavailable")
                                )
                        elif event["type"] == "error" and self.on_event:
                            await self.on_event(event)
                    elif self.on_event and event.get("generation") == self.generation:
                        await self.on_event(event)
                except asyncio.CancelledError:
                    raise
                except RuntimeError as error:
                    if str(error) == "fusion_models_unavailable":
                        raise
                    log.exception("av_worker event handler failed for %s", event.get("type"))
                except Exception:
                    # One bad event must not leave every later reply unread.
                    log.exception("av_worker event handler failed for %s", event.get("type"))
        except (Exception, asyncio.CancelledError):
            pass
        finally:
            returncode = getattr(self.process, "returncode", None)
            log.warning("av_worker reader ended (worker returncode %s)", returncode)
            if self.session_ready and not self.session_ready.done():
                self.session_ready.set_exception(RuntimeError("fusion_session_unavailable"))
            if self.ready and not self.ready.done():
                self.ready.set_exception(RuntimeError("fusion_models_unavailable"))
            if self.on_event:
                with contextlib.suppress(Exception):
                    await self.on_event({"type": "error", "generation": self.generation})

    async def begin(self, generation, session_id, on_event, track_id=None):
        await self.start()
        self.generation, self.on_event = generation, on_event
        await self._session_command(
            {
                "type": "begin",
                "generation": generation,
                "session_id": session_id,
                "track_id": track_id,
            }
        )

    async def _session_command(self, message):
        self.request_id += 1
        ready = self.session_ready = asyncio.get_running_loop().create_future()
        try:
            await self._write({**message, "request_id": self.request_id})
            await asyncio.wait_for(ready, self.reply_timeout)
        except TimeoutError:
            await self._worker_was_silent(message.get("type"))
            raise
        finally:
            if not ready.done():
                ready.cancel()

    async def _worker_was_silent(self, kind):
        """No answer at all: after repeated silence, replace the worker instead of retrying it."""
        self.silent += 1
        log = logging.getLogger(__name__)
        log.warning(
            "av_worker did not answer %s within %ss (%d in a row)",
            kind,
            self.reply_timeout,
            self.silent,
        )
        if self.silent < self.silent_limit:
            return
        log.warning("av_worker is not answering; stopping it so the next session starts a new one")
        self.silent = 0
        async with self.lock:
            await self._stop_process()
            if self.reader is not None:
                self.reader.cancel()
                await asyncio.gather(self.reader, return_exceptions=True)
                self.reader = None

    async def check_ready(self):
        await self._session_command({"type": "check_ready", "generation": self.generation})

    async def audio(self, pcm):
        if self.generation is None or len(pcm) != 2560:
            return
        if self.process.stdin.transport.get_write_buffer_size() > 65536:
            raise RuntimeError("fusion_input_backpressure")
        await self._write(
            {
                "type": "audio",
                "generation": self.generation,
                "data": base64.b64encode(pcm).decode("ascii"),
            }
        )

    async def playback(self, playing):
        if self.generation is not None:
            await self._write(
                {"type": "playback", "generation": self.generation, "playing": playing}
            )

    async def end(self):
        if self.session_ready and not self.session_ready.done():
            self.session_ready.cancel()
        generation, self.generation = self.generation, None
        self.on_event = None
        if self.process and self.process.returncode is None:
            await self._write({"type": "end", "generation": generation})

    async def close(self):
        with contextlib.suppress(Exception):
            await self.end()
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 3)
            except TimeoutError:
                self.process.kill()
                await self.process.wait()
        if self.reader:
            self.reader.cancel()
            await asyncio.gather(self.reader, return_exceptions=True)
