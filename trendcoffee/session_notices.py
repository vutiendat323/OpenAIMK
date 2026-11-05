"""What Trend says on its own during a session, as Codex turns on the guest's thread.

The kiosk starts the turn; Codex's answer reaches the realtime voice like any other result.

- A quiet guest (2026-11-05, user decision): the session does not end. After `idle_seconds`
  without the guest speaking, touching or changing the cart, Trend asks one short question
  that fits where the guest is: nothing chosen, items in the cart, an order waiting for
  payment, or a paid order. Nothing is added, changed or ordered without the guest asking.
- The time limit: Trend warns `warning_seconds` before the session reaches its maximum.
"""

QR_SENTENCE = "Bạn quét QR trên màn hình để thanh toán nhé."

_NO_CHANGE = (
    "Never add, change, remove or order anything, and never place an order, unless the guest "
    "asks for it. Do not say the session will end."
)


def guest_situation(cart, fulfillment="", table_label="", order=None, paid=False):
    """(state, facts) about where this guest is, for the nudge. Facts are data, not orders."""
    if order is not None:
        reference = (order.get("payment") or {}).get("merchant_order_id") or order.get("id")
        if paid or order.get("payment_status") == "paid":
            return "paid", f"The guest's order {reference} is already paid."
        return "awaiting_payment", f"The guest's order {reference} was placed and is waiting " + (
            "for payment (QR on screen)." if order.get("merchant") else "for staff."
        )
    if cart:
        lines = ", ".join(
            f"{line.get('quantity', 1)} × {(line.get('item') or {}).get('name', '?')}"
            for line in cart
        )
        where = (
            "at the table" + (f" {table_label}" if table_label else "")
            if fulfillment == "at_table"
            else "takeaway"
            if fulfillment == "takeaway"
            else "not chosen yet"
        )
        return "cart", f"Cart, not ordered yet: {lines}. Takeaway or table: {where}."
    return "nothing", "The guest has not chosen anything yet."


_ASK = {
    "nothing": (
        "Ask what they would like to drink or eat today, or offer to suggest something. You may "
        "show the menu with kiosk_menu (display only)."
    ),
    "cart": (
        "Ask whether they want to pay for these now or add something else; if takeaway or table "
        "is not chosen yet, you may ask that instead. If you mention what is in the cart, first "
        "call kiosk_cart with action=view (it only shows the cart)."
    ),
    "awaiting_payment": (
        "Call kiosk_payment once to refresh the real payment status. If it is still pending, "
        f"say only: '{QR_SENTENCE}' If it is paid, tell them warmly in your own words. "
        "Otherwise relay the real status briefly."
    ),
    "paid": "Ask whether they would like anything else, or if you can help with anything.",
}


def idle_nudge_turn(state, facts, seconds):
    return (
        "Kiosk notice, not a guest message: the guest has not spoken or touched the screen for "
        f"about {round(seconds)} seconds. {facts} {_ASK.get(state, _ASK['nothing'])} Use your "
        "own words: one short, warm question that fits this guest and the conversation so far. "
        + _NO_CHANGE
    )


def time_warning_turn(seconds):
    return (
        "Kiosk notice, not a guest message: this session reaches its time limit in about "
        f"{round(seconds)} seconds. Tell the guest in your own words, warmly and in one short "
        "sentence, so they can finish their order now. Do not call any tool and do not change "
        "the cart or any order."
    )


def fallback_text(kind, seconds=0):
    """Shown only when Trend cannot say it (no conversation, or Codex refused the turn)."""
    if kind == "nudge":
        return "Bạn cần Trend giúp gì thêm không?"
    seconds = round(seconds)
    return "Phiên trò chuyện còn một phút." if seconds == 60 else f"Phiên còn {seconds} giây."
