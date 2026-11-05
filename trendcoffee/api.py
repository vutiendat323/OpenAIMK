"""Local HTTP adapter with capability sessions and separate operator authority."""

import asyncio
import contextlib
import hmac
import json
import logging
import os
import secrets
import struct
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from .agent import Agent
from .merchant import from_environment
from .service import Service, ServiceError


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Line(Input):
    item_id: str = Field(min_length=1, max_length=200)
    quantity: StrictInt = Field(ge=1, le=100)
    options: dict[str, str] = Field(default_factory=dict, max_length=12)
    note: str = Field(default="", max_length=300)


class Quote(Input):
    lines: list[Line] = Field(min_length=1, max_length=20)
    fulfillment: str | None = None
    table_label: str | None = Field(default=None, max_length=50)
    order_note: str = Field(default="", max_length=1000)


class Confirm(Input):
    quote_id: str = Field(min_length=1, max_length=100)
    confirmation_token: str = Field(min_length=1, max_length=100)
    user_confirmed: bool = False


class Checkout(Quote):
    checkout_id: str = Field(min_length=1, max_length=100)


class Memory(Input):
    key: str = Field(max_length=40)
    value: str = Field(min_length=1, max_length=200)
    consent: bool = False


class Message(Input):
    message: str = Field(min_length=1, max_length=2000)


class Support(Input):
    reason: str = Field(min_length=1, max_length=1000)


class Transition(Input):
    status: str | None = Field(default=None, max_length=40)
    payment_status: str | None = Field(default=None, max_length=40)


