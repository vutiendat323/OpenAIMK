"""C (2026-11-06): kiosk_checkout took 2.9 s median and up to 10.5 s, spent in merchant calls
nobody had timed. Each checkout now logs how long every merchant step took. Fixtures only."""

import re

import httpx
from test_merchant import PNG, connect, place, remote_order


def test_a_checkout_logs_each_merchant_step(svc, caplog):
    def handler(request):
        if request.url.path.endswith("/payment/initiate/public"):
            return httpx.Response(200, json={"result": {}})
        remote = remote_order()
        if handler.initiated:
            remote["payment"]["qrCode"] = PNG
        else:
            remote["payment"].pop("qrCode")
        return httpx.Response(200, json={"result": remote})

    handler.initiated = False
    connect(svc, handler)
    original = svc.merchant.initiate

    def initiate(order):
        handler.initiated = True
        return original(order)

    svc.merchant.initiate = initiate
    with caplog.at_level("WARNING", logger="trendcoffee.service"):
        place(svc)
    (line,) = [r.getMessage() for r in caplog.records if "Merchant checkout" in r.getMessage()]
    assert re.search(r"took \d+\.\d s", line)
    for step in ("create", "initiate", "fetch", "payment"):
        assert re.search(step + r" \d+\.\d\d", line), (step, line)


def test_a_failed_checkout_still_logs_its_timing(svc, caplog):
    connect(svc, lambda request: httpx.Response(403, json={"message": "no"}))
    with caplog.at_level("WARNING", logger="trendcoffee.service"):
        _, _, order = place(svc)
    assert order["merchant"]["state"] == "rejected"
    (line,) = [r.getMessage() for r in caplog.records if "Merchant checkout" in r.getMessage()]
    assert "create" in line and "merchant_rejected" in line
