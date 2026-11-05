"""Frame and turn verdicts from diarizer probabilities and Vision evidence.

Pure on purpose: no Pipecat, no models. A host feeds per-frame verdicts in;
its turn strategies read turn verdicts out.
"""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Mapping, Sequence

from audio.domain.evidence import VISION_WINDOW_SECS, FaceTrackBuffer
from audio.domain.settings import SpeakerSettings
from audio.domain.verdict import Verdict, turn_verdict

# A slot is judged as echo only after 2 s of its speech, most of it heard
# while Jarvis was playing: the TTS voice diarizes as a speaker of its own.
ECHO_MIN_FRAMES = 25


ECHO_BOT_FRACTION = 0.8


# Audio alone cannot tell the customer from a bystander, so the target follows
# whoever holds the floor alone for 0.5 s while Jarvis is silent. Without this,
# a bystander who spoke first would lock the customer out for the session.
# ponytail: audio-only heuristic; vision fusion (PR-5) replaces it.
FLOOR_FRAMES = 6


class OverlapDetector:
    """Two or more voices at once, with hysteresis so 80 ms spikes don't count."""

    def __init__(self, *, on_frames: int, off_frames: int) -> None:
        self._on_frames = on_frames
        self._off_frames = off_frames
        self._run = 0
        self.active = False

    def update(self, n_voices: int) -> bool:
        if (n_voices >= 2) != self.active:
            self._run += 1
        else:
            self._run = 0
        if self._run >= (self._off_frames if self.active else self._on_frames):
            self.active = not self.active
            self._run = 0
        return self.active


