"""SEC-N8 (plan.md §8 Phase 8; R16): no token, webhook/recording URL, phone
number or precise coordinate reaches a log line. main.py installs the scrub
at import, so every record created here already went through it.
"""

import logging
from pathlib import Path

import httpx
import log_redaction
import main  # noqa: F401 — installs the record factory
import pytest

REPO = Path(__file__).resolve().parents[3]
_LOG = logging.getLogger("weathergpt.test_redaction")


def test_gateway_copy_is_identical():
    ours = (REPO / "services/orchestrator/log_redaction.py").read_text()
    assert (REPO / "services/gateway/log_redaction.py").read_text() == ours


@pytest.mark.parametrize("raw,kept,gone", [
    ("POST /ivr/recording?key=s3cr3t&lang=ta HTTP/1.1", "?key=[redacted]&lang=ta", "s3cr3t"),
    ("GET /alerts/subscriptions?target=https%3A%2F%2Fhooks.example%2Fabc",
     "target=[redacted]", "hooks"),
    ("Authorization: Bearer eyJh.payload.sig", "Bearer [redacted]", "payload"),
    ("jwt eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NSJ9.c2ln", "jwt [redacted]", "eyJzdWIi"),
    ("webhook https://discord.com/api/webhooks/123/SECRETTOKEN failed",
     "https://discord.com failed", "SECRETTOKEN"),
    ("fetch 'https://api.exotel.com/v1/Recordings/RE1.wav?sig=abc'",
     "'https://api.exotel.com'", "RE1"),
    ("postgresql://weathergpt:hunter2@db:5432/x refused",
     "postgresql://db:5432 refused", "hunter2"),
    ("caller +91 98765 43210", "[phone …10]", "98765"),
    ("caller 9876543210 again", "[phone …10] again", "9876543210"),
    ("GET /facts?lat=13.082712&lon=80.270718", "lat=13.08&lon=80.27", "082712"),
])
def test_redact(raw, kept, gone):
    out = log_redaction.redact(raw)
    assert kept in out and gone not in out


@pytest.mark.parametrize("benign", [
    "2026-10-01T12:00:00+05:30", "ts 1727771234", "weather_facts queue full (5000)",
    "live current_conditions for chennai failed", "UTC 2026-10-01",
])
def test_ordinary_text_is_left_alone(benign):
    assert log_redaction.redact(benign) == benign


def test_records_are_scrubbed_at_creation(caplog):
    with caplog.at_level(logging.WARNING, logger="weathergpt.test_redaction"):
        _LOG.warning("dispatch to %s failed (%d tries) for %s",
                     "https://hooks.slack.com/services/T0/B0/XYZ", 3, "+919876543210")
    msg = caplog.records[-1].getMessage()
    assert msg == "dispatch to https://hooks.slack.com failed (3 tries) for [phone …10]"


def test_exception_args_and_tracebacks_are_scrubbed(caplog):
    url = "https://example.com/v1/x?key=AIzaSECRET"
    exc = httpx.ConnectError(f"boom ({url})")
    with caplog.at_level(logging.WARNING, logger="weathergpt.test_redaction"):
        _LOG.warning("failed (%s)", exc)
        try:
            raise exc
        except httpx.ConnectError:
            _LOG.exception("failed hard")
    text = caplog.text
    assert "AIzaSECRET" not in text and "/v1/x" not in text
    assert "https://example.com" in text


def test_uvicorn_access_record_keeps_its_shape():
    # uvicorn's AccessFormatter unpacks record.args into five fields, the
    # last an int — the scrub must keep the tuple and the status code intact.
    record = logging.getLogger("uvicorn.access").makeRecord(
        "uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d',
        ("203.0.113.7:5555", "GET", "/ivr/menu.wav?key=s3cr3t", "1.1", 200), None)
    assert record.args == ("203.0.113.7:5555", "GET", "/ivr/menu.wav?key=[redacted]", "1.1", 200)


def test_install_is_idempotent():
    before = logging.getLogRecordFactory()
    log_redaction.install()
    assert logging.getLogRecordFactory() is before
