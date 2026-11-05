"""The target-speaker gate's answers, per frame and per turn."""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum


class Verdict(str, Enum):
    """The target-speaker gate's answer for a frame or a turn."""

    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    UNCERTAIN = "UNCERTAIN"


def turn_verdict(
    counts: Mapping[Verdict, int], *, accept_fraction: float, reject_fraction: float
) -> Verdict:
    """Fold a turn's frame verdicts into one.

    No frames means no diarizer evidence, which is today's behaviour: accept.
    """
    total = sum(counts.values())
    if total == 0:
        return Verdict.ACCEPT
    accepted = counts.get(Verdict.ACCEPT, 0) / total
    rejected = counts.get(Verdict.REJECT, 0) / total
    if rejected >= reject_fraction:
        return Verdict.REJECT
    if accepted >= accept_fraction and rejected < 0.2:
        return Verdict.ACCEPT
    return Verdict.UNCERTAIN
