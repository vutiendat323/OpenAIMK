"""Warm, natural spoken replies without weakening the checkout and payment contract."""

import re

from trendcoffee.codex_voice import INSTRUCTIONS, VOICE_INSTRUCTIONS

QR_LINE = "Bạn quét QR trên màn hình để thanh toán nhé."
PAID_LINE = "Đơn đã được thanh toán."


def test_exact_payment_sentences_stay_exact_in_both_prompts():
    for prompt in (INSTRUCTIONS, VOICE_INSTRUCTIONS):
        assert QR_LINE in prompt


def test_the_paid_result_is_worded_naturally_not_a_fixed_sentence():
    """User decision 2026-11-05: no hardcoded paid sentence."""
    for prompt in (INSTRUCTIONS, VOICE_INSTRUCTIONS):
        flat = " ".join(prompt.split())
        assert PAID_LINE not in prompt
        assert "own words" in flat
        assert "status=paid" in flat or "payment_status is paid" in flat
        assert "without another QR/order" in flat or "Do not create another order" in flat


def test_checkout_replies_stay_short_and_unconfirmed():
    assert "ENTIRE final reply must be exactly" in INSTRUCTIONS
    assert "No repeat order or\nconfirmation question" in VOICE_INSTRUCTIONS
    for prompt in (INSTRUCTIONS, VOICE_INSTRUCTIONS):
        assert "never over 20 words" not in prompt, "the old blanket limit is replaced"


def test_conversation_replies_are_warm_and_a_little_longer_in_both_prompts():
    for prompt in (INSTRUCTIONS, VOICE_INSTRUCTIONS):
        flat = " ".join(prompt.split())
        assert re.search(r"warm, friendly", flat)
        assert re.search(r"two or three (short )?sentences", flat)
        assert "about 40 words" in flat
        assert "light emotion" in flat or "gentle emotion" in flat
        assert "Never read the whole menu" in flat or "Never read the whole menu" in INSTRUCTIONS


def test_acknowledgement_stays_brief_but_friendly_and_claims_no_success():
    flat = " ".join(VOICE_INSTRUCTIONS.split())
    assert "4-8 words" in flat
    assert "friendly" in flat
    assert "An acknowledgement means you heard the request" in flat
    assert "within 30 words" not in flat, "combined budget is replaced by per-turn-type limits"


def test_result_sentence_after_a_tool_is_one_or_two_friendly_sentences():
    flat = " ".join(VOICE_INSTRUCTIONS.split())
    assert "one or two friendly sentences" in flat
    assert "about 25 words" in flat


def test_no_prompt_grants_authority_to_invent_success_or_confirm_orders():
    for prompt in (INSTRUCTIONS, VOICE_INSTRUCTIONS):
        flat = " ".join(prompt.split())
        assert "Never guess facts" in flat or "Never invent availability" in flat
    assert "Ask only for missing information, never\norder confirmation" in VOICE_INSTRUCTIONS


def test_the_voice_layer_states_results_only_by_relaying_codex():
    """15 results were spoken on 2026-11-04 without any delegation (claim_guard.py)."""
    flat = " ".join(VOICE_INSTRUCTIONS.split())
    assert flat.startswith("You never know the kiosk state yourself."), (
        "the rule comes first, before the exact sentences it governs"
    )
    assert "only when relaying Codex's result for the guest's latest request" in flat
    assert "If you have not delegated the latest request, delegate it now" in flat
    assert "never repeat an earlier result as if it were new" in flat.lower()
    assert QR_LINE in VOICE_INSTRUCTIONS and "the paid result below" in flat
