import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from test_kiosk_runtime import FakeCodex

from trendcoffee.api import create_app
from trendcoffee.kiosk import InteractionHost


def test_controller_requires_same_origin_and_capability(svc):
    app = create_app(service=svc, kiosk_host=InteractionHost(svc, codex=FakeCodex()))
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/api/kiosk", headers={"origin": "https://evil.example"}):
                pass
        with client.websocket_connect(
            "/api/kiosk", headers={"origin": "http://testserver"}
        ) as socket:
            socket.send_json({"type": "auth", "session_token": "invalid"})
            with pytest.raises(WebSocketDisconnect):
                socket.receive_json()


def test_touch_checkout_places_shared_cart_without_confirmation(svc):
    app = create_app(service=svc, kiosk_host=InteractionHost(svc, codex=FakeCodex()))
    with TestClient(app) as client:
        token = client.post("/api/sessions").json()["session_token"]
        with client.websocket_connect(
            "/api/kiosk", headers={"origin": "http://testserver"}
        ) as socket:
            socket.send_json({"type": "auth", "session_token": token})
            assert socket.receive_json()["type"] == "status"
            socket.send_json({"id": "begin", "type": "begin"})
            session = None
            for _ in range(5):
                event = socket.receive_json()
                if event["type"] == "session":
                    session = event
                    break
            assert session and session["session_token"] != token
            gen = session["generation"]

            def command(ident, **data):
                socket.send_json({"id": ident, "generation": gen, **data})
                for _ in range(20):
                    event = socket.receive_json()
                    if event.get("id") == ident:
                        assert event["type"] == "result", event
                        return event["result"]
                raise AssertionError("No command response")

            command(
                "add",
                type="action",
                action={"type": "add", "item": {"id": "coffee"}, "quantity": 2},
            )
            command("mode", type="action", action={"type": "fulfillment", "value": "takeaway"})
            order = command("checkout", type="checkout")
            assert command("retry", type="checkout")["id"] == order["id"]
            assert order["total_vnd"] == 60000
            assert order["payment_status"] == "unverified"
            assert (
                len(
                    client.get(
                        "/api/progress",
                        headers={"Authorization": "Bearer " + session["session_token"]},
                    ).json()["orders"]
                )
                == 1
            )


@pytest.mark.parametrize("source", ["local", "device"])
def test_controller_camera_selection_reaches_host(svc, source):
    host = InteractionHost(svc, codex=FakeCodex())
    with TestClient(create_app(service=svc, kiosk_host=host)) as client:
        token = client.post("/api/sessions").json()["session_token"]
        with client.websocket_connect(
            "/api/kiosk", headers={"origin": "http://testserver"}
        ) as socket:
            socket.send_json({"type": "auth", "session_token": token, "camera_source": source})
            assert socket.receive_json()["type"] == "status"
            assert host.camera_source == source


@pytest.mark.parametrize("source", ["unknown", True, None, {}])
def test_controller_camera_selection_rejects_invalid_source(svc, source):
    host = InteractionHost(svc, codex=FakeCodex())
    with TestClient(create_app(service=svc, kiosk_host=host)) as client:
        token = client.post("/api/sessions").json()["session_token"]
        with client.websocket_connect(
            "/api/kiosk", headers={"origin": "http://testserver"}
        ) as socket:
            socket.send_json({"type": "auth", "session_token": token, "camera_source": source})
            with pytest.raises(WebSocketDisconnect):
                socket.receive_json()
        assert host.controller is None
