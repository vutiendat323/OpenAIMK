"""Opt-in rendered speaker-output quality through the real browser/avatar transport."""

import asyncio
import contextlib
import json
import os
import shutil
import threading
import time

import pytest
import uvicorn
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.responses import Response

from trendcoffee.api import create_app

CAPTURE = """class CapturePCM extends AudioWorkletProcessor {
  constructor(){super();this.samples=new Float32Array(14*48000);this.offset=0;}
  process(inputs){const input=inputs[0]?.[0];if(input && this.offset<this.samples.length){
    const n=Math.min(input.length,this.samples.length-this.offset);
    this.samples.set(input.subarray(0,n),this.offset);this.offset+=n;
    if(this.offset===this.samples.length)this.port.postMessage(this.samples,[this.samples.buffer]);
  }return true;}}
registerProcessor('capture-pcm',CapturePCM);
"""


@pytest.mark.parametrize("renderer", ["unavailable", "paused", "live"])
def test_native_sized_packets_render_continuously_and_status_does_not_flicker(
    svc, monkeypatch, renderer
):
    from playwright.sync_api import expect, sync_playwright

    url = os.getenv("TREND_TEST_AVATAR_URL")
    if renderer == "live" and not url:
        pytest.skip("Set TREND_TEST_AVATAR_URL for real GPU/WebRTC output quality")
    monkeypatch.setenv("TREND_AVATAR_URL", url or "http://127.0.0.1:1")
    app = create_app(service=svc)

    @app.get("/quality-capture.js")
    def worklet():
        return Response(CAPTURE, media_type="application/javascript")

    app.router.routes.insert(0, app.router.routes.pop())

    @app.websocket("/api/kiosk")
    async def fixture_voice(socket: WebSocket):
        await socket.accept()
        while True:
            event = await socket.receive()
            if event["type"] == "websocket.disconnect":
                return
            if event.get("text") and json.loads(event["text"]).get("type") == "auth":
                await socket.send_json({"type": "camera", "generation": 0, "local_available": True})

    app.router.routes.insert(0, app.router.routes.pop())
    if renderer != "live":

        @app.websocket("/api/avatar")
        async def failed_renderer(socket: WebSocket):
            await socket.accept()
            await socket.receive_json()
            await socket.send_json({"type": "ready", "flow_control": True})
            # The engine never answers SDP, then drops the connection mid-speech.
            await asyncio.sleep(3)
            with contextlib.suppress(WebSocketDisconnect):
                await socket.close()

        app.router.routes.insert(0, app.router.routes.pop())

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="error"))
    worker = threading.Thread(target=server.run, daemon=True)
    worker.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.02)
        assert server.started
        port = server.servers[0].sockets[0].getsockname()[1]
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                executable_path=shutil.which("chromium"),
                args=[
                    "--no-sandbox",
                    "--use-fake-ui-for-media-stream",
                    "--use-fake-device-for-media-stream",
                    "--autoplay-policy=no-user-gesture-required",
                ],
            )
            try:
                page = browser.new_page(permissions=["microphone", "camera"])
                page.add_init_script("""
                  navigator.permissions.query=async()=>({state:'prompt'});
                  const getMedia=navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
                  navigator.mediaDevices.getUserMedia=async options=>{
                    const stream=await getMedia(options);
                    window.captureSettings=stream.getAudioTracks()[0].getSettings();
                    return stream;
                  };
                  window.qualityMeters=[];window.avatarSentAt=[];
                  const create=AudioContext.prototype.createAnalyser;
                  AudioContext.prototype.createAnalyser=function(){const meter=create.call(this);window.qualityMeters.push(meter);return meter;};
                  const RTC=RTCPeerConnection;
                  window.RTCPeerConnection=class extends RTC{constructor(...args){super(...args);window.qualityPeer=this;}};
                  const Socket=WebSocket;
                  window.WebSocket=class extends Socket{constructor(...args){super(...args);
                    if(String(args[0]).endsWith('/api/kiosk'))window.voiceFixture=this;}
                    send(raw){if(typeof raw==='string'&&this.url.endsWith('/api/avatar')&&JSON.parse(raw).type==='audio')avatarSentAt.push(performance.now());return super.send(raw);}};
                """)
                page.route(
                    "**/api/kiosk/status", lambda route: route.fulfill(json={"enabled": True})
                )
                page.route(
                    "**/api/kiosk/voices", lambda route: route.fulfill(json={"voices": ["maple"]})
                )
                if renderer != "live":
                    page.route(
                        "**/api/avatar/status",
                        lambda route: route.fulfill(json={"enabled": True, "actions": []}),
                    )
                page.goto(f"http://127.0.0.1:{port}/")
                page.get_by_role("button", name="Bật micro", exact=True).click()
                expect(page.get_by_role("button", name="Bắt đầu nói", exact=True)).to_be_visible(
                    timeout=30000
                )
                assert page.evaluate("captureSettings.autoGainControl") is False
                assert page.evaluate("captureSettings.noiseSuppression") is False
                assert page.evaluate("captureSettings.echoCancellation") is True
                if renderer == "live":
                    page.wait_for_function(
                        "() => document.querySelector('.avatar-stage video').readyState >= 2",
                        timeout=20000,
                    )
                result = page.evaluate(
                    """async(pauseMs)=>{
                  const meter=qualityMeters[1],context=meter.context;
                  await context.audioWorklet.addModule('/quality-capture.js');
                  const capture=new AudioWorkletNode(context,'capture-pcm');
                  meter.connect(capture);capture.connect(context.destination);
                  const recorded=new Promise(resolve=>capture.port.onmessage=({data})=>resolve(data));
                  const events=[];
                  const observer=new MutationObserver(()=>events.push(document.querySelector('.avatar-assistant')?.dataset.phase));
                  observer.observe(document.body,{attributes:true,subtree:true,attributeFilter:['data-phase']});
                  const emit=message=>voiceFixture.onmessage({data:JSON.stringify({generation:1,...message})});
                  emit({type:'session',voice:'maple'});emit({type:'status',status:'listening'});
                  const packets=[];
                  for(let packet=0;packet<500;packet++){
                    const bytes=new Uint8Array(1920),view=new DataView(bytes.buffer);
                    for(let i=0;i<960;i++){const t=(packet*960+i)/48000;
                      view.setInt16(i*2,Math.round(8000*Math.sin(2*Math.PI*1733*t)+2000*Math.sin(2*Math.PI*373*t)),true);}
                    packets.push(btoa(String.fromCharCode(...bytes)));
                  }
                  for(let i=0;i<packets.length;i++)setTimeout(()=>emit({type:'audio',audio:{data:packets[i],sampleRate:48000,numChannels:1}}),i*20+[0,4,12,2,7][i%5]+(i>=100?pauseMs:0));
                  for(const at of [550,1550,3550,5550,7550])setTimeout(()=>{
                    const until=performance.now()+45;while(performance.now()<until){}
                  },at);
                  const samples=await recorded;observer.disconnect();capture.disconnect();
                  const energies=[];
                  for(let start=0;start+960<=samples.length;start+=960){
                    let sum=0;for(let i=start;i<start+960;i++)sum+=samples[i]*samples[i];
                    energies.push(Math.sqrt(sum/960));}
                  const active=energies.map((value,index)=>value>.04?index:-1).filter(index=>index>=0);
                  let silent=0;for(let i=active[0]+2;i<active.at(-1)-2;i++)if(energies[i]<.01)silent++;
                  const states=events.filter((value,index)=>!index||events[index-1]!==value);
                  const stats=[...(await qualityPeer.getStats()).values()].find(s=>s.type==='inbound-rtp'&&s.kind==='audio');
                  return {silentFrames:silent,outputSpan:(active.at(-1)-active[0]+1)*.02,
                    sentPackets:avatarSentAt.length,sendSpan:(avatarSentAt.at(-1)-avatarSentAt[0])/1000,
                    concealed:stats?.concealedSamples,jitter:stats?.jitter,
                    speakingStarts:states.filter(value=>value==='speaking').length,states};
                }""",
                    500 if renderer == "paused" else 0,
                )
                print(result)
                assert abs(result["silentFrames"] - (25 if renderer == "paused" else 0)) <= (
                    2 if renderer == "paused" else 0
                ), result
                assert abs(result["outputSpan"] - (10.5 if renderer == "paused" else 10)) <= 0.06, (
                    result
                )
                assert result["speakingStarts"] == 1, result
            finally:
                browser.close()
    finally:
        server.should_exit = True
        worker.join(10)