class AudioOnlyGate:
    """Frame verdicts from diarizer probabilities (spec §5.4).

    With fresh Vision face tracks, speech counts only while the engaged
    customer's mouth moves; anything else heard is REJECTed. Without them,
    audio alone can only say "not the target", which is UNCERTAIN.
    """

    def __init__(
        self, settings: SpeakerSettings, faces: FaceTrackBuffer | None = None
    ) -> None:
        self._faces = faces
        self._mouth_active = settings.mouth_active
        self._anchor_max_m = settings.anchor_max_m
        self._threshold = settings.speaker_active_prob
        self.vision_asd = settings.vision_asd
        self.asd_wait_secs = settings.asd_wait_secs if settings.vision_asd else 0.0
        self._asd_accept = settings.asd_accept_prob
        self._asd_reject = settings.asd_reject_prob
        # Per ASD-eligible row: used_accept, used_reject, middle, late, warmup
        # or gap -- enough to derive spec §9's effective-use fraction.
        self.asd_counts: Counter[str] = Counter()
        # Set by the processor per chunk: why ASD may be missing (late/warmup).
        self.asd_row_reason: str | None = None
        self._overlap = OverlapDetector(
            on_frames=settings.overlap_on_frames,
            off_frames=settings.overlap_off_frames,
        )
        self._active_frames: Counter[int] = Counter()
        self._bot_frames: Counter[int] = Counter()
        self.target: int | None = None
        # (anchor track, mouth activity) behind the last vision verdict, for logs.
        self.last_evidence: tuple[int | None, float | None] | None = None
        self.last_evidence_detail: dict[str, object] | None = None
        self._asd_snapshot: FaceTrackBuffer | None = None
        self._floor_slot: int | None = None
        self._floor_run = 0

    @property
    def overlap(self) -> bool:
        return self._overlap.active

    def apply_live_settings(self, settings: SpeakerSettings) -> None:
        """Apply validated console thresholds without resetting speaker evidence."""
        self._mouth_active = settings.mouth_active
        self._anchor_max_m = settings.anchor_max_m
        self._asd_accept = settings.asd_accept_prob
        self._asd_reject = settings.asd_reject_prob

    def is_echo(self, slot: int) -> bool:
        heard = self._active_frames[slot]
        return (
            heard >= ECHO_MIN_FRAMES
            and self._bot_frames[slot] / heard >= ECHO_BOT_FRACTION
        )

    def asd_wait_track(self, t: float) -> int | None:
        """The face whose ASD a chunk ending at *t* waits for: the anchor."""
        if self._faces is None or not self._faces.fresh(t):
            return None
        return self._faces.anchor(t, self._anchor_max_m)

    def asd_wait_candidate(self, t: float, rows: Sequence[Sequence[float]]) -> bool:
        return bool(
            self.vision_asd
            and self._faces is not None
            and any(p >= self._threshold for row in rows for p in row)
            and self._faces.fresh(t)
            and self.asd_wait_track(t) is not None
        )

    def frame(
        self,
        probs: Sequence[float],
        *,
        bot_speaking: bool,
        t: float | None = None,
        asd_stream_id: str | None = None,
    ) -> Verdict | None:
        active = [slot for slot, p in enumerate(probs) if p >= self._threshold]
        for slot in active:
            self._active_frames[slot] += 1
            if bot_speaking:
                self._bot_frames[slot] += 1
        voices = [slot for slot in active if not self.is_echo(slot)]
        # A playback tail longer than the processor's can bind Jarvis's own
        # voice; once that slot proves to be echo, let the customer rebind.
        if self.target is not None and self.is_echo(self.target):
            self.target = None
        overlap = self._overlap.update(len(voices))
        self.last_evidence = None
        self.last_evidence_detail = None
        if not active:
            return None
        if not voices:
            return Verdict.REJECT
        if not bot_speaking and len(voices) == 1:
            if voices[0] == self._floor_slot:
                self._floor_run += 1
            else:
                self._floor_slot, self._floor_run = voices[0], 1
            if self.target is None or self._floor_run >= FLOOR_FRAMES:
                self.target = voices[0]
        else:
            self._floor_slot, self._floor_run = None, 0
        if self._faces is not None and t is not None and self._faces.fresh(t):
            anchor = self._faces.anchor(t, self._anchor_max_m)
            mouth = (
                self._faces.mouth(
                    anchor, t - VISION_WINDOW_SECS, t + VISION_WINDOW_SECS
                )
                if anchor is not None
                else None
            )
            self.last_evidence = (anchor, mouth)
            self.last_evidence_detail = {
                "source": "mar",
                "t0": t - 0.08,
                "t1": t,
                "stream_id": asd_stream_id,
                "track_id": anchor,
                "probability": None,
                "mouth": mouth,
                "fallback_reason": "asd_disabled"
                if not self.vision_asd
                else "asd_unavailable",
            }
            if overlap or anchor is None:
                self.last_evidence_detail["fallback_reason"] = (
                    "overlap" if overlap else "no_anchor"
                )
                # Overlap is never ACCEPTed, but with the customer's mouth
                # still the other voice is all there is: live 2026-09-28,
                # hysteresis kept a video's words UNCERTAIN and they were
                # acted on.
                if anchor is None or mouth is None or mouth >= self._mouth_active:
                    return Verdict.UNCERTAIN
                probability = (
                    self._asd_probability(anchor, t, asd_stream_id)
                    if self.vision_asd and asd_stream_id is not None
                    else None
                )
                self.last_evidence_detail["probability"] = probability
                if probability is not None and probability >= self._asd_accept:
                    return Verdict.UNCERTAIN
                return Verdict.REJECT
            if self.vision_asd and asd_stream_id is not None:
                probability = self._asd_probability(anchor, t, asd_stream_id)
                if probability is not None:
                    self.last_evidence_detail["probability"] = probability
                    if probability >= self._asd_accept:
                        self.last_evidence_detail.update(
                            source="asd", fallback_reason=None
                        )
                        self.asd_counts["used_accept"] += 1
                        return Verdict.ACCEPT
                    if probability <= self._asd_reject:
                        self.last_evidence_detail.update(
                            source="asd", fallback_reason=None
                        )
                        self.asd_counts["used_reject"] += 1
                        return Verdict.REJECT
                    self.last_evidence_detail["fallback_reason"] = "asd_middle"
                    self.asd_counts["middle"] += 1
                else:
                    reason = self.asd_row_reason or "gap"
                    self.last_evidence_detail["fallback_reason"] = f"asd_{reason}"
                    self.asd_counts[reason] += 1
            if mouth is not None and mouth >= self._mouth_active:
                return Verdict.ACCEPT
            return Verdict.REJECT
        self.last_evidence_detail = {
            "source": "audio",
            "t0": t - 0.08 if t is not None else None,
            "t1": t,
            "stream_id": asd_stream_id,
            "track_id": None,
            "probability": None,
            "fallback_reason": "stale_or_absent_vision",
        }
        if self.target not in voices:
            return Verdict.UNCERTAIN
        if overlap:
            return Verdict.UNCERTAIN
        return Verdict.ACCEPT

    def _asd_probability(self, anchor: int, t: float, stream_id: str) -> float | None:
        if not self._faces.asd_stream_matches(stream_id):
            return None
        return (self._asd_snapshot or self._faces).active_speaker(
            anchor, t - 0.08, t, stream_id=stream_id, now=time.time()
        )


