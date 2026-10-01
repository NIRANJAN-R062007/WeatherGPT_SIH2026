"""Scrub secrets and personal data out of every log record (plan.md §8
Phase 8, SEC-N8; risk R16).

`install()` wraps the global LogRecord factory, so it covers every logger in
the process — this app's, httpx's, and uvicorn's access log, which writes
each request line with its query string (the IVR's `?key=<webhook secret>`,
`/alerts/subscriptions?target=<webhook URL or FCM token>`). Records are
cleaned when they are created, before any handler or formatter sees them:

- `Authorization: Bearer <token>`, bare JWTs, and the values of sensitive
  query parameters (key, token, secret, target, ...) become [redacted];
- full URLs shrink to scheme://host — webhook and recording URLs often carry
  a secret in the path or query (Slack/Discord webhooks, signed S3 links),
  and a connection URL its password;
- `lat`/`lon` query values are rounded to 2 decimals (~1 km);
- phone numbers (+CC..., or a bare 10-digit Indian mobile) keep only their
  last two digits.

Exception tracebacks get the same pass (httpx puts the full request URL in its
error text). Byte-identical copies live in `services/orchestrator/` and
`services/gateway/`; `tests/test_log_redaction.py` fails if they drift.
"""

import logging
import re
import traceback

_REDACTED = "[redacted]"

_BEARER = re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]+")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*")
# scheme://[user:pass@]host[/path?query] -> scheme://host: the userinfo goes
# too (a DATABASE_URL in a driver error would otherwise keep its password).
_URL = re.compile(r"\b([a-z][a-z0-9+.-]*://)(?:[^/\s?#@'\"<>)]*@)?([^/\s?#'\"<>)]+)[^\s'\"<>)]*", re.I)
_SECRET_PARAM = re.compile(
    r"(?i)([?&;](?:key|api_?key|token|access_token|refresh_token|manage_token|secret"
    r"|password|signature|sig|target|recordingurl|from|to|phone|callfrom|callto)=)[^&#\s\"']*"
)
_COORD_PARAM = re.compile(r"(?i)([?&;](?:lat|lon|lng|latitude|longitude)=)(-?\d+(?:\.\d+)?)")
_PHONE = re.compile(r"(?<![\w.+-])(?:\+\d{1,3}[\s-]?\d[\d\s-]{6,12}\d|(?:91)?[6-9]\d{9})(?![\w.])")


def _mask_phone(match: re.Match) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    return f"[phone …{digits[-2:]}]"


def redact(text: str) -> str:
    """The scrub, on one string. Order matters: query values before URLs,
    since shrinking a URL drops its query string anyway, and a request line
    (uvicorn's access log) has a path but no scheme."""
    text = _BEARER.sub(rf"\1 {_REDACTED}", text)
    text = _JWT.sub(_REDACTED, text)
    text = _SECRET_PARAM.sub(rf"\1{_REDACTED}", text)
    text = _COORD_PARAM.sub(lambda m: f"{m.group(1)}{round(float(m.group(2)), 2)}", text)
    text = _URL.sub(r"\1\2", text)
    return _PHONE.sub(_mask_phone, text)


def _clean(value):
    # Numbers stay numbers so %d keeps working; everything else (exceptions
    # included — their text is where URLs hide) is rendered and scrubbed.
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redact(str(value))


def _scrub(record: logging.LogRecord) -> logging.LogRecord:
    if isinstance(record.msg, str):
        record.msg = redact(record.msg)
    if isinstance(record.args, tuple):
        record.args = tuple(_clean(a) for a in record.args)
    elif isinstance(record.args, dict):
        record.args = {k: _clean(v) for k, v in record.args.items()}
    if record.exc_info and record.exc_info[1] is not None:
        # Pre-render the traceback: formatters reuse exc_text when it's set.
        record.exc_text = redact("".join(traceback.format_exception(*record.exc_info)).rstrip())
    return record


_installed = False


def install() -> None:
    """Idempotent: wraps the current factory once per process."""
    global _installed
    if _installed:
        return
    previous = logging.getLogRecordFactory()

    def factory(*args, **kwargs):
        return _scrub(previous(*args, **kwargs))

    logging.setLogRecordFactory(factory)
    _installed = True