def create_app(service=None, staff_token=None, semantic=None, kiosk_host=None):
    svc = service or Service(
        os.environ.get("TREND_DB", ".runtime/trendcoffee.db"), merchant=from_environment()
    )
    secret = staff_token if staff_token is not None else os.environ.get("TREND_STAFF_TOKEN", "")
    agent = Agent(svc, semantic=semantic)
    timings = deque(maxlen=2000)
    if kiosk_host is None and os.environ.get("TREND_CODEX_VOICE") == "1":
        from .av_transport import FusionProcess
        from .kiosk import InteractionHost

        root = Path(__file__).resolve().parent.parent
        visual_url = "ws://127.0.0.1:9877"
        kiosk_host = InteractionHost(
            svc, visual_url=visual_url, fusion=FusionProcess(root, visual_url)
        )

    @asynccontextmanager
    async def lifespan(app):
        from .invoices import invoice_worker

        warm = asyncio.create_task(kiosk_host.warmup()) if kiosk_host else None
        try:
            async with invoice_worker(svc):
                yield
        finally:
            if warm:
                warm.cancel()
                await asyncio.gather(warm, return_exceptions=True)
            if kiosk_host:
                await kiosk_host.close()

    app = FastAPI(title="Trend Coffee Service", version="0.1.0", lifespan=lifespan)
    app.state.service = svc
    from .avatar import install_avatar_routes

    install_avatar_routes(app, svc)

    @app.exception_handler(ServiceError)
    async def service_error(request, exc):
        return JSONResponse(status_code=exc.status, content={"error": exc.code})

    @app.middleware("http")
    async def timing(request: Request, call_next):
        started = time.perf_counter()
        # Avoid accepting arbitrarily large request bodies before Pydantic validation.
        try:
            size = int(request.headers.get("content-length", "0") or "0")
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "invalid_content_length"})
        if size < 0:
            return JSONResponse(status_code=400, content={"error": "invalid_content_length"})
        if size > 32768:
            return JSONResponse(status_code=413, content={"error": "body_too_large"})
        request.state.style_nonce = (
            secrets.token_urlsafe(24) if request.url.path in ("/", "/index.html") else None
        )
        response = await call_next(request)
        elapsed = (time.perf_counter() - started) * 1000
        timings.append(elapsed)
        response.headers["Server-Timing"] = f"app;dur={elapsed:.3f}"
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; "
            + (
                f"style-src 'self' 'nonce-{request.state.style_nonce}'; "
                if request.state.style_nonce
                else "style-src 'self'; "
            )
            + "connect-src 'self'; worker-src 'self'; media-src 'self' blob:; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'"
        )
        return response

    def customer(authorization: str = Header(default="")):
        if not authorization.startswith("Bearer "):
            raise ServiceError("session_required", 401)
        token = authorization[7:]
        svc.memory(token)
        return token

    def staff(authorization: str = Header(default="")):
        if not secret:
            raise ServiceError("staff_disabled", 503)
        if not authorization.startswith("Bearer ") or not hmac.compare_digest(
            authorization[7:].encode(), secret.encode()
        ):
            raise ServiceError("staff_forbidden", 403)

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "mode": "merchant_api" if svc.merchant else "local_queue_only",
            "live_pos_connected": bool(svc.merchant),
        }

    @app.post("/api/sessions")
    def session():
        return {"session_token": svc.new_session(), "expires_in_days": 30}

    @app.get("/api/kiosk/status")
    def kiosk_status():
        return {
            "enabled": kiosk_host is not None,
            "input": "av_fusion_pcm16",
            "voice": "codex_cli_native",
            "session_active": bool(kiosk_host and kiosk_host.active),
            "voice_ready": bool(kiosk_host and kiosk_host.voice_ready),
            "voice_prepared": bool(
                kiosk_host and getattr(kiosk_host.codex, "prepared_voice_ready", False)
            ),
            "microphone_receiving": bool(
                kiosk_host
                and kiosk_host.last_microphone_at is not None
                and kiosk_host.clock() - kiosk_host.last_microphone_at < 2
            ),
            "accepted_audio_receiving": bool(
                kiosk_host
                and kiosk_host.active
                and kiosk_host.last_accepted_audio_at is not None
                and kiosk_host.clock() - kiosk_host.last_accepted_audio_at < 2
            ),
            "audio_gate": kiosk_host.audio_gate if kiosk_host and kiosk_host.active else None,
            "audio_metrics": kiosk_host.audio_metrics if kiosk_host else {},
        }

    @app.get("/api/kiosk/voices")
    async def kiosk_voices():
        if not kiosk_host:
            return {"voices": []}
        return {"voices": await kiosk_host.voice_options()}

    @app.websocket("/api/kiosk")
    async def kiosk_socket(socket: WebSocket):
        origin = socket.headers.get("origin", "")
        expected = (
            ("https" if socket.url.scheme == "wss" else "http")
            + "://"
            + socket.headers.get("host", "")
        )
        if not kiosk_host or origin != expected:
            await socket.close(code=1008)
            return
        await socket.accept()
        controller = None
        ended = "closed by browser"
        send_lock = asyncio.Lock()

        async def send(event):
            async with send_lock:
                await socket.send_json(event)

        try:
            message = await asyncio.wait_for(socket.receive_text(), 5)
            if len(message) > 4096:
                raise ServiceError("invalid_kiosk_auth")
            auth = json.loads(message)
            if auth.get("type") != "auth":
                raise ServiceError("session_required", 401)
            controller = await kiosk_host.attach(
                auth.get("session_token", ""),
                send,
                camera_source=auth.get("camera_source", "local"),
                voice=auth.get("voice"),
                require_microphone=True,
            )
            kiosk_host.start_background()
            while True:
                incoming = await socket.receive()
                if incoming["type"] == "websocket.disconnect":
                    break
                raw = incoming.get("bytes")
                if raw is not None:
                    if not raw or len(raw) > 256001:
                        raise ServiceError("invalid_media_packet")
                    if raw[0] == 1 and len(raw) == 2565:
                        generation = struct.unpack("<I", raw[1:5])[0]
                        if generation == kiosk_host.generation and kiosk_host.active:
                            await kiosk_host.microphone(generation, raw[5:])
                    elif raw[0] == 2:
                        await kiosk_host.camera(raw[1:])
                    continue
                raw = incoming.get("text", "")
                if len(raw) > 16384:
                    raise ServiceError("invalid_kiosk_command")
                message = json.loads(raw)
                ident = message.get("id")
                try:
                    result = await kiosk_host.command(message)
                    await send(
                        {
                            "type": "result",
                            "id": ident,
                            "result": result,
                            "generation": kiosk_host.generation,
                        }
                    )
                except ServiceError as error:
                    await send(
                        {
                            "type": "error",
                            "id": ident,
                            "error": error.code,
                            "generation": kiosk_host.generation,
                        }
                    )
        except (TimeoutError, ServiceError, WebSocketDisconnect, ValueError, TypeError) as error:
            ended = f"{type(error).__name__} {getattr(error, 'code', '')}".strip()
            with contextlib.suppress(Exception):
                await socket.close(code=1008)
        except BaseException as error:
            ended = f"{type(error).__name__}: {error}"
            raise
        finally:
            # Each socket end detaches the kiosk and releases the device camera in Visual.
            logging.getLogger(__name__).warning(
                "Kiosk socket ended at %s: %s", time.strftime("%H:%M:%S"), ended
            )
            if controller:
                await kiosk_host.detach(controller)

    @app.get("/api/menu")
    def menu(q: str = ""):
        return {
            **svc.menu_search(q[:500]),
            "availability": "snapshot_not_live",
            "merchant_connected": svc.merchant is not None,
        }

    @app.get("/api/knowledge")
    def knowledge(q: str = ""):
        return {"results": svc.search(q[:500])}

    @app.get("/api/tables")
    def tables(table_label: str | None = None):
        return svc.tables(table_label)

    @app.post("/api/chat")
    async def chat(data: Message, token=Depends(customer)):
        return await agent.chat(token, data.message)

    @app.get("/api/memory")
    def memory(token=Depends(customer)):
        return svc.memory(token)

    @app.post("/api/memory")
    def remember(data: Memory, token=Depends(customer)):
        return svc.remember(token, data.key, data.value, data.consent)

    @app.delete("/api/memory")
    def forget(token=Depends(customer)):
        return svc.forget(token)

    @app.post("/api/quotes")
    def quote(data: Quote, token=Depends(customer)):
        return svc.quote(
            token,
            [line.model_dump() for line in data.lines],
            data.fulfillment,
            data.table_label,
            order_note=data.order_note,
        )

    @app.post("/api/checkout")
    def checkout(data: Checkout, token=Depends(customer)):
        return svc.checkout(
            token,
            [line.model_dump() for line in data.lines],
            data.fulfillment,
            data.table_label,
            checkout_id=data.checkout_id,
            order_note=data.order_note,
        )

    @app.post("/api/orders")
    def submit(data: Confirm, token=Depends(customer)):
        return svc.submit(token, data.quote_id, data.confirmation_token, data.user_confirmed)

    @app.get("/api/orders/{order_id}/payment")
    def payment(order_id: str, token=Depends(customer)):
        return svc.payment(token, order_id)

    @app.post("/api/orders/{order_id}/invoice")
    def print_invoice(order_id: str, token=Depends(customer)):
        return svc.print_invoice(token, order_id)

    @app.get("/api/orders/{order_id}/invoice")
    def invoice_status(order_id: str, token=Depends(customer)):
        return svc.invoice_status(token, order_id)

    @app.get("/api/progress")
    def progress(token=Depends(customer)):
        return svc.progress(token)

    @app.post("/api/handoffs")
    def handoff(data: Support, token=Depends(customer)):
        return svc.handoff(token, data.reason)

    @app.get("/api/staff/queue", dependencies=[Depends(staff)])
    def queue():
        return svc.staff_queue()

    @app.post("/api/staff/orders/{order_id}", dependencies=[Depends(staff)])
    def transition(order_id: str, data: Transition):
        return svc.staff_update(order_id, data.status, data.payment_status)

    @app.post("/api/staff/handoffs/{handoff_id}", dependencies=[Depends(staff)])
    def handle_handoff(handoff_id: str, data: Transition):
        if data.payment_status is not None:
            raise ServiceError("invalid_transition")
        return svc.staff_handoff(handoff_id, data.status)

    @app.get("/api/staff/metrics", dependencies=[Depends(staff)])
    def metrics():
        values = sorted(timings)

        def percentile(fraction):
            return (
                round(values[min(int((len(values) - 1) * fraction), len(values) - 1)], 3)
                if values
                else 0
            )

        return {
            "requests": len(values),
            "window": 2000,
            "p50_ms": percentile(0.5),
            "p95_ms": percentile(0.95),
            "p99_ms": percentile(0.99),
        }

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/index.html", response_class=HTMLResponse, include_in_schema=False)
    def kiosk(request: Request):
        template = (Path(__file__).parent / "static" / "index.html").read_text()
        return HTMLResponse(template.replace("__CSP_NONCE__", request.state.style_nonce))

    app.mount(
        "/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="console"
    )
    return app
