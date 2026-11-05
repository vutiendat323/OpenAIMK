"""Speaker settings: defaults, validation and the operator-tunable bounds."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SpeakerSettings:
    """The ``[voice.speaker]`` preset section. Off by default."""

    enabled: bool = False
    uncertain_allowed_tools: tuple[str, ...] = ("display_menu",)
    bargein_accept_frames: int = 3
    accept_turn_fraction: float = 0.7
    reject_turn_fraction: float = 0.7
    diarizer: str = "none"
    enhancer: str = "none"
    diarizer_latency: str = "ultra_low"
    speaker_active_prob: float = 0.5
    overlap_on_frames: int = 3
    overlap_off_frames: int = 4
    vision_faces: bool = False
    vision_asd: bool = False
    asd_accept_prob: float = 0.7
    asd_reject_prob: float = 0.3
    asd_wait_secs: float = 0.12
    mouth_active: float = 0.5
    anchor_max_m: float = 1.5
    stt_mask: bool = False
    stt_mask_delay_secs: float = 0.5
    separator: str = "none"
    separator_model: str = "~/.cache/openjarvis/tse/bsrnn_spk_emb_100.ts"
    # Audio-visual fusion (spec 2026-09-30): lock one customer per kiosk
    # session. "none" keeps the gate exactly as it was.
    identity: str = "none"
    lock_asd_frames: int = 6
    voiceprint_min_secs: float = 2.0
    voice_match: float = 0.65
    voice_reject: float = 0.45
    bot_match: float = 0.70
    embed_segment_secs: float = 1.0
    embedder_model: str = "titanet_small"


# Fusion: a slot's solo speech is embedded in segments of embed_segment_secs,
# keeping at most this much while it accumulates (speaker_audio uses it).
SEGMENT_MAX_SECS = 3.0


def _fraction(section: Mapping[str, Any], key: str, default: float) -> float:
    value = section.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"voice_speaker_{key}_must_be_a_number")
    if not 0 < value <= 1:
        raise ValueError(f"voice_speaker_{key}_must_be_in_(0,1]")
    return float(value)


def _positive_int(section: Mapping[str, Any], key: str, default: int) -> int:
    value = section.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"voice_speaker_{key}_must_be_a_positive_int")
    return value


def _positive_float(section: Mapping[str, Any], key: str, default: float) -> float:
    value = section.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"voice_speaker_{key}_must_be_a_positive_number")
    return float(value)


def _finite_float(section: Mapping[str, Any], key: str, default: float) -> float:
    value = section.get(key, default)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise ValueError(f"voice_speaker_{key}_must_be_finite")
    return float(value)


def _boolean(section: Mapping[str, Any], key: str, default: bool) -> bool:
    value = section.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"voice_speaker_{key}_must_be_a_boolean")
    return value


def _choice(
    section: Mapping[str, Any], key: str, default: str, choices: tuple[str, ...]
) -> str:
    value = section.get(key, default)
    if value not in choices:
        raise ValueError(f"voice_speaker_{key}_must_be_one_of_{'|'.join(choices)}")
    return value


def settings_from_mapping(section: Mapping[str, Any]) -> SpeakerSettings:
    """Validate one ``[voice.speaker]`` table; errors are ``voice_speaker_*``."""
    defaults = SpeakerSettings()
    enabled = section.get("enabled", defaults.enabled)
    if not isinstance(enabled, bool):
        raise ValueError("voice_speaker_enabled_must_be_a_boolean")
    tools = section.get(
        "uncertain_allowed_tools", list(defaults.uncertain_allowed_tools)
    )
    if not isinstance(tools, list) or not all(isinstance(t, str) for t in tools):
        raise ValueError("voice_speaker_uncertain_allowed_tools_must_be_a_string_list")
    frames = _positive_int(
        section, "bargein_accept_frames", defaults.bargein_accept_frames
    )

    stt_mask = _boolean(section, "stt_mask", defaults.stt_mask)
    vision_asd = _boolean(section, "vision_asd", defaults.vision_asd)
    diarizer = _choice(section, "diarizer", defaults.diarizer, ("none", "sortformer"))
    vision_faces = _boolean(section, "vision_faces", defaults.vision_faces)
    if vision_asd and (not enabled or diarizer != "sortformer" or not vision_faces):
        raise ValueError("voice_speaker_vision_asd_needs_enabled_diarizer_and_faces")
    asd_accept = _finite_float(section, "asd_accept_prob", defaults.asd_accept_prob)
    asd_reject = _finite_float(section, "asd_reject_prob", defaults.asd_reject_prob)
    asd_wait = _finite_float(section, "asd_wait_secs", defaults.asd_wait_secs)
    if not 0 <= asd_reject < asd_accept <= 1:
        raise ValueError("voice_speaker_asd_thresholds_invalid")
    if not 0 <= asd_wait <= 0.12:
        raise ValueError("voice_speaker_asd_wait_secs_invalid")
    stt_delay = _positive_float(
        section, "stt_mask_delay_secs", defaults.stt_mask_delay_secs
    )
    if vision_asd and stt_mask and (not math.isfinite(stt_delay) or stt_delay < 0.7):
        raise ValueError("voice_speaker_vision_asd_stt_mask_delay_too_short")
    separator = _choice(section, "separator", defaults.separator, ("none", "tse"))
    if separator != "none" and not stt_mask:
        # Separation holds overlapped audio in the delayed STT copy.
        raise ValueError("voice_speaker_separator_needs_stt_mask")
    separator_model = section.get("separator_model", defaults.separator_model)
    if not isinstance(separator_model, str) or not separator_model.strip():
        raise ValueError("voice_speaker_separator_model_must_be_a_path")
    identity = _choice(section, "identity", defaults.identity, ("none", "fusion"))
    if identity == "fusion" and not (
        enabled and diarizer == "sortformer" and vision_faces and vision_asd
    ):
        raise ValueError("voice_speaker_fusion_needs_enabled_diarizer_faces_and_asd")
    voice_match = _fraction(section, "voice_match", defaults.voice_match)
    voice_reject = _fraction(section, "voice_reject", defaults.voice_reject)
    if voice_reject >= voice_match:
        raise ValueError("voice_speaker_voice_thresholds_invalid")
    embedder_model = section.get("embedder_model", defaults.embedder_model)
    if not isinstance(embedder_model, str) or not embedder_model.strip():
        raise ValueError("voice_speaker_embedder_model_must_be_a_name")
    embed_segment_secs = _positive_float(
        section, "embed_segment_secs", defaults.embed_segment_secs
    )
    if embed_segment_secs > SEGMENT_MAX_SECS:
        # A segment never grows past SEGMENT_MAX_SECS, so it would never embed.
        raise ValueError("voice_speaker_embed_segment_secs_too_long")

    return SpeakerSettings(
        enabled=enabled,
        uncertain_allowed_tools=tuple(
            dict.fromkeys(t.strip() for t in tools if t.strip())
        ),
        bargein_accept_frames=frames,
        accept_turn_fraction=_fraction(
            section, "accept_turn_fraction", defaults.accept_turn_fraction
        ),
        reject_turn_fraction=_fraction(
            section, "reject_turn_fraction", defaults.reject_turn_fraction
        ),
        diarizer=diarizer,
        enhancer=_choice(section, "enhancer", defaults.enhancer, ("none", "rnnoise")),
        diarizer_latency=_choice(
            section, "diarizer_latency", defaults.diarizer_latency, ("ultra_low", "low")
        ),
        speaker_active_prob=_fraction(
            section, "speaker_active_prob", defaults.speaker_active_prob
        ),
        overlap_on_frames=_positive_int(
            section, "overlap_on_frames", defaults.overlap_on_frames
        ),
        overlap_off_frames=_positive_int(
            section, "overlap_off_frames", defaults.overlap_off_frames
        ),
        vision_faces=vision_faces,
        vision_asd=vision_asd,
        asd_accept_prob=asd_accept,
        asd_reject_prob=asd_reject,
        asd_wait_secs=asd_wait,
        mouth_active=_fraction(section, "mouth_active", defaults.mouth_active),
        anchor_max_m=_positive_float(section, "anchor_max_m", defaults.anchor_max_m),
        stt_mask=stt_mask,
        stt_mask_delay_secs=stt_delay,
        separator=separator,
        separator_model=separator_model,
        identity=identity,
        lock_asd_frames=_positive_int(
            section, "lock_asd_frames", defaults.lock_asd_frames
        ),
        voiceprint_min_secs=_positive_float(
            section, "voiceprint_min_secs", defaults.voiceprint_min_secs
        ),
        voice_match=voice_match,
        voice_reject=voice_reject,
        bot_match=_fraction(section, "bot_match", defaults.bot_match),
        embed_segment_secs=embed_segment_secs,
        embedder_model=embedder_model.strip(),
    )


SPEAKER_LIVE_KEYS = {
    "anchor_max_m": (0.1, 6.0),
    "mouth_active": (0.01, 1.0),
    "asd_accept_prob": (0.01, 1.0),
    "asd_reject_prob": (0.0, 0.99),
    "voice_match": (0.01, 1.0),
    "voice_reject": (0.01, 0.99),
    "bot_match": (0.01, 1.0),
}
