"""Trend must not state a kiosk result that no kiosk tool produced.

The realtime voice layer decides by itself whether to delegate a guest request to
Codex, which alone holds the kiosk tools. When it does not delegate, it can still
say that an item was added, an order created, a QR shown or a payment received,
copying sentences from its prompt and earlier turns. The host sees every kiosk
tool call and every word Trend speaks, so it can tell when a spoken result has no
tool behind it.

Rule, checked against the kiosk transcripts of 2026-11-03/04 (23 unbacked results
caught, no tool-backed result flagged after ignoring short interjections): a result
sentence is backed when any kiosk tool ran after the guest's latest request began,
less a small allowance because Codex can start a tool just before the guest's
transcript arrives. Interjections under three words ("nhé", "Mang về") continue
the current request rather than start a new one.
"""

import re
import unicodedata

# Completed-result wording only; acknowledgements ("Dạ, có ngay!", "... vào giỏ
# ngay nhé") and questions about a future action are not results.
RESULT = re.compile(
    r"quét QR|đã tạo|tạo xong|đã gửi|đã được thanh toán"
    r"|đã thêm|đã vào giỏ|vào giỏ rồi|vào đơn rồi|đã có .{0,40}(trong giỏ|tại bàn)"
    r"|chỉnh còn|giờ chỉ còn|đã cập nhật|đã chỉnh"
    r"|đã mở|đang (mở|hiển thị|hiện) trên màn hình|trên màn hình rồi|đã hiển thị",
    re.IGNORECASE,
)
REQUEST_MIN_WORDS = 3
TOOL_ALLOWANCE = 2.5  # seconds a tool may precede the guest's transcript


class ClaimGuard:
    def __init__(self):
        self.request_at = None
        self.request_text = ""
        self.tool_at = None
        self.flagged = set()
        self.blocked = 0

    def guest(self, text, now):
        """A finished guest utterance; a short interjection continues the request."""
        if len(str(text).split()) >= REQUEST_MIN_WORDS:
            self.request_at = now
            self.request_text = str(text)

    def tool(self, now):
        self.tool_at = now

    def backed(self):
        if self.tool_at is None:
            return False
        return self.request_at is None or self.tool_at >= self.request_at - TOOL_ALLOWANCE

    def reply(self, turn_id, text, now):
        """True once per reply when its text so far states a result no tool produced."""
        if turn_id in self.flagged or not RESULT.search(str(text)) or self.backed():
            return False
        self.flagged.add(turn_id)
        self.blocked += 1
        return True


# Sent to the realtime voice layer as a developer note when a result is stopped.
UNBACKED_RESULT_NOTE = (
    "Kiosk check: no kiosk tool ran for the guest's latest request, so the result you "
    "just started to state did not happen and is not on screen. Do not state results "
    "yourself. Delegate the guest's latest request to Codex now and say only its actual "
    "result."
)


# What Trend reads out loud about drinks must also be on the customer's screen.
SPOKEN_ITEMS_LIMIT = 6
SPOKEN_NAME_MIN = 6  # shorter names ("Trà") are ordinary words, not a drink


def _fold(text):
    return " ".join(unicodedata.normalize("NFC", str(text)).lower().split())


def spoken_items(text, catalog, limit=SPOKEN_ITEMS_LIMIT):
    """Catalog item ids whose names appear in `text`, in spoken order.

    A name inside a longer matched name ("Cà phê sữa" in "Cà phê sữa đá") is dropped.
    """
    spoken = _fold(text)
    if not spoken:
        return []
    found = []
    for item in catalog:
        name = _fold(item.get("name", ""))
        if len(name) >= SPOKEN_NAME_MIN and name in spoken:
            found.append((spoken.index(name), name, item["id"]))
    kept = [
        (at, name, ident)
        for at, name, ident in found
        if not any(name != other and name in other for _, other, _ in found)
    ]
    return [ident for _, _, ident in sorted(kept)][:limit]


# "Paid" is a locked sentence: only a tool result that says paid may back it.
PAID = re.compile(r"đã được thanh toán|đã thanh toán (xong|thành công)", re.IGNORECASE)
UNVERIFIED_PAID_NOTE = (
    "Kiosk check: this order is not verified as paid by any tool result. Never say it was "
    "paid. If the guest asked about payment, call kiosk_payment and relay its actual status; "
    "for a pending QR say only: 'Bạn quét QR trên màn hình để thanh toán nhé.'"
)


def says_paid(result):
    """True when a kiosk tool result reports a verified paid order."""
    if not isinstance(result, dict):
        return False
    payment = result.get("payment") if isinstance(result.get("payment"), dict) else {}
    return "paid" in (result.get("payment_status"), result.get("status"), payment.get("status"))


# Sent when the kiosk runs the guest's request itself, because the voice stated a result
# without ever delegating it (2026-11-04 16:00: "để mình lên đơn", then a QR that did not exist).
TAKEOVER_NOTE = (
    "Kiosk check: no kiosk tool ran for the guest's latest request, so the result you started "
    "to state did not happen. The kiosk is now running that request itself. Do not delegate it "
    "again and do not state any result; wait for the result and relay it."
)


def recovery_turn(request, history, *, payment=False):
    """The text of the Codex turn the kiosk starts for a request nobody delegated."""
    recent = "\n".join(f"{role}: {text}" for role, text in history)
    context = f"Recent conversation (oldest first):\n{recent}\n" if recent else ""
    task = (
        "The guest asks whether the order is paid. Call kiosk_payment and report its real status."
        if payment
        else "No kiosk tool has run for this request yet. Carry it out now with the kiosk tools, "
        "following the service instructions, and report only the real result."
    )
    return f'The guest just said (Vietnamese): "{request}"\n{context}{task}'
