"""Frontend <-> backend integration: drives the real WeatherGPT.dc.html in headless
Chromium against a real /ask service (fixtures mode: deterministic, offline).

    /home/masasa23/codsoft/.venv/bin/pytest prototype/frontend/test_integration.py -v

Requires: pytest-playwright + `playwright install chromium`.
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

HERE = Path(__file__).resolve().parent
ASK_DIR = HERE.parent / "ask_service"
PY = sys.executable


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
    env = {**os.environ, "WEATHER_MODE": "fixtures", "GEMINI_API_KEY": ""}
    proc = subprocess.Popen(
        [PY, "-m", "uvicorn", "main:app", "--port", str(port), "--log-level", "warning"],
        cwd=ASK_DIR, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    _wait(f"http://127.0.0.1:{port}/health")
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
        cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
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
    # The canvas prop default is http://localhost:8001; rewrite those requests to
    # the ephemeral backend port at the network layer (no DOM hacking needed).
    target = f"http://127.0.0.1:{backend['port']}"
    page.route(
        "http://localhost:8001/**",
        lambda route: route.continue_(
            url=route.request.url.replace("http://localhost:8001", target, 1)
        ),
    )
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


def test_backend_down_shows_error_card(app, backend):
    backend["proc"].terminate()
    backend["proc"].wait(timeout=5)
    try:
        app.get_by_role("button", name="Madurai today").click()
        app.get_by_test_id("error-card").first.wait_for(timeout=20000)
        assert app.get_by_test_id("error-card").first.is_visible()
    finally:
        backend["proc"] = backend["respawn"]()
