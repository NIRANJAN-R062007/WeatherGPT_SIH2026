"""web/ <-> backend integration: drives the real Phase 3 pages in headless Chromium
against a real orchestrator (fixtures mode, warning fixtures on: deterministic, offline).

    pytest web/tests_e2e_web.py -v

Requires: pytest-playwright + `playwright install chromium`. Modelled on
prototype/tests_e2e_frontend.py; here the pages take the backend via `?apiBase=`
(both origins are http), so no request rewriting is needed.
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import unquote

import httpx
import pytest

HERE = Path(__file__).resolve().parent
ASK_DIR = HERE.parent / "services" / "orchestrator"
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
    env = {**os.environ, "WEATHER_MODE": "fixtures", "GEMINI_API_KEY": "", "WARNINGS_ENABLED": "1"}
    proc = subprocess.Popen(
        [PY, "-m", "uvicorn", "main:app", "--port", str(port), "--log-level", "warning"],
        cwd=ASK_DIR, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    _wait(f"http://127.0.0.1:{port}/livez")  # not /health: it probes Ollama and is slow
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
    _wait(f"http://127.0.0.1:{port}/index.html")
    yield f"http://127.0.0.1:{port}"
    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture
def app(page, backend, frontend):
    """A page factory: open(name) loads web/<name> pointed at the spawned backend."""
    errors = []
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("console", lambda m: errors.append(f"console: {m.text}") if m.type == "error" else None)
    api = f"http://127.0.0.1:{backend['port']}"

    def open_page(name: str, lang: str = "en"):
        page.goto(f"{frontend}/{name}?apiBase={api}&lang={lang}", wait_until="networkidle")
        page.wait_for_timeout(500)
        return page

    page.open = open_page
    page.errors = errors
    page.api = api
    return page


def _ask(page, text: str):
    page.locator("#q").fill(text)
    page.keyboard.press("Enter")
    page.get_by_test_id("answer").first.wait_for(timeout=15000)
    return page.get_by_test_id("answer").first.inner_text()


def test_ask_page_loads_with_empty_state(app):
    app.open("index.html")
    assert app.get_by_test_id("empty").is_visible()
    assert app.locator("#city option").count() == 3  # from GET /cities
    assert not app.errors, app.errors


def test_ask_shows_provenance_evidence_and_validator(app):
    app.open("index.html")
    text = _ask(app, "What's the weather in Chennai?")
    assert text.startswith("Chennai:") and "feels like 32.5" in text and "81%" in text
    assert app.get_by_test_id("live-badge").first.inner_text().strip() in ("snapshot", "live")
    assert "issued" in app.get_by_test_id("data-note").first.inner_text().lower() or \
        "Issued" in app.locator(".receipt").first.inner_text()
    assert "4/4" in app.get_by_test_id("validator").first.inner_text()
    app.get_by_test_id("view-source").first.click()
    app.get_by_test_id("figure-path").first.wait_for(timeout=5000)
    paths = [e.inner_text() for e in app.get_by_test_id("figure-path").all()]
    assert {"temp_c", "feels_like_c", "humidity_pct"} <= set(paths)
    assert not app.errors, app.errors


def test_ask_message_only_shape_has_no_evidence(app):
    app.open("index.html")
    text = _ask(app, "weather in Mumbai")
    assert "Chennai, Madurai and Coimbatore" in text
    assert app.get_by_test_id("view-source").count() == 0
    assert app.get_by_test_id("validator").count() == 0


def test_ask_answers_in_hindi_with_devanagari_font(app):
    app.open("index.html", lang="hi")
    assert app.evaluate("document.documentElement.className") == "hi"
    text = _ask(app, "Will it rain in Madurai tomorrow?")
    assert text.startswith("मदुरै:") and "%" in text
    assert "3/3" in app.get_by_test_id("validator").first.inner_text()


def test_dashboard_shows_every_demo_city_with_imd_chips(app):
    app.open("dashboard.html")
    app.wait_for_function(
        "() => document.querySelectorAll('[data-testid=city-panel] [role=meter]').length === 3",
        timeout=15000,
    )
    board = app.get_by_test_id("dashboard").inner_text()
    for city in ("Chennai", "Madurai", "Coimbatore"):
        assert city in board
    temps = [e.inner_text().strip() for e in app.get_by_test_id("hero-temp").all()]
    assert temps == ["28", "27", "24.6"]  # fixture snapshots, not mocks
    assert "tomorrow" in board.lower() and "Chance of rain today" in board
    chips = app.locator("[data-testid=imd-chip] .imd")
    assert chips.count() == 3
    colours = {c.get_attribute("data-colour") for c in chips.all()}
    assert colours == {"orange", "yellow", "green"}
    for c in chips.all():  # icon + label + colour, never colour alone
        assert c.locator("svg").count() == 1 and c.inner_text().strip()
    assert not app.errors, app.errors


def test_dashboard_unit_toggle_converts_display_only(app):
    app.open("settings.html")
    app.locator("#unit-f").check()
    app.open("dashboard.html")
    app.wait_for_function(
        "() => document.querySelectorAll('[data-testid=hero-temp]').length === 3", timeout=15000)
    assert app.get_by_test_id("hero-temp").first.inner_text().strip() == "82.4"  # 28 °C
    app.open("settings.html")
    app.locator("#unit-c").check()


def test_warnings_bands_sorted_by_severity_with_validity_window(app):
    app.open("warnings.html")
    bands = app.get_by_test_id("warning-band")
    app.wait_for_function(
        "() => document.querySelectorAll('[data-testid=warning-band]').length === 3", timeout=15000)
    assert [b.get_attribute("data-colour") for b in bands.all()] == ["orange", "yellow", "green"]
    first = bands.first
    assert "heavy rainfall" in first.get_by_test_id("headline").inner_text().lower()
    assert "IST" in first.get_by_test_id("validity").inner_text()
    assert first.locator("svg").count() >= 1 and first.get_by_test_id("code-name").inner_text()
    assert "fixture" in first.inner_text().lower()  # honest label: not a live IMD feed
    assert not app.errors, app.errors


def test_warnings_empty_state_when_nothing_in_force(app):
    app.route(f"{app.api}/warnings?city=coimbatore*", lambda route: route.fulfill(
        status=200, content_type="application/json",
        body='{"city":"coimbatore","city_name":"Coimbatore","warning":null}'))
    app.open("warnings.html")
    app.wait_for_function(
        "() => document.querySelectorAll('[data-testid=warning-band]').length === 3", timeout=15000)
    last = app.get_by_test_id("warning-band").last
    assert last.get_attribute("data-colour") == "none"
    assert "No warning in force" in last.inner_text()
    app.unroute(f"{app.api}/warnings?city=coimbatore*")


def test_language_choice_is_shared_across_pages(app, frontend):
    app.open("settings.html")
    app.locator("input[name=lang][value=te]").check()
    assert app.evaluate("document.documentElement.className") == "te"
    # no ?lang= this time: the stored preference must win
    app.goto(f"{frontend}/dashboard.html?apiBase={app.api}", wait_until="networkidle")
    app.wait_for_function(
        "() => document.querySelectorAll('[data-testid=city-panel]').length === 3", timeout=15000)
    assert app.evaluate("document.documentElement.lang") == "te"
    assert "చెన్నై" in app.get_by_test_id("dashboard").inner_text()
    app.open("settings.html", lang="en")


def test_nav_links_carry_api_base_override(app):
    app.open("index.html")
    hrefs = [unquote(a.get_attribute("href")) for a in app.locator(".shell nav a").all()]
    assert len(hrefs) == 4 and all(f"apiBase={app.api}" in h for h in hrefs)
    assert app.locator(".shell nav a[aria-current=page]").inner_text() == "Ask"


def test_backend_down_shows_error_cards(app, backend):
    backend["proc"].terminate()
    backend["proc"].wait(timeout=5)
    try:
        app.open("index.html")
        app.locator("#q").fill("Madurai today")
        app.keyboard.press("Enter")
        app.get_by_test_id("error-card").first.wait_for(timeout=20000)
        assert app.get_by_role("button", name="Try again").is_visible()
        app.open("dashboard.html")
        app.get_by_test_id("error-card").first.wait_for(timeout=20000)
    finally:
        backend["proc"] = backend["respawn"]()
