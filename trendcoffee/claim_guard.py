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
# A guest remark while Codex works ("ừ nhanh nha bạn") starts a new request, but the tool
# result Trend has not read out yet is still what it is about to say (2026-11-05: a real
# "Bạn quét QR..." was cut). Such a result backs a reply for this long after the tool,
# until a reply with result wording has been spoken after it.
RELAY_WINDOW = 15.0


class ClaimGuard:
    def __init__(self):
        self.request_at = None
        self.request_text = ""
        self.tool_at = None
        self.relayed_at = None  # when Trend last finished a reply that stated a result
        self.flagged = set()
        self.blocked = 0

    def guest(self, text, now):
        """A finished guest utterance; a short interjection continues the request."""
        if len(str(text).split()) >= REQUEST_MIN_WORDS:
            self.request_at = now
            self.request_text = str(text)

    def tool(self, now):
        self.tool_at = now

    def backed(self, now=None):
        if self.tool_at is None:
            return False
        if self.request_at is None or self.tool_at >= self.request_at - TOOL_ALLOWANCE:
            return True
        # A tool result not yet read out, from before the guest's latest remark.
        return (
            now is not None
            and (self.relayed_at is None or self.tool_at > self.relayed_at)
            and now - self.tool_at <= RELAY_WINDOW
        )

    def done(self, text, now):
        """A finished Trend reply; one that stated a result has read out the tool results."""
        if RESULT.search(str(text)):
            self.relayed_at = now

    def reply(self, turn_id, text, now):
        """True once per reply when its text so far states a result no tool produced."""
        if turn_id in self.flagged or not RESULT.search(str(text)) or self.backed(now):
            return False
        self.flagged.add(turn_id)
        self.blocked += 1
        return True


# Sent to the realtime voice layer as a developer note when a result is stopped.
# A pickup card Trend names must be the order's own (anti-goal, 2026-11-06): the guest
# takes and waits for that card.
SPOKEN_CARD = re.compile(r"thẻ rung\D{0,30}?số\s*(\d+)", re.IGNORECASE)


def wrong_card(text, card):
    """True when the reply names a pickup card other than the order's own card."""
    return any(int(number) != card for number in SPOKEN_CARD.findall(str(text)))


def wrong_card_note(card):
    if not card:
        return (
            "Kiosk check: this guest's order has no pickup card. Do not name a card number; "
            "correct yourself in one short sentence."
        )
    return (
        f"Kiosk check: the pickup card you just named is wrong. This order's card is số {card}. "
        "Correct it in one short sentence; never name another card number."
    )


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


# Trend words a paid result freely, but only a tool result that says paid may back it.
PAID = re.compile(
    r"đã được thanh toán|đã thanh toán (xong|thành công|rồi)"
    r"|thanh toán (đã )?(xong|thành công) rồi|thanh toán thành công"
    r"|đã nhận (được )?(tiền|thanh toán)",
    re.IGNORECASE,
)
UNVERIFIED_PAID_NOTE = (
    "Kiosk check: this order is not verified as paid by any tool result. Never say it was "
    "paid. If the guest asked about payment, call kiosk_payment and relay its actual status; "
    "for a pending QR say only the qr_reply it returns (it names the pickup card)."
)


def says_paid(result):
    """True when a kiosk tool result reports a verified paid order."""
    if not isinstance(result, dict):
        return False
    payment = result.get("payment") if isinstance(result.get("payment"), dict) else {}
    return "paid" in (result.get("payment_status"), result.get("status"), payment.get("status"))


# Sent when the kiosk runs the guest's request itself, because the voice stated a result
# without ever delegating it (2026-11-04 16:00: "để mình lên đơn", then a QR that did not exist).
def takeover_note(request, *, promise=False):
    """What Trend is told when the kiosk runs a request itself.

    Scoped to that one request (2026-11-06 20:38: an unscoped "do not delegate it again ...
    wait for the result" made Trend stop delegating new orders for the rest of the session)."""
    what = (
        "you promised to act on it but did not delegate it"
        if promise
        else "the result you started to state did not happen"
    )
    return (
        f'Kiosk check about the guest\'s request "{request}": {what}. The kiosk is running '
        "that one request itself, so do not delegate that same request again and do not state "
        "its result yourself; relay the result when Codex returns it. This applies only to that "
        "request: delegate every new guest request to Codex as usual, right away."
    )


# A promise to act ("mình ghi liền cho bạn") is not a result, but if no Codex turn follows,
# the guest waits for nothing (2026-11-06: 16:07, 20:38, 20:44; the guest had to repeat).
PROMISE = re.compile(
    r"(làm|gửi|ghi|đặt|tạo|lên đơn|xử lý|kiểm tra)\s*(ngay|liền)"
    r"|để mình (làm|gửi|ghi|đặt|tạo|lên đơn|xử lý|kiểm tra)"
    r"|đang chờ hệ thống",
    re.IGNORECASE,
)


def promises(text):
    """True when Trend says it is about to act on a request (an acknowledgement, not a result)."""
    return bool(PROMISE.search(str(text)))


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


def paid_summary(order):
    """A short, factual description of a paid order, for Trend's own context."""
    lines = []
    for line in order.get("lines") or []:
        text = f"{line.get('quantity', 1)} × {line.get('name', line.get('item_id', ''))}"
        options = ", ".join(str(v) for v in (line.get("options") or {}).values())
        if options:
            text += f" ({options})"
        if line.get("note"):
            text += f" — ghi chú: {line['note']}"
        lines.append(text)
    if order.get("fulfillment") == "at_table":
        where = f"tại bàn {order['table_label']}" if order.get("table_label") else "tại bàn"
    elif order.get("fulfillment") == "takeaway":
        where = "mang đi"
    else:
        where = str(order.get("fulfillment") or "")
    parts = ["; ".join(lines) or "no lines"]
    if order.get("total_vnd") is not None:
        parts.append(f"total {order['total_vnd']} VND")
    if where:
        parts.append(where)
    reference = (order.get("payment") or {}).get("merchant_order_id")
    if reference:
        parts.append(f"merchant order {reference}")
    return ", ".join(parts)


def paid_turn(order):
    """The Codex turn the kiosk starts when the merchant verifies a guest's payment."""
    return (
        "Kiosk notice, not a guest message: the merchant has just verified payment for this "
        f"guest's order ({paid_summary(order)}). Call kiosk_payment once to confirm its real "
        "status. If it reports paid, tell the guest warmly, in your own words and one or two "
        "short sentences, that the payment went through; you may mention this order (at most "
        "two drink names, takeaway or table). Otherwise relay its real status as the service "
        "instructions say. Do not create another order or payment. Keep this paid order in "
        "mind for the guest's next questions."
    )


# Sent to the realtime voice layer when Codex cannot take the paid-order turn.
def paid_note(order):
    return (
        "Kiosk notice: the merchant verified payment for this guest's order "
        f"({paid_summary(order)}). Do not create another order or QR. If the guest asks about "
        "payment, delegate so Codex calls kiosk_payment and relay only its result."
    )
