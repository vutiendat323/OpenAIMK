"""Render actual native output packets through the browser without a speaker/model."""

import asyncio
import base64
import math
import shutil
import struct
import subprocess
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from aiortc.mediastreams import MediaStreamError
from av import AudioFrame

from trendcoffee.native_peer import NativePeer


def test_native_packets_render_without_resampling_clicks_at_every_join():
    from playwright.sync_api import sync_playwright

    executable = shutil.which("chromium") or shutil.which("chromium-browser")
    if not executable or not shutil.which("node"):
        pytest.skip("Chromium/Node required for actual Web Audio rendering")

    async def capture():
        packets = []

        async def event(method, params):
            if method == "thread/realtime/outputAudio/delta":
                packets.append(params["audio"])

        class Track:
            position = 0

            async def recv(self):
                if self.position >= 30 * 960:
                    raise MediaStreamError
                frame = AudioFrame(format="s16", layout="mono", samples=960)
                pcm = b"".join(
                    struct.pack("<h", round(12000 * math.sin(2 * math.pi * 1733 * i / 48000)))
                    for i in range(self.position, self.position + 960)
                )
                frame.planes[0].update(pcm)
                frame.sample_rate = 48000
                self.position += 960
                return frame

        peer = NativePeer(None, "fixture", event)
        try:
            await peer.receive_audio(Track())
            await asyncio.sleep(0)
            return packets
        finally:
            await peer.close()

    packets = asyncio.run(capture())
    assert len(packets) >= 29
    whole = {
        **packets[0],
        "data": base64.b64encode(
            b"".join(base64.b64decode(packet["data"]) for packet in packets)
        ).decode(),
    }
    root = Path(__file__).resolve().parents[1]
    script = subprocess.check_output(
        ["node", "--input-type=module"],
        cwd=root,
        timeout=10,
        input=b"""
import ts from './frontend/node_modules/typescript/lib/typescript.js';
import fs from 'node:fs';
process.stdout.write(ts.transpileModule(fs.readFileSync('frontend/src/voiceAudio.ts','utf8'),
{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}})
.outputText.replace(/^export /gm,''));
""",
    ).decode()
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(root / "frontend/public"))
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=executable, args=["--no-sandbox"])
        try:
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{server.server_port}/")
            result = page.evaluate(
                """async ({script, packets, whole}) => {
                    const VoicePlayer = new Function(script + '; return VoicePlayer;')();
                    async function render(chunks) {
                        const context = new OfflineAudioContext(1, 48000, 48000);
                        const player = await VoicePlayer.create(context, () => {});
                        for (const chunk of chunks) player.push(chunk);
                        return (await context.startRendering()).getChannelData(0);
                    }
                    const split = await render(packets), continuous = await render([whole]);
                    let maxError = 0;
                    for (let i = 6000; i < 34000; i++)
                        maxError = Math.max(maxError, Math.abs(split[i] - continuous[i]));
                    return {maxError};
                }""",
                {"script": script, "packets": packets, "whole": whole},
            )
            assert result["maxError"] < 0.001, result
        finally:
            browser.close()
            server.shutdown()
            server.server_close()


def test_timed_browser_playback_keeps_words_while_ui_thread_is_busy():
    """Render actual-time delivery and UI stalls, then compare every middle sample."""
    from playwright.sync_api import sync_playwright

    executable = shutil.which("chromium") or shutil.which("chromium-browser")
    if not executable:
        pytest.skip("Chromium required")
    root = Path(__file__).resolve().parents[1]
    # A changing signal makes missing/reordered samples detectable, unlike a single tone.
    pcm = b"".join(
        struct.pack("<h", round(9000 * math.sin(i * 0.17 + 0.000003 * i * i))) for i in range(48000)
    )
    packets = [
        {
            "data": base64.b64encode(pcm[i : i + 1920]).decode(),
            "sampleRate": 48000,
            "numChannels": 1,
        }
        for i in range(0, len(pcm), 1920)
    ]
    script = subprocess.check_output(
        ["node", "--input-type=module"],
        cwd=root,
        timeout=10,
        input=b"""
import ts from './frontend/node_modules/typescript/lib/typescript.js';
import fs from 'node:fs';
process.stdout.write(ts.transpileModule(fs.readFileSync('frontend/src/voiceAudio.ts','utf8'),
{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}})
.outputText.replace(/^export /gm,''));
""",
    ).decode()
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(root / "frontend/public"))
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                executable_path=executable,
                args=["--no-sandbox", "--autoplay-policy=no-user-gesture-required"],
            )
            try:
                page = browser.new_page()
                page.goto(f"http://127.0.0.1:{server.server_port}/")
                result = page.evaluate(
                    """async ({script, packets}) => {
                    const VoicePlayer = new Function(script + '; return VoicePlayer;')();
                    const context = new AudioContext({sampleRate:48000,latencyHint:"interactive"});
                    const recorder = `class Capture extends AudioWorkletProcessor {
                        constructor(){super();this.data=new Float32Array(96000);this.offset=0;}
                        process(inputs){const samples=inputs[0]?.[0];if(samples && this.offset<this.data.length){
                            this.data.set(samples,this.offset);this.offset+=samples.length;
                            if(this.offset===this.data.length)this.port.postMessage(this.data,[this.data.buffer]);
                        }return true;}}
                        registerProcessor('capture',Capture);`;
                    const url=URL.createObjectURL(new Blob([recorder],{type:'text/javascript'}));
                    await context.audioWorklet.addModule(url);URL.revokeObjectURL(url);
                    const capture=new AudioWorkletNode(context,'capture');capture.connect(context.destination);
                    const recording=new Promise(resolve=>capture.port.onmessage=e=>resolve(e.data));
                    const events=[];
                    const player=await VoicePlayer.create(context,value=>events.push({value,time:context.currentTime}),capture);
                    await context.resume();
                    for(let i=0;i<packets.length;i++)
                        setTimeout(()=>{player.push(packets[i]);},i*20 + [0,4,12,2,7][i%5]);
                    for(const at of [250,650])setTimeout(()=>{
                        const until=performance.now()+120;while(performance.now()<until){}
                    },at);
                    const recorded=await recording;
                    const expected=[];
                    for(const packet of packets){const bytes=Uint8Array.from(atob(packet.data),c=>c.charCodeAt(0));
                        const v=new DataView(bytes.buffer);for(let i=0;i<bytes.length;i+=2)expected.push(v.getInt16(i,true)/32768);}
                    // Match beyond the 3 ms fade-in to locate the exact output sample offset.
                    let offset=-1;
                    for(let candidate=0;candidate<12000;candidate++){
                        if(Math.abs(recorded[candidate+1000]-expected[1000])<1e-7 &&
                           Math.abs(recorded[candidate+1001]-expected[1001])<1e-7){offset=candidate;break;}}
                    let maxError=1;
                    if(offset>=0){maxError=0;for(let i=240;i<expected.length-240;i++)
                        maxError=Math.max(maxError,Math.abs(recorded[offset+i]-expected[i]));}
                    player.close();await context.close();
                    return {offset,maxError,firstAudioMs:offset/48,events};
                }""",
                    {"script": script, "packets": packets},
                )
                assert result["offset"] >= 0, result
                assert result["firstAudioMs"] < 250, result
                assert result["maxError"] < 0.0001, result
                assert [event["value"] for event in result["events"]] == [True, False], result
            finally:
                browser.close()
    finally:
        server.shutdown()
        server.server_close()
