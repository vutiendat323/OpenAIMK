"""Spoken session warnings: Trend tells the guest, in its own words, before a session ends.

The kiosk starts a Codex turn on the guest's thread; Codex's answer reaches the realtime
voice like any other result. These turns change nothing: no tool, cart or order.
"""

IDLE_WARNING_SHARE = 0.25  # warn a quarter of the idle time before it ends (30 of 120 s)

_NO_ACTION = "Do not call any tool and do not change the cart or any order."


def idle_warning_lead(idle_seconds):
    return idle_seconds * IDLE_WARNING_SHARE


def idle_warning_turn(seconds):
    return (
        "Kiosk notice, not a guest message: the guest has not spoken or touched the screen for "
        f"a while. Without any activity this session ends in about {round(seconds)} seconds. "
        "Tell the guest in your own words, warmly and in one short sentence, that the session "
        "will end soon, and invite them to keep ordering or ask for help. " + _NO_ACTION
    )


def time_warning_turn(seconds):
    return (
        "Kiosk notice, not a guest message: this session reaches its time limit in about "
        f"{round(seconds)} seconds. Tell the guest in your own words, warmly and in one short "
        "sentence, so they can finish their order now. " + _NO_ACTION
    )


def fallback_text(kind, seconds):
    """Shown only when Trend cannot say it (no conversation, or Codex refused the turn)."""
    seconds = round(seconds)
    if kind == "idle":
        return f"Phiên sẽ kết thúc sau {seconds} giây nếu không có tương tác."
    return "Phiên trò chuyện còn một phút." if seconds == 60 else f"Phiên còn {seconds} giây."
