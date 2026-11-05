"""Immediate local mic feedback without waiting for Fusion or fabricating text."""

import asyncio
import shutil
import threading
import time

import pytest
import uvicorn
from test_kiosk_runtime import FakeCodex

from trendcoffee.api import create_app
from trendcoffee.kiosk import InteractionHost


def test_microphone_feedback_precedes_fusion_lock_and_native_transcript(
    svc, tmp_path, record_property
):
    from playwright.sync_api import expect, sync_playwright

    executable = shutil.which("chromium") or shutil.which("chromium-browser")
    if not executable:
        pytest.skip("Local Chromium needed")

    class ReadyCodex(FakeCodex):
        async def start_filtered_voice(self, thread):
            pass

    class Fusion:
        async def start(self):
            pass

        async def begin(self, *args):
            pass

        async def audio(self, pcm):
            pass

        async def playback(self, playing):
            pass

        async def end(self):
            pass

        async def close(self):
            pass

    codex = ReadyCodex()
    host = InteractionHost(svc, codex=codex, fusion=Fusion())
    microphone_packets = []
    microphone = host.microphone

    async def capture_microphone(generation, pcm):
        if any(pcm):
            microphone_packets.append((generation, len(pcm)))
        await microphone(generation, pcm)

    host.microphone = capture_microphone
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(service=svc, kiosk_host=host), host="127.0.0.1", port=0, log_level="error"
        )
    )
    worker = threading.Thread(target=server.run, daemon=True)
    worker.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.02)
        assert server.started
        port = server.servers[0].sockets[0].getsockname()[1]
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=executable,
                args=["--no-sandbox", "--autoplay-policy=no-user-gesture-required"],
            )
            try:
                page = browser.new_page()
                page.add_init_script("""
                    navigator.permissions.query = async () => ({state: 'prompt'});
                    navigator.mediaDevices.getUserMedia = async () => {
                        const context = new AudioContext({sampleRate: 48000});
                        const tone = context.createOscillator();
                        const gain = context.createGain();
                        const output = context.createMediaStreamDestination();
                        gain.gain.value = 0;
                        tone.connect(gain).connect(output);
                        tone.start();
                        await context.resume();
                        window.fixtureMic = {context, gain};
                        return output.stream;
                    };
                """)
                page.set_default_timeout(4000)
                page.goto(f"http://127.0.0.1:{port}/")
                page.get_by_role("button", name="Bật micro", exact=True).click()
                page.get_by_role("button", name="Bắt đầu nói", exact=True).click()
                page.wait_for_function(
                    "() => document.querySelector('.avatar-assistant').dataset.phase === 'speaking'"
                )
                page.wait_for_function(
                    "() => document.querySelector('.avatar-assistant').dataset.phase !== 'speaking'"
                )
                loop = host.tick_task.get_loop()

                def emit(kind, **data):
                    asyncio.run_coroutine_threadsafe(host.emit(kind, **data), loop).result(2)

                # Native is ready, but Fusion deliberately never sends locked=True.
                emit("status", status="listening", message="Bạn nói món muốn gọi nhé.")
                emit("fusion", locked=False)
                expect(page.locator(".avatar-assistant")).to_have_attribute(
                    "data-phase", "listening", timeout=500
                )
                expect(page.locator(".assistant-phase")).to_have_text("Đang lắng nghe")
                page.wait_for_timeout(150)
                assert page.locator(".assistant-wave span").evaluate_all(
                    "nodes => nodes.every(node => parseFloat(node.style.height) === 4)"
                )
                result = page.evaluate("""async () => {
                    const start = performance.now();
                    const wave = document.querySelector('.assistant-wave');
                    return await new Promise(resolve => {
                        const timer = setTimeout(() => {
                            observer.disconnect(); resolve({responded: false});
                        }, 500);
                        const observer = new MutationObserver(() => {
                            if ([...wave.children].some(node => parseFloat(node.style.height) > 6)) {
                                clearTimeout(timer); observer.disconnect();
                                resolve({responded: true, elapsed: performance.now() - start});
                            }
                        });
                        observer.observe(wave, {subtree: true, attributes: true});
                        window.fixtureMic.gain.gain.value = 0.25;
                    });
                }""")
                assert result["responded"], result
                assert result["elapsed"] < 250, result
                record_property("microphone_feedback_ms", round(result["elapsed"], 1))
                for _ in range(10):
                    if microphone_packets:
                        break
                    page.wait_for_timeout(20)
                assert microphone_packets and microphone_packets[0] == (host.generation, 2560)
                # A local level never creates a user transcript or submits an order.
                expect(page.locator(".assistant-bubble.user")).to_have_count(0)
                assert svc.progress(host.token)["orders"] == []
                page.screenshot(path=str(tmp_path / "microphone-before-fusion.png"))

                # Real native deltas still update one bubble immediately, before turn.done.
                on_event = codex.callbacks[host.thread_id][1]
                for delta, text in [("Xin ", "Xin"), ("chào bạn", "Xin chào bạn")]:
                    asyncio.run_coroutine_threadsafe(
                        on_event(
                            "thread/realtime/transcript/delta",
                            {"role": "user", "delta": delta, "turnId": "fixture-turn"},
                        ),
                        loop,
                    ).result(2)
                    expect(page.locator(".assistant-bubble.user p")).to_have_text(text)
                expect(page.locator(".assistant-bubble.user")).to_have_count(1)
                page.get_by_role("button", name="Tắt micro", exact=True).click()
                expect(page.locator(".avatar-assistant")).to_have_attribute("data-phase", "off")
                expect(page.locator(".assistant-bubble.user")).to_have_count(0)
                assert page.locator(".assistant-wave span").evaluate_all(
                    "nodes => nodes.every(node => parseFloat(node.style.height) === 4)"
                )
            finally:
                browser.close()
    finally:
        server.should_exit = True
        worker.join(5)
