"""main.py's static-frontend mount is opt-in via FRONTEND_DIR: unset is
API-only, set serves that directory at `/` with the `/` -> /WeatherGPT.dc.html
redirect the gateway passes through (services/gateway/tests/test_proxy.py
plays the same 307). The app is built at import, so each case reloads config
and main the way test_config.py does, and restores both afterwards.
"""

import importlib

import config
import main
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_with(monkeypatch):
    def build(frontend_dir):
        if frontend_dir is None:
            monkeypatch.delenv("FRONTEND_DIR", raising=False)
        else:
            monkeypatch.setenv("FRONTEND_DIR", str(frontend_dir))
        importlib.reload(config)
        return importlib.reload(main).app

    yield build
    monkeypatch.undo()
    importlib.reload(config)
    importlib.reload(main)


def test_unset_is_api_only(app_with):
    client = TestClient(app_with(None))
    r = client.get("/")
    assert r.status_code == 200
    assert r.json() == {"service": "WeatherGPT Orchestrator", "health": "/health", "docs": "/docs"}
    assert client.get("/WeatherGPT.dc.html").status_code == 404
    assert client.get("/health").status_code == 200


def test_set_serves_the_directory_and_redirects_root(app_with, tmp_path):
    (tmp_path / "WeatherGPT.dc.html").write_text("<html>demo</html>")
    client = TestClient(app_with(tmp_path))
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/WeatherGPT.dc.html"
    r = client.get("/WeatherGPT.dc.html")
    assert r.status_code == 200
    assert r.text == "<html>demo</html>"
    assert client.get("/health").status_code == 200  # mounted last: API routes still win


def test_missing_directory_still_boots(app_with, tmp_path):
    # check_dir=False: an image without the directory must not crash at import.
    client = TestClient(app_with(tmp_path / "absent"))
    assert client.get("/", follow_redirects=False).status_code == 307
    assert client.get("/health").status_code == 200