class SpeakerTracker:
    """One Voice session's speaker evidence, shared by the turn strategies
    and the LLM service. Everything runs on the pipeline's event loop."""

    def __init__(self, settings: SpeakerSettings, *, diarized: bool = False) -> None:
        self._settings = settings
        self._diarized = diarized
        self._counts: Counter[Verdict] = Counter()
        self._sources: Counter[str] = Counter()
        self.bargein_blocked = 0
        self._closed: Verdict | None = None
        # With a diarizer, every decision waits for its evidence from the
        # first frame of the session; without one, the legacy behaviour.
        self.has_evidence = diarized

    def record(self, verdict: Verdict, source: str | None = None) -> None:
        self.has_evidence = True
        self._counts[verdict] += 1
        if source is not None:
            self._sources[source] += 1

    @property
    def masks_stt(self) -> bool:
        """REJECTed audio reaches STT as silence, so no rejected words exist."""
        return self._settings.stt_mask

    def begin_span(self) -> None:
        """Speech started outside a turn: its frames start a fresh count."""
        self._counts.clear()
        self._sources.clear()

    def source_counts(self) -> dict[str, int]:
        """What confirmed this span's frames (asd, mar, voice, audio), for logs."""
        return dict(self._sources)

    def begin_turn(self) -> None:
        """A turn opened. A closed verdict nobody took is stale: its turn had
        no transcript, or this turn's interruption dropped its LLM frame."""
        self._closed = None

    def span_verdict(self, counts: Mapping[Verdict, int] | None = None) -> Verdict:
        counts = self._counts if counts is None else counts
        if self._diarized and not counts:
            # The diarizer ran but never confirmed this speech (it lagged, or
            # placed nobody): not the customer's word.
            return Verdict.UNCERTAIN
        return turn_verdict(
            counts,
            accept_fraction=self._settings.accept_turn_fraction,
            reject_fraction=self._settings.reject_turn_fraction,
        )

    def _turn_verdict(self) -> Verdict:
        """The finished turn's verdict, from the speech its transcript holds.

        With ``stt_mask``, REJECTed audio reached Gemini as silence, so it put
        no words in the transcript: only the other frames decide. Live
        2026-09-26: a phone video between the customer's words turned their
        turns UNCERTAIN, or REJECTed and dropped them. A turn of nothing but
        rejected speech stays REJECT. Turn starts still count every frame.
        """
        counts = self._counts
        if self._settings.stt_mask and (
            counts[Verdict.ACCEPT] or counts[Verdict.UNCERTAIN]
        ):
            counts = Counter(
                {v: n for v, n in counts.items() if v is not Verdict.REJECT}
            )
        return self.span_verdict(counts)

    def close_turn(self) -> Verdict:
        self._closed = self._turn_verdict()
        return self._closed

    def frame_counts(self) -> dict[str, int]:
        """This span's frame verdicts, for logs."""
        return {verdict.value: n for verdict, n in self._counts.items()}

    def take_turn_verdict(self) -> Verdict:
        """The verdict for the turn the LLM is about to answer, consumed once.

        Falls back to the live count when the turn was finalized without
        ``close_turn`` (Pipecat's stop watchdog).
        """
        verdict = self._closed if self._closed is not None else self._turn_verdict()
        self._closed = None
        return verdict
