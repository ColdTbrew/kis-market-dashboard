from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import create_app


@pytest.fixture()
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "config").mkdir()
    (root / "tmp").mkdir()
    (root / "web_ui").mkdir()
    (root / "kis_market_dashboard.py").write_text("print('stub')")
    (root / "web_ui" / "index.html").write_text("<html><body>KIS Command Center</body></html>")
    (root / "web_ui" / "styles.css").write_text("body{}")
    (root / "web_ui" / "app.js").write_text("console.log('ok');")
    monkeypatch.setenv("KIS_WEB_DASHBOARD_PASSWORD", "secret")
    monkeypatch.setenv("KIS_WEB_DASHBOARD_SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("KIS_WEB_DASHBOARD_INSECURE_HTTP", "1")
    return root


@pytest.fixture()
def client(workspace: Path) -> TestClient:
    app = create_app(root_dir=workspace)
    return TestClient(app)


def login(client: TestClient) -> None:
    response = client.post("/api/login", json={"password": "secret"})
    assert response.status_code == 200
    assert response.json()["csrf_token"]


def test_login_and_session(client: TestClient) -> None:
    denied = client.get("/api/session")
    assert denied.status_code == 401

    response = client.post("/api/login", json={"password": "secret"})
    assert response.status_code == 200
    assert response.json()["authenticated"] is True
    assert response.json()["csrf_token"]

    session = client.get("/api/session")
    assert session.status_code == 200
    assert session.json()["authenticated"] is True
    assert session.json()["csrf_token"]


def test_watchlist_roundtrip(client: TestClient, workspace: Path) -> None:
    login_response = client.post("/api/login", json={"password": "secret"})
    csrf_token = login_response.json()["csrf_token"]

    add_response = client.post(
        "/api/watchlist",
        json={"market": "kr", "code": "005930", "name": "Samsung Elec.", "market_label": "005930"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert add_response.status_code == 200
    payload = add_response.json()
    assert payload["items"][0]["code"] == "005930"

    saved = json.loads((workspace / "config" / "watchlist.kr.json").read_text())
    assert saved[0]["name"] == "Samsung Elec."

    list_response = client.get("/api/watchlist", params={"market": "kr"})
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["code"] == "005930"

    delete_response = client.delete(
        "/api/watchlist/005930", params={"market": "kr"}, headers={"X-CSRF-Token": csrf_token}
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["items"] == []


def test_generate_creates_artifact_metadata(
    client: TestClient, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    login_response = client.post("/api/login", json={"password": "secret"})
    csrf_token = login_response.json()["csrf_token"]

    generated_json = {"market": "kr", "summary_cards": [], "stocks": []}

    def fake_run(command: list[str], cwd: Path, check: bool, capture_output: bool, text: bool):
        assert cwd == workspace
        assert command[:4] == ["uv", "run", "python", "kis_market_dashboard.py"]
        json_out = Path(command[command.index("--json-out") + 1])
        image_out = Path(command[command.index("--image-out") + 1])
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(generated_json))
        image_out.write_bytes(b"img")

        class Result:
            stdout = str(image_out)
            stderr = ""

        return Result()

    monkeypatch.setattr("app.main.subprocess.run", fake_run)

    response = client.post(
        "/api/generate",
        json={
            "market": "kr",
            "format": "webp",
            "interval_minutes": 15,
            "candle_width_scale": 0.8,
            "width_px": 1440,
            "render_scale": 2.5,
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["artifact"]["market"] == "kr"
    assert payload["artifact"]["format"] == "webp"
    artifact_dir = workspace / "tmp" / "web-artifacts" / payload["artifact"]["id"]
    assert (artifact_dir / "metadata.json").exists()
    assert (artifact_dir / "dashboard.json").exists()
    assert (artifact_dir / "dashboard.webp").exists()


def test_index_serves_html(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "KIS Command Center" in response.text


def test_missing_csrf_is_rejected(client: TestClient) -> None:
    login(client)
    response = client.post(
        "/api/watchlist",
        json={"market": "kr", "code": "005930", "name": "Samsung Elec.", "market_label": "005930"},
    )
    assert response.status_code == 403
