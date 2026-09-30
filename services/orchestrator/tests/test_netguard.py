"""SSRF guard for alert webhooks. DNS is mocked; no real network."""

import alert_engine
import config
import httpx
import netguard
import pytest


def _dns(monkeypatch, mapping):
    def _resolve(host, port):
        if host not in mapping:
            import socket
            raise socket.gaierror("nx")
        return mapping[host]

    monkeypatch.setattr(netguard, "_resolve", _resolve)


@pytest.fixture(autouse=True)
def _strict(monkeypatch):
    monkeypatch.setattr(config, "ALERT_WEBHOOK_ALLOW_PRIVATE", False)


def test_public_host_ok(monkeypatch):
    _dns(monkeypatch, {"hooks.example.com": ["93.184.216.34"]})
    url = "https://hooks.example.com/x?y=1"
    assert netguard.validate_public_https_url(url) == url


@pytest.mark.parametrize("ip", [
    "127.0.0.1", "10.0.0.5", "172.16.3.4", "192.168.1.1", "169.254.169.254",
    "224.0.0.1", "0.0.0.0", "240.0.0.1", "100.64.0.1",
    "::1", "fe80::1", "fc00::1", "ff02::1", "::", "::ffff:127.0.0.1",
    "::ffff:169.254.169.254",
])
def test_non_public_resolution_rejected(monkeypatch, ip):
    _dns(monkeypatch, {"evil.example.com": [ip]})
    with pytest.raises(netguard.UnsafeURLError):
        netguard.validate_public_https_url("https://evil.example.com/")


def test_mixed_resolution_rejected(monkeypatch):
    _dns(monkeypatch, {"m.example.com": ["93.184.216.34", "127.0.0.1"]})
    with pytest.raises(netguard.UnsafeURLError):
        netguard.validate_public_https_url("https://m.example.com/")


@pytest.mark.parametrize("url", [
    "https://127.0.0.1/", "https://[::1]/", "https://169.254.169.254/latest",
    "https://[::ffff:10.0.0.1]/",
    "http://hooks.example.com/",
    "ftp://hooks.example.com/",
    "https://user:pw@hooks.example.com/",
    "https://user@hooks.example.com/",
    "https:///nohost",
    "https://nx.example.com/",
    "https://hooks.example.com/" + "a" * 2100,
    "",
])
def test_bad_urls_rejected(monkeypatch, url):
    _dns(monkeypatch, {"hooks.example.com": ["93.184.216.34"]})
    with pytest.raises(netguard.UnsafeURLError):
        netguard.validate_public_https_url(url)


def test_allow_private_permits_loopback_http():
    url = "http://127.0.0.1:8000/hook"
    assert netguard.validate_public_https_url(url, allow_private=True) == url
    with pytest.raises(netguard.UnsafeURLError):
        netguard.validate_public_https_url("http://u:p@127.0.0.1/", allow_private=True)


def test_subscribe_rejects_private_webhook():
    with pytest.raises(alert_engine.SubscriptionError):
        alert_engine.subscribe(
            channel="webhook", target="https://169.254.169.254/x", city_key="chennai",
        )


def test_dispatch_revalidates_and_does_not_post(monkeypatch):
    # Host was public at subscribe time, rebinds to loopback afterwards.
    _dns(monkeypatch, {"rebind.example.com": ["127.0.0.1"]})
    called = []
    monkeypatch.setattr(httpx, "post", lambda *a, **k: called.append(1))
    assert alert_engine._dispatch_webhook("https://rebind.example.com/h", {}) is False
    assert called == []


def test_dispatch_no_redirects_short_timeout(monkeypatch):
    _dns(monkeypatch, {"hooks.example.com": ["93.184.216.34"]})
    seen = {}

    class _R:
        def raise_for_status(self):
            pass

    def _post(url, **kw):
        seen.update(kw)
        return _R()

    monkeypatch.setattr(httpx, "post", _post)
    assert alert_engine._dispatch_webhook("https://hooks.example.com/h", {"a": 1}) is True
    assert seen["follow_redirects"] is False
    assert seen["timeout"] <= 10


def test_logs_do_not_leak_url_or_token(monkeypatch, caplog):
    _dns(monkeypatch, {"hooks.example.com": ["93.184.216.34"]})

    def _post(url, **kw):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(httpx, "post", _post)
    with caplog.at_level("WARNING"):
        alert_engine._dispatch_webhook("https://hooks.example.com/secret-path-token", {})
        alert_engine._dispatch_fcm("SECRET-FCM-TOKEN-123", {})
    assert "secret-path-token" not in caplog.text
    assert "SECRET-FCM-TOKEN-123" not in caplog.text
    assert "hooks.example.com" in caplog.text
