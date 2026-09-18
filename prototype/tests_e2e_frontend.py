"""Frontend <-> backend integration: drives the real WeatherGPT.dc.html in headless
Chromium against a real /ask service (fixtures mode: deterministic, offline).

    pytest prototype/tests_e2e_frontend.py -v

Requires: pytest-playwright + `playwright install chromium`.
"""

import html as html_lib
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

HERE = Path(__file__).resolve().parent
ASK_DIR = HERE.parent / "services" / "orchestrator"
FRONTEND_DIR = HERE / "frontend"  # lives outside the served folder on purpose
PY = sys.executable
_PAGE = (FRONTEND_DIR / "WeatherGPT.dc.html").read_text("utf-8")
_PROPS = json.loads(html_lib.unescape(re.search(r'data-props="([^"]*)"', _PAGE).group(1)))
API_BASE = _PROPS["apiBase"]["default"].rstrip("/")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait(url: str, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=1.0).status_code < 500:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    raise RuntimeError(f"{url} did not come up")


def _spawn_backend(port: int) -> subprocess.Popen:
    env = {**os.environ, "WEATHER_MODE": "fixtures", "GEMINI_API_KEY": "", "WARNINGS_ENABLED": "1"}
    proc = subprocess.Popen(
        [PY, "-m", "uvicorn", "main:app", "--port", str(port), "--log-level", "warning"],
        cwd=ASK_DIR, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    # /livez, not /health: /health probes Ollama and can exceed _wait's per-request timeout
    _wait(f"http://127.0.0.1:{port}/livez")
    return proc


@pytest.fixture(scope="module")
def backend():
    port = _free_port()
    proc = _spawn_backend(port)
    yield {"port": port, "proc": proc, "respawn": lambda: _spawn_backend(port)}
    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture(scope="module")
def frontend():
    port = _free_port()
    proc = subprocess.Popen(
        [PY, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
        cwd=FRONTEND_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    _wait(f"http://127.0.0.1:{port}/WeatherGPT.dc.html")
    yield f"http://127.0.0.1:{port}/WeatherGPT.dc.html"
    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture
def app(page, backend, frontend):
    """A loaded page whose apiBase points at the spawned backend."""
    errors = []
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("console", lambda m: errors.append(f"console: {m.text}") if m.type == "error" else None)
    # Rewrite requests aimed at the canvas prop's default apiBase to the
    # ephemeral backend port at the network layer (no DOM hacking needed).
    target = f"http://127.0.0.1:{backend['port']}"

    def proxy(route):
        # fetch+fulfill rather than continue_: the default apiBase is https and
        # Playwright refuses to continue_ a request onto a different protocol.
        try:
            resp = route.fetch(url=route.request.url.replace(API_BASE, target, 1))
        except Exception:  # backend down -> surface as a network failure
            route.abort("connectionrefused")
            return
        route.fulfill(response=resp)

    page.route(f"{API_BASE}/**", proxy)
    page.goto(frontend, wait_until="networkidle")
    page.wait_for_timeout(1500)
    page.errors = errors
    return page


def _answers(page):
    return page.get_by_test_id("answer")


def test_page_loads_without_errors(app):
    assert app.get_by_role("button", name="What's the weather in Chennai?").is_visible()
    assert not app.errors, app.errors


def test_hero_card_is_backend_data(app):
    # fixture snapshot says 28; the old mock said 32
    assert app.get_by_test_id("hero-temp").inner_text().strip() == "28"


def test_chip_renders_backend_answer_and_figure_paths(app):
    app.get_by_role("button", name="What's the weather in Chennai?").click()
    _answers(app).first.wait_for(timeout=15000)
    text = _answers(app).first.inner_text()
    assert text.startswith("Chennai:") and "feels like 32.5" in text and "81%" in text
    assert app.get_by_test_id("live-badge").first.inner_text().strip() in ("snapshot", "live")
    app.get_by_test_id("view-source").first.click()
    app.get_by_test_id("figure-path").first.wait_for(timeout=5000)
    paths = [e.inner_text() for e in app.get_by_test_id("figure-path").all()]
    assert {"temp_c", "feels_like_c", "humidity_pct"} <= set(paths)
    assert "issued" in app.get_by_test_id("data-note").first.inner_text()
    assert not app.errors, app.errors


def test_tamil_chip_renders_tamil_answer(app):
    app.get_by_role("button", name="தமிழ்").click()
    app.get_by_role("button", name="கோயம்புத்தூரில் நாளை மழை?").click()
    _answers(app).first.wait_for(timeout=15000)
    text = _answers(app).first.inner_text()
    assert text.startswith("கோயம்புத்தூர்:") and "50%" in text
    assert "unrecognized" not in text.lower()
    # hero follows the city the answer resolved to
    assert app.get_by_test_id("hero-temp").inner_text().strip() == "24.6"


def test_backend_message_renders_without_source_panel(app):
    app.get_by_placeholder("Ask WeatherGPT about any place...").fill("weather in Mumbai")
    app.keyboard.press("Enter")
    _answers(app).first.wait_for(timeout=15000)
    assert "Chennai, Madurai and Coimbatore" in _answers(app).first.inner_text()
    assert app.get_by_test_id("view-source").count() == 0


def test_dashboard_shows_every_demo_city(app):
    app.get_by_role("button", name="Dashboard").click()
    cards = app.get_by_test_id("dash-card")
    cards.first.wait_for(timeout=5000)
    assert cards.count() == 3
    app.wait_for_function(
        "() => document.querySelectorAll('[data-testid=dash-card] [role=meter]').length === 3",
        timeout=15000,
    )
    text = app.get_by_test_id("dashboard").inner_text()
    for city in ("Chennai", "Madurai", "Coimbatore"):
        assert city in text
    assert "28" in text and "81%" in text  # Chennai fixture snapshot
    assert "Tomorrow" in text
    chips = [c.inner_text() for c in app.get_by_test_id("dash-warning").all()]
    assert len(chips) == 3 and any("alert" in c.lower() for c in chips)  # fixture colour codes
    assert not app.errors, app.errors


def test_dashboard_ask_button_returns_home_with_city(app):
    app.get_by_role("button", name="Dashboard").click()
    app.get_by_test_id("dash-card").nth(2).get_by_role("button", name="Ask").click()
    app.get_by_test_id("hero-temp").wait_for(timeout=5000)
    app.wait_for_function(
        "() => document.querySelector('[data-testid=hero-temp]').innerText.trim() === '24.6'",
        timeout=15000,
    )
    assert not app.errors, app.errors


def test_backend_down_shows_error_card(app, backend):
    backend["proc"].terminate()
    backend["proc"].wait(timeout=5)
    try:
        app.get_by_role("button", name="Madurai today").click()
        app.get_by_test_id("error-card").first.wait_for(timeout=20000)
        assert app.get_by_test_id("error-card").first.is_visible()
    finally:
        backend["proc"] = backend["respawn"]()
