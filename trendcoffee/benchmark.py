"""Concurrent local HTTP benchmark. No production traffic, paid calls or persisted test records."""

import json
import platform
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from .api import create_app
from .cli import bundle_path
from .service import Service


def run(requests=300, concurrency=8):
    requests = min(max(requests, 20), 10000)
    concurrency = min(max(concurrency, 1), 32)
    started = time.perf_counter()
    with tempfile.TemporaryDirectory() as directory:
        service = Service(Path(directory) / "benchmark.db")
        service.ingest(json.loads(bundle_path().read_text()))
        with TestClient(create_app(service=service, staff_token="benchmark-only")) as client:
            headers = [
                {"Authorization": "Bearer " + client.post("/api/sessions").json()["session_token"]}
                for _ in range(concurrency)
            ]
            cold_start = (time.perf_counter() - started) * 1000
            messages = ["Xin chào", "địa chỉ", "thanh toán QR", "thực đơn", "đơn của tôi"]
            for message in messages:
                client.post("/api/chat", headers=headers[0], json={"message": message})

            def one(index):
                before = time.perf_counter()
                response = client.post(
                    "/api/chat",
                    headers=headers[index % concurrency],
                    json={"message": messages[index % len(messages)]},
                )
                return ((time.perf_counter() - before) * 1000, response.status_code == 200)

            batch = time.perf_counter()
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                results = list(pool.map(one, range(requests)))
            duration = time.perf_counter() - batch
            retrieval = []
            for _ in range(50):
                before = time.perf_counter()
                assert (
                    client.get("/api/knowledge", params={"q": "thanh toán QR"}).status_code == 200
                )
                retrieval.append((time.perf_counter() - before) * 1000)
    values = sorted(item[0] for item in results)

    def pct(values, p):
        values = sorted(values)
        return round(values[min(int((len(values) - 1) * p), len(values) - 1)], 3)

    p95 = pct(values, 0.95)
    errors = sum(not good for _, good in results)
    return {
        "requests": requests,
        "concurrency": concurrency,
        "errors": errors,
        "transport": "in_process_http",
        "scope": "local HTTP routing/SQLite; excludes browser network, remote model and POS",
        "p50_ms": pct(values, 0.5),
        "p95_ms": p95,
        "p99_ms": pct(values, 0.99),
        "retrieval_requests": 50,
        "retrieval_p95_ms": pct(retrieval, 0.95),
        "cold_start_ms": round(cold_start, 3),
        "requests_per_second": round(requests / duration, 1),
        "local_p95_target_ms": 250,
        "target_met": p95 < 250 and errors == 0,
        "python": platform.python_version(),
        "platform": platform.system(),
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
