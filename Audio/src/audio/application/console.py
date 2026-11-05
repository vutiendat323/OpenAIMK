"""Bounded observations and live controls for the operator's Vision console.

No model or network calls belong on the audio path. The bridge coalesces
snapshots; only an explicit Save command writes settings, through the store
the host supplies.
"""

from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import replace

from audio.application.ports import ConsoleSource, LiveKey, SettingsStore
from audio.domain.settings import SPEAKER_LIVE_KEYS, SpeakerSettings
from audio.domain.signal import audio_levels


class SpeakerConsole:
    def __init__(
        self,
        source: ConsoleSource,
        settings: SpeakerSettings,
        *,
        enhancer=None,
        target_audio_monitor=None,
        live_keys: Sequence[LiveKey] = (),
        store: SettingsStore | None = None,
    ):
        overlap = [key.name for key in live_keys if key.name in SPEAKER_LIVE_KEYS]
        if overlap:
            raise ValueError(f"Live keys overlap speaker settings: {overlap}")
        names = [key.name for key in live_keys]
        if "target_audio_monitor" in names or len(set(names)) != len(names):
            raise ValueError(f"Live keys must be unique and not reserved: {names}")
        self.source = source
        self.settings = settings
        self.enhancer = enhancer
        self.target_audio_monitor = target_audio_monitor
        self._host_keys = {key.name: key for key in live_keys}
        self._store = store
        self._next_publish = 0.0
        self._levels = {"rms_dbfs": -96.0, "peak": 0.0, "waveform": []}
        self._wave: deque[float] = deque(maxlen=128)
        self._verdict = None
        self._verdict_at = None
        self._audio_at = None

    @property
    def bounds(self) -> dict[str, tuple[float, float]]:
        """Host keys first, then the speaker's own, in the console's order."""
        host = {name: key.bounds for name, key in self._host_keys.items()}
        return {**host, **SPEAKER_LIVE_KEYS}

    def tune(self, key: str, value) -> dict:
        if key == "target_audio_monitor":
            if type(value) is not bool or self.target_audio_monitor is None:
                raise ValueError(
                    "Target audio monitor requires ON or OFF and an active session"
                )
            # This control is session-only; never part of values() or Save.
            # The bridge calls it off-thread, then publishes on the event loop.
            self.target_audio_monitor.set_enabled(value)
            return {"key": key, "value": self.target_audio_monitor.enabled}
        bounds = self.bounds.get(key)
        if bounds is None or type(value) not in (int, float):
            raise ValueError("Unsupported setting or non-numeric value")
        if not math.isfinite(value) or not bounds[0] <= value <= bounds[1]:
            raise ValueError(f"Value must be within {bounds[0]}–{bounds[1]}")
        host = self._host_keys.get(key)
        if host is not None:
            host.set(float(value))
            self.publish(force=True)
            return {"key": key, "value": float(value)}
        updated = replace(self.settings, **{key: float(value)})
        if updated.asd_reject_prob >= updated.asd_accept_prob:
            raise ValueError("ASD reject threshold must be below accept threshold")
        if updated.voice_reject >= updated.voice_match:
            raise ValueError("Voice reject threshold must be below match threshold")
        self.source.gate.apply_live_settings(updated)
        self.settings = updated
        self.publish(force=True)
        return {"key": key, "value": float(value)}

    def values(self) -> dict:
        host = {name: key.get() for name, key in self._host_keys.items()}
        own = {key: getattr(self.settings, key) for key in SPEAKER_LIVE_KEYS}
        return {**host, **own}

    def save(self, values: Mapping[str, float]) -> None:
        if self._store is None:
            raise ValueError("No settings store configured")
        self._store.save(values)

    def audio(self, audio: bytes) -> None:
        self._levels = audio_levels(audio)
        self._wave.extend(self._levels["waveform"])
        self._audio_at = time.time()
        self.publish()

    def verdict(self, verdict, timestamp: float) -> None:
        self._verdict = verdict.value if verdict is not None else None
        self._verdict_at = timestamp

    def snapshot(self) -> dict:
        source = self.source
        gate = source.gate
        fusion = source.fusion
        lock = fusion.lock if fusion is not None else None
        detail = dict(gate.last_evidence_detail or {})
        counts = gate.asd_counts
        used = counts["used_accept"] + counts["used_reject"]
        eligible = used + counts["middle"] + counts["late"] + counts["gap"]
        bridge = source.bridge
        slots = sorted(lock.target_slots) if lock is not None else []
        similarities = (
            [
                lock.slots[s].voice_sim
                for s in slots
                if s in lock.slots and lock.slots[s].voice_sim is not None
            ]
            if lock is not None
            else []
        )
        enhancer = self.enhancer
        audio = {**self._levels, "waveform": list(self._wave), "ts": self._audio_at}
        audio["raw_rms_dbfs"] = self._levels["rms_dbfs"] if enhancer is None else None
        if enhancer is not None:
            audio["raw_rms_dbfs"] = getattr(enhancer, "raw_rms_dbfs", None)
        return {
            "ts": time.time(),
            "target_audio_monitor": (
                self.target_audio_monitor.snapshot()
                if self.target_audio_monitor
                else None
            ),
            "audio": audio,
            "enhancer_requested": self.settings.enhancer,
            "enhancer_effective": getattr(enhancer, "effective_name", "none"),
            "identity": self.settings.identity,
            "verdict": self._verdict,
            "verdict_ts": self._verdict_at,
            "evidence": detail,
            "locked": lock.locked if lock is not None else False,
            "lock_state": lock.state.value if lock is not None else "NONE",
            "target_track": lock.target_track if lock is not None else None,
            "target_slots": slots,
            "voice_ready": lock.voice_ready if lock is not None else False,
            "voice_similarity": max(similarities) if similarities else None,
            "overlap": gate.overlap,
            "bot_speaking": time.monotonic() < source.bot_audible_until,
            "stt_mask": self.settings.stt_mask,
            "tse_ready": source.tse_ready,
            "stt_masked_no_verdict_frames": source.stt_masked_no_verdict,
            "asd_effective_use": used / eligible if eligible else None,
            "asd_late": getattr(bridge, "asd_late", 0),
            "asd_age_ms": bridge.asd_age_ms[-1] if bridge.asd_age_ms else None,
            "bargein_blocked": source.bargein_blocked,
            "echo_rejects": getattr(fusion, "echo_rejects", 0),
            "settings": self.values(),
            "bounds": {key: list(value) for key, value in self.bounds.items()},
        }

    def publish(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if force or now >= self._next_publish:
            self._next_publish = now + 0.1
            self.source.bridge.offer_telemetry(self.snapshot())
