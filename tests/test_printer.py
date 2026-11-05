"""CUPS command/IPP/raster contract tests; never contact a printer."""

import struct
from pathlib import Path
from types import SimpleNamespace

import pytest

from trendcoffee.printer import CupsPrinter


def attributes(state="completed", reasons="job-completed-successfully", title="invoice"):
    return SimpleNamespace(
        stdout=(
            f"job-id (integer) = 12\njob-name (nameWithoutLanguage) = {title}\n"
            f"job-state (enum) = {state}\njob-printer-uri (uri) = ipp://localhost/printers/GP-C180I\n"
            f"job-state-reasons (keyword) = {reasons}\n"
        ).encode()
    )


@pytest.mark.parametrize(
    "state,reasons,expected",
    [
        ("completed", "job-completed-successfully", "completed"),
        ("completed", "job-completed-successfully,queued-in-device", "unknown"),
        ("completed", "job-completed-with-warnings", "failed"),
        ("completed", "none", "unknown"),
        ("processing", "none", "processing"),
        ("aborted", "job-completed-with-errors", "failed"),
    ],
)
def test_ipp_requires_positive_completion_evidence(state, reasons, expected):
    printer = CupsPrinter("GP-C180I", run=lambda *a, **k: attributes(state, reasons))
    assert printer.job_state("GP-C180I-12", "invoice") == expected


def test_job_identity_must_match_before_release():
    printer = CupsPrinter(
        "GP-C180I", run=lambda *a, **k: attributes("pending-held", title="other-job")
    )
    with pytest.raises(ValueError, match="identity_mismatch"):
        printer.verify_held("GP-C180I-12", "invoice")
    with pytest.raises(ValueError, match="identity_mismatch"):
        printer.job_state("other-12", "invoice")


def test_spools_one_held_copy_and_releases_the_same_job(tmp_path):
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        assert kwargs["timeout"] == 15 and kwargs["check"]
        return SimpleNamespace(stdout=b"request id is GP-C180I-12 (1 file(s))")

    printer = CupsPrinter("GP-C180I", run=run)
    job = printer.hold(tmp_path / "receipt.escpos", "invoice")
    printer.release(job)
    assert calls[0][0] == "lp" and "raw" in calls[0] and "hold" in calls[0]
    assert calls[0][calls[0].index("-n") + 1] == "1"
    assert calls[1] == ["lp", "-h", "localhost:631", "-i", "GP-C180I-12", "-H", "resume"]


def test_raster_preserves_every_page_and_trims_only_blank_tail(tmp_path):
    def run(args, **kwargs):
        assert args[0] == "pdftoppm"
        for page, ink in [(1, b"\xff"), (2, b"\x80")]:
            Path(f"{args[-1]}-{page}.pbm").write_bytes(b"P4\n8 2\n" + ink + b"\x00")

    result = CupsPrinter("GP-C180I", width_dots=8, run=run).prepare(
        tmp_path / "invoice.pdf", tmp_path
    )
    header = b"\x1dv0\x00" + struct.pack("<HH", 1, 1)
    data = result.read_bytes()
    prefix, raster = data.split(header, 1)
    notice = b"AI ORDER,QUY KHACH VUI LONG DOI 15 NHAN MON TAI QUAY NHE"
    assert notice in b" ".join(prefix.split())
    assert data.count(b"AI ORDER,") == 1  # one notice per receipt, including multi-page PDFs
    assert prefix.startswith(b"\x1b@")
    assert raster == b"\xff" + header + b"\x80\n\n\n\x1dV\x00"
