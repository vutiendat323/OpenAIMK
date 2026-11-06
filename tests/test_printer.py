"""CUPS command/IPP/raster contract tests; never contact a printer."""

import shutil
import struct
import subprocess
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


def fake_raster(header_ink=b"\xf0", fail_header=False):
    """pdftoppm writes one 8x2 page; magick writes the 8x2 card header (or fails)."""
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        if args[0] == "magick":
            if fail_header:
                raise subprocess.CalledProcessError(1, args)
            Path(args[-1].removeprefix("pbm:")).write_bytes(b"P4\n8 2\n" + header_ink + b"\x00")
        else:
            assert args[0] == "pdftoppm"
            Path(f"{args[-1]}-1.pbm").write_bytes(b"P4\n8 2\n\xff\x00")

    return run, calls


def test_a_carded_invoice_starts_with_the_card_as_a_raster_header(tmp_path):
    """2026-11-06: the header names the pickup card, in Vietnamese with diacritics."""
    run, calls = fake_raster()
    result = CupsPrinter("GP-C180I", width_dots=8, run=run).prepare(
        tmp_path / "invoice.pdf", tmp_path, card=7
    )
    (magick,) = [args for args in calls if args[0] == "magick"]
    assert "label:THẺ RUNG SỐ 7" in magick
    assert magick[magick.index("-extent") + 1] == "8x"
    data = result.read_bytes()
    assert b"AI ORDER," not in data and b"QUY KHACH" not in data
    strip = b"\x1dv0\x00" + struct.pack("<HH", 1, 1)
    assert data.startswith(b"\x1b@" + strip + b"\xf0" + strip + b"\xff")


def test_a_failing_header_render_raises_instead_of_printing_without_the_card(tmp_path):
    run, _ = fake_raster(fail_header=True)
    with pytest.raises(subprocess.CalledProcessError):
        CupsPrinter("GP-C180I", width_dots=8, run=run).prepare(
            tmp_path / "invoice.pdf", tmp_path, card=7
        )


@pytest.mark.skipif(shutil.which("magick") is None, reason="ImageMagick not installed")
def test_the_real_header_render_fits_the_paper(tmp_path):
    def run(args, **kwargs):
        if args[0] == "pdftoppm":
            Path(f"{args[-1]}-1.pbm").write_bytes(b"P4\n576 1\n" + b"\xff" * 72)
            return None
        return subprocess.run(args, **kwargs)

    printer = CupsPrinter("GP-C180I", run=run)
    printer.prepare(tmp_path / "invoice.pdf", tmp_path, card=16)
    header = (tmp_path / "header.pbm").read_bytes()
    assert header.startswith(b"P4\n576 ")
    assert any(header.split(b"\n", 2)[2])  # the card text left ink
