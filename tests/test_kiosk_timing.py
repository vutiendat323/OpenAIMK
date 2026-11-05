"""Staff tune when a kiosk session starts and ends; guests cannot, and a typo cannot lock it."""

import json

import pytest
from fastapi.testclient import TestClient
from test_kiosk_runtime import FakeCodex

from trendcoffee.api import create_app
from trendcoffee.kiosk import InteractionHost
from trendcoffee.kiosk_timing import KioskTiming, defaults
from trendcoffee.service import ServiceError

STAFF = {"Authorization": "Bearer staff-test-secret"}


def test_defaults_match_the_previous_fixed_boundaries():
    assert defaults() == {
        "presence_distance_m": 0.6,
        "enter_seconds": 2.0,
        "leave_seconds": 3.0,
        "idle_seconds": 120.0,
        "session_limit_seconds": 600.0,
        "warning_seconds": 60.0,
    }


def test_values_are_saved_and_survive_a_restart(tmp_path):
    path = tmp_path / "kiosk-timing.json"
    KioskTiming(path).update({"enter_seconds": 1.5, "idle_seconds": 90})
    reloaded = KioskTiming(path)
    assert reloaded.values["enter_seconds"] == 1.5
    assert reloaded.values["idle_seconds"] == 90
    assert reloaded.values["leave_seconds"] == 3.0, "untouched values keep their default"


@pytest.mark.parametrize(
    "changes",
    [
        {"enter_seconds": 0},
        {"idle_seconds": 10_000},
        {"presence_distance_m": float("nan")},
        {"leave_seconds": True},
        {"leave_seconds": "3"},
        {"unknown": 1},
        {},
        {"warning_seconds": 300, "session_limit_seconds": 300},
    ],
)
def test_out_of_range_or_unknown_values_are_rejected_and_nothing_is_saved(tmp_path, changes):
    path = tmp_path / "kiosk-timing.json"
    timing = KioskTiming(path)
    with pytest.raises(ServiceError) as error:
        timing.update(changes)
    assert error.value.code == "invalid_kiosk_timing"
    assert timing.values == defaults()
    assert not path.exists()


@pytest.mark.parametrize("content", ["not json", "[]", '{"enter_seconds": 99}'])
def test_an_unreadable_file_falls_back_to_defaults(tmp_path, content):
    path = tmp_path / "kiosk-timing.json"
    path.write_text(content)
    assert KioskTiming(path).values == defaults()


def test_anyone_can_read_but_only_staff_can_change(svc):
    client = TestClient(create_app(service=svc, staff_token="staff-test-secret"))
    read = client.get("/api/kiosk/timing").json()
    assert read["values"] == defaults()
    assert read["limits"]["enter_seconds"] == {"min": 0.5, "max": 10.0}
    guest = client.put("/api/kiosk/timing", json={"enter_seconds": 1.0})
    assert guest.status_code == 403 and guest.json() == {"error": "staff_forbidden"}
    wrong = client.put(
        "/api/kiosk/timing",
        json={"enter_seconds": 1.0},
        headers={"Authorization": "Bearer guess"},
    )
    assert wrong.status_code == 403
    saved = client.put("/api/kiosk/timing", json={"enter_seconds": 1.0}, headers=STAFF)
    assert saved.status_code == 200
    assert saved.json()["values"]["enter_seconds"] == 1.0
    assert client.get("/api/kiosk/timing").json()["values"]["enter_seconds"] == 1.0
    stored = json.loads((svc.store.path.parent / "kiosk-timing.json").read_text())
    assert stored["enter_seconds"] == 1.0
    bad = client.put("/api/kiosk/timing", json={"enter_seconds": 99}, headers=STAFF)
    assert bad.status_code == 400 and bad.json() == {"error": "invalid_kiosk_timing"}
    extra = client.put("/api/kiosk/timing", json={"other": 1}, headers=STAFF)
    assert extra.status_code in (400, 422)


def test_changes_are_refused_when_no_staff_code_is_configured(svc):
    client = TestClient(create_app(service=svc, staff_token=""))
    response = client.put("/api/kiosk/timing", json={"enter_seconds": 1.0}, headers=STAFF)
    assert response.status_code == 503 and response.json() == {"error": "staff_disabled"}


def host_with(svc, tmp_path):
    timing = KioskTiming(tmp_path / "kiosk-timing.json")
    clock = [1000.0]
    host = InteractionHost(svc, codex=FakeCodex(), timing=timing, clock=lambda: clock[0])
    return host, timing, clock


def test_presence_limits_apply_between_guests_not_during_one(svc, tmp_path):
    host, timing, _ = host_with(svc, tmp_path)
    assert (host.policy.threshold, host.policy.enter_seconds) == (0.6, 2.0)
    timing.update({"presence_distance_m": 0.9, "enter_seconds": 1.0, "leave_seconds": 5})
    assert host.apply_timing() is True
    assert (host.policy.threshold, host.policy.enter_seconds, host.policy.leave_seconds) == (
        0.9,
        1.0,
        5.0,
    )
    host.active = True
    timing.update({"enter_seconds": 4.0})
    assert host.apply_timing() is False
    assert host.policy.enter_seconds == 1.0, "the current guest keeps their limits"


def test_session_limits_come_from_the_values_the_guest_started_with(svc, tmp_path):
    host, timing, clock = host_with(svc, tmp_path)
    timing.update({"idle_seconds": 45, "session_limit_seconds": 300, "warning_seconds": 30})
    host.session_timing = dict(timing.values)  # what _initialize_guest takes for a guest
    host.started = host.activity_at = clock[0]
    timing.update({"idle_seconds": 600})  # a change during the session waits for the next one
    assert host.session_limit(clock[0] + 44) is None
    assert host.session_limit(clock[0] + 45) == "idle"
    host.activity_at = clock[0] + 260
    assert host.session_limit(clock[0] + 270) == "warning"
    host.warned = True
    assert host.session_limit(clock[0] + 280) is None
    assert host.session_limit(clock[0] + 300) == "time_limit"


def test_no_warning_when_it_is_set_to_zero(svc, tmp_path):
    host, timing, clock = host_with(svc, tmp_path)
    timing.update({"warning_seconds": 0})
    host.session_timing = dict(timing.values)
    host.started = host.activity_at = clock[0]
    host.activity_at = clock[0] + 599
    assert host.session_limit(clock[0] + 599) is None
