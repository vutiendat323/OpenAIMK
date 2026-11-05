"""Both native transports must use one policy for short spoken customer turns."""

import asyncio

from trendcoffee.codex_voice import CodexVoice


def test_role_bearing_startup_item_cannot_override_the_current_voice_policy():
    async def run():
        voice = CodexVoice(".")
        voice.callbacks["fixture"] = (None, None)
        sent = []

        async def request(method, params, **kwargs):
            sent.append(params)
            if "fixture" in voice.started:
                voice.started["fixture"].set_result({})
            else:
                voice.sdp["fixture"].set_result("fixture-answer")
            return {}

        voice.request = request
        await voice.start_audio("fixture")
        await voice.start_voice("fixture", "fixture-offer")
        assert len(sent) == 2
        for params in sent:
            assert params.get("initialItems") == [
                {"role": "developer", "text": params["prompt"]}
            ], "startup conversation carries a stale/different voice policy"

    asyncio.run(run())
