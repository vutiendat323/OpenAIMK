"""The target-speaker gate with a locked customer (fusion spec 2026-09-30 §5)."""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence

import numpy as np

from audio.domain.evidence import VISION_WINDOW_SECS, FaceTrackBuffer
from audio.domain.gate import AudioOnlyGate
from audio.domain.identity import ROW_SECS, Label, LockState, TargetLock
from audio.domain.settings import SpeakerSettings
from audio.domain.verdict import Verdict


class FusionGate(AudioOnlyGate):
    """The target-speaker gate with a locked customer (spec §5).

    Before the lock it is the AudioOnlyGate, plus bot-voiceprint echo. Once
    Light-ASD has confirmed one face and one diarizer slot together, a row's
    verdict follows who each active slot is, not whose mouth moves nearest.
    """

    def __init__(
        self,
        settings: SpeakerSettings,
        faces: FaceTrackBuffer | None,
        *,
        fsm_state: Callable[[], str],
        bot_voiceprint: Callable[[], np.ndarray | None] = lambda: None,
    ) -> None:
        super().__init__(settings, faces=faces)
        self.settings = settings
        self.lock = TargetLock(settings)
        self._fsm_state = fsm_state
        self._bot_voiceprint = bot_voiceprint
        self.row_voices: list[int] = []
        self.row_asd_track: int | None = None
        self.row_is_target = False
        self.target_overlap = False
        self.target_speaking_visibly = False
        self.last_source: str | None = None
        self.echo_rejects = 0

    @property
    def locked(self) -> bool:
        return self.lock.locked

    def apply_live_settings(self, settings: SpeakerSettings) -> None:
        super().apply_live_settings(settings)
        self.settings = settings
        self.lock._s = settings

    def asd_wait_track(self, t: float) -> int | None:
        """The pinned customer once locked: Vision pushes ASD for them only,
        so waiting on a nearer face would time out every chunk."""
        pinned = self.lock.desired_pin(t)
        return pinned if pinned is not None else super().asd_wait_track(t)

    def frame(
        self,
        probs: Sequence[float],
        *,
        bot_speaking: bool,
        t: float | None = None,
        asd_stream_id: str | None = None,
    ) -> Verdict | None:
        t = time.time() if t is None else t
        self.lock.observe_fsm(self._fsm_state(), t)
        self.lock.bot_voiceprint = self._bot_voiceprint()
        self.row_voices, self.row_asd_track, self.row_is_target = [], None, False
        self.target_overlap = self.target_speaking_visibly = False
        self.last_source = None
        if self.lock.locked:
            verdict = self._locked_frame(probs, bot_speaking, t, asd_stream_id)
        else:
            verdict = self._pre_lock_frame(probs, bot_speaking, t, asd_stream_id)
        if (
            verdict is Verdict.REJECT
            and not self.row_voices
            and any(p >= self._threshold for p in probs)
        ):
            self.echo_rejects += 1
        return verdict

    def _pre_lock_frame(self, probs, bot_speaking, t, stream_id):
        verdict = super().frame(
            probs, bot_speaking=bot_speaking, t=t, asd_stream_id=stream_id
        )
        active = [s for s, p in enumerate(probs) if p >= self._threshold]
        self.row_voices = [
            s
            for s in active
            if self.lock.label(s, bot_echo=self.is_echo(s)) is not Label.BOT
        ]
        if active and not self.row_voices:
            verdict = Verdict.REJECT  # the bot's own voice, known by its voiceprint
        detail = self.last_evidence_detail or {}
        anchor = detail.get("track_id")
        confirmed = verdict is Verdict.ACCEPT and detail.get("source") == "asd"
        if verdict is Verdict.ACCEPT:
            self.last_source = detail.get("source")
        if confirmed:
            self.row_asd_track = anchor
        self._update_binder(t, probs, anchor, detail.get("probability"))
        if self.lock.state is LockState.PRE_LOCK:
            self.lock.observe_row(
                t, self.row_voices, anchor=anchor, anchor_asd_accept=confirmed
            )
        return verdict

    def _locked_frame(self, probs, bot_speaking, t, stream_id):
        lock = self.lock
        active = [s for s, p in enumerate(probs) if p >= self._threshold]
        for s in active:
            self._active_frames[s] += 1
            if bot_speaking:
                self._bot_frames[s] += 1
        labels = {s: lock.label(s, bot_echo=self.is_echo(s)) for s in active}
        voices = [s for s in active if labels[s] is not Label.BOT]
        self.row_voices = voices
        # The customer's slots are one voice: Sortformer often runs two of
        # them at once for the same speaker, which is not an overlap.
        others = [s for s in voices if labels[s] is not Label.TARGET]
        overlap = self._overlap.update(len(others) + (len(others) < len(voices)))
        visible, asd, mouth = self._target_evidence(t, stream_id)
        asd_ok = asd is not None and asd >= self._asd_accept
        mouth_ok = mouth is not None and mouth >= self._mouth_active
        anchor, anchor_ok = (
            self._rebind_evidence(t, stream_id)
            if lock.target_absent(t)
            else (None, False)
        )
        lock.observe_row(
            t,
            voices,
            anchor=anchor,
            anchor_asd_accept=anchor_ok,
            target_visible=visible,
            target_asd_accept=asd_ok,
        )
        self._update_binder(t, probs, lock.target_track, asd)
        targets = [s for s in voices if labels[s] is Label.TARGET]
        self.last_evidence = (lock.target_track, mouth)
        self.last_evidence_detail = {
            "source": None,
            "t0": t - ROW_SECS,
            "t1": t,
            "stream_id": stream_id,
            "track_id": lock.target_track,
            "probability": asd,
            "mouth": mouth,
            "labels": {s: labels[s].value for s in active},
            "fallback_reason": None,
        }
        if targets and self.vision_asd and stream_id is not None and visible:
            self._count_asd(asd)
        if not active:
            return None
        if not voices:
            return Verdict.REJECT
        if targets and overlap:
            self.target_overlap = True
            self.target_speaking_visibly = visible and (asd_ok or mouth_ok)
            return Verdict.UNCERTAIN
        if targets:
            self.row_is_target = True
            return self._target_verdict(targets[0], visible, asd_ok, mouth_ok)
        if overlap or all(labels[s] is Label.OTHER for s in voices):
            return Verdict.REJECT
        if asd_ok:
            # An UNKNOWN slot while the customer's face speaks: Sortformer gave
            # them a new slot. The binder learns it from this row.
            return self._accept("asd")
        return Verdict.UNCERTAIN

    def _target_verdict(self, slot, visible, asd_ok, mouth_ok):
        if visible:
            if asd_ok:
                return self._accept("asd")
            if mouth_ok:
                return self._accept("mar")
            if self.lock.voice_ok(slot):
                return self._accept("voice")  # MAR missed: hand or cup at the mouth
            return Verdict.REJECT
        if self.lock.voice_ok(slot):
            return self._accept("voice")
        return Verdict.UNCERTAIN

    def _accept(self, source: str) -> Verdict:
        self.last_source = source
        self.last_evidence_detail["source"] = source
        if source == "asd":
            self.row_asd_track = self.lock.target_track
        return Verdict.ACCEPT

    def _target_evidence(self, t, stream_id):
        """(visible, ASD probability, mouth) of the locked customer at row time t."""
        track, faces = self.lock.target_track, self._faces
        if (
            faces is None
            or track is None
            or not faces.fresh(t)
            or not faces.present(track, t - VISION_WINDOW_SECS, t + VISION_WINDOW_SECS)
        ):
            return False, None, None
        asd = (
            self._asd_probability(track, t, stream_id)
            if self.vision_asd and stream_id is not None
            else None
        )
        mouth = faces.mouth(track, t - VISION_WINDOW_SECS, t + VISION_WINDOW_SECS)
        return (asd is not None or mouth is not None), asd, mouth

    def _rebind_evidence(self, t, stream_id):
        """The nearest face and whether ASD hears it (Vision runs ASD on it
        while the locked customer is unpinned)."""
        faces = self._faces
        if faces is None or not faces.fresh(t):
            return None, False
        anchor = faces.anchor(t, self._anchor_max_m)
        if (
            anchor is None
            or anchor == self.lock.target_track
            or stream_id is None
            or not self.vision_asd
        ):
            return anchor, False
        probability = self._asd_probability(anchor, t, stream_id)
        return anchor, probability is not None and probability >= self._asd_accept

    def _update_binder(self, t, probs, asd_track, asd_probability) -> None:
        if self._faces is None or not self.row_voices:
            return
        scores: dict[int, float] = {}
        for track in self._faces.tracks_at(t):
            x = track.get("track_id")
            if isinstance(x, bool) or not isinstance(x, int):
                continue
            if x == asd_track and asd_probability is not None:
                scores[x] = float(asd_probability)
            else:
                mouth = self._faces.mouth(
                    x, t - VISION_WINDOW_SECS, t + VISION_WINDOW_SECS
                )
                scores[x] = 0.0 if mouth is None else float(mouth)
        self.lock.binder.update(
            t, {s: float(probs[s]) for s in self.row_voices}, scores
        )

    def _count_asd(self, asd: float | None) -> None:
        if asd is None:
            self.asd_counts[self.asd_row_reason or "gap"] += 1
        elif asd >= self._asd_accept:
            self.asd_counts["used_accept"] += 1
        elif asd <= self._asd_reject:
            self.asd_counts["used_reject"] += 1
        else:
            self.asd_counts["middle"] += 1
