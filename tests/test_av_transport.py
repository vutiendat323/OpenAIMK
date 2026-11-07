"""Fail closed at the boundary between AV evidence and native voice."""

import asyncio
import base64

from trendcoffee.av_transport import accepted_pcm
from trendcoffee.codex_voice import CodexVoice


def test_only_current_fusion_approved_audio_can_reach_native_voice():
    pcm = b"\x01\x02" * 1280
    for verdict, reason, locked, fresh in [
        ("unknown", "kept", False, True),
        ("UNCERTAIN", "kept", True, True),
        ("ACCEPT", "kept", True, False),
        ("REJECT", "silenced_reject", True, True),
        ("UNCERTAIN", "kept", False, True),
        ("REJECT", "kept_target_onset", True, True),
        ("ACCEPT", "kept_target_onset", False, True),
        ("ACCEPT", "kept_target_tail", True, False),
    ]:
        assert accepted_pcm(
            pcm, verdict=verdict, reason=reason, locked=locked, fresh=fresh
        ) == bytes(len(pcm))
    assert accepted_pcm(pcm, verdict="ACCEPT", reason="kept", locked=True, fresh=True) == pcm
    assert (
        accepted_pcm(pcm, verdict="UNCERTAIN", reason="separated", locked=True, fresh=True) == pcm
    )
    assert accepted_pcm(pcm, verdict="None", reason="kept_onset", locked=True, fresh=True) == pcm
    for reason in ("kept_target_onset", "kept_target_tail"):
        assert accepted_pcm(pcm, verdict="ACCEPT", reason=reason, locked=True, fresh=True) == pcm


def test_native_voice_uses_filtered_pcm_transport():
    async def run():
        native = CodexVoice(".")
        native.callbacks["thread"] = (None, None)
        sent = []

        async def request(method, params, **kwargs):
            sent.append((method, params))
            if method == "thread/realtime/start":
                if "thread" in native.started:
                    native.started["thread"].set_result({"threadId": "thread"})
                else:
                    native.sdp["thread"].set_result("fixture-answer")
            return {}

        native.request = request
        await native.start_audio("thread")
        assert sent[0][1]["transport"] == {"type": "websocket"}
        assert sent[0][1]["delegationAckFiller"] is True
        assert sent[0][1]["codexResponseHandoffMode"] == "commentary"
        assert sent[0][1]["includeStartupContext"] is False
        await native.append_audio("thread", b"\x01\x00" * 1280)
        method, params = sent[-1]
        assert method == "thread/realtime/appendAudio"
        assert params["audio"]["sampleRate"] == 16000
        assert base64.b64decode(params["audio"]["data"]) == b"\x01\x00" * 1280
        assert await native.start_voice("thread", "fixture-offer") == "fixture-answer"
        params = sent[-1][1]
        assert params["transport"] == {"type": "webrtc", "sdp": "fixture-offer"}
        assert params["delegationAckFiller"] is True
        assert params["codexResponseHandoffMode"] == "commentary"

    asyncio.run(run())


def test_mcp_overrides_are_dotted_keys_not_quoted_literal_names():
    native = CodexVoice(".")
    overrides = [arg for arg in native.argv() if arg.startswith("mcp_servers.")]
    assert overrides
    assert all('"' not in arg for arg in overrides)


def test_native_business_tools_keep_required_code_mode_host_available():
    args = CodexVoice(".").argv()
    disabled = {args[i + 1] for i, arg in enumerate(args[:-1]) if arg == "--disable"}
    assert "shell_tool" in disabled
    assert "code_mode_host" not in disabled
    assert "apps" in disabled
    assert "plugins" in disabled


def test_guest_thread_uses_luna_medium_without_fast_or_model_fallback():
    async def run():
        native = CodexVoice(".")
        requests = []

        async def start():
            pass

        async def request(method, params):
            requests.append((method, params))
            return {"thread": {"id": "guest-thread"}}

        native.start, native.request = start, request
        assert await native.create_thread([], None, None) == "guest-thread"
        method, params = requests[0]
        assert method == "thread/start"
        assert params["model"] == "gpt-6-luna"
        assert "serviceTier" not in params
        assert params["config"]["model_reasoning_effort"] == "medium"
        assert params["allowProviderModelFallback"] is False

    asyncio.run(run())


def test_guest_thread_leaves_out_coding_context_codex_would_load():
    """The repo's AGENTS.md and the host's skill list (~26k chars) are not for guests."""

    async def run():
        native = CodexVoice(".")
        requests = []

        async def start():
            pass

        async def request(method, params):
            requests.append((method, params))
            return {"thread": {"id": "guest-thread"}}

        native.start, native.request = start, request
        await native.create_thread([], None, None)
        config = requests[0][1]["config"]
        assert config["project_doc_max_bytes"] == 0
        assert config["skills.include_instructions"] is False

    asyncio.run(run())


def test_native_process_exit_notifies_guest_to_stop_voice():
    async def run():
        events = []

        class Output:
            async def readline(self):
                return b""

        class Process:
            stdout = Output()

        native = CodexVoice(".")
        native.process = Process()

        async def notify(method, params):
            events.append(method)

        native.callbacks["guest"] = (None, notify)
        await native._read()
        assert "thread/realtime/closed" in events

    asyncio.run(run())


def test_codex_is_resolved_when_service_path_omits_user_bin(monkeypatch, tmp_path):
    import shutil
    from pathlib import Path

    binary = tmp_path / ".local/bin/codex"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(0o755)
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setattr(shutil, "which", lambda executable: None)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert CodexVoice(".").argv()[0] == str(binary)
    assert CodexVoice(".", executable="/custom/codex").argv()[0] == "/custom/codex"


def test_fusion_begin_waits_for_matching_worker_session_ready():
    from types import SimpleNamespace

    from trendcoffee.av_transport import FusionProcess

    async def run():
        fusion = FusionProcess(".", None)
        output = asyncio.StreamReader()
        fusion.process = SimpleNamespace(stdout=output)
        sent = asyncio.Event()
        events = []

        async def start():
            pass

        async def write(message):
            sent.set()

        async def event(message):
            events.append(message)

        fusion.start, fusion._write = start, write
        reader = asyncio.create_task(fusion._read())
        begin = asyncio.create_task(fusion.begin(7, "fixture", event))
        try:
            await sent.wait()
            await asyncio.sleep(0)
            assert not begin.done(), "begin returned before the worker initialized the session"
            output.feed_data(b'{"type":"session_ready","generation":6,"request_id":1}\n')
            await asyncio.sleep(0)
            assert not begin.done()
            output.feed_data(b'{"type":"session_ready","generation":7,"request_id":0}\n')
            await asyncio.sleep(0)
            assert not begin.done()
            output.feed_data(b'{"type":"session_ready","generation":7,"request_id":1}\n')
            await asyncio.wait_for(begin, 1)
        finally:
            begin.cancel()
            reader.cancel()
            await asyncio.gather(begin, reader, return_exceptions=True)

    asyncio.run(run())
