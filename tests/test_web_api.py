import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


WORKTREE_ROOT = Path(__file__).resolve().parents[1]
WEB_API_ROOT = WORKTREE_ROOT / "web_api"
if str(WEB_API_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_API_ROOT))

from app.main import create_app


class FakeDashboardService:
    def build_dashboard(self, market: str, interval_minutes: int) -> dict[str, object]:
        return {
            "market": market,
            "title": f"{market.upper()} Market Dashboard",
            "subtitle": "Live dashboard payload",
            "generated_at": "2026-03-19T10:00:00",
            "interval_minutes": interval_minutes,
            "summary_cards": [],
            "stock_cards": [],
        }


@pytest.fixture()
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "config").mkdir()
    (root / "tmp").mkdir()
    (root / "web_ui").mkdir()
    (root / "web_ui" / "index.html").write_text("<html><body>KIS Command Center</body></html>")
    (root / "web_ui" / "styles.css").write_text("body{}")
    (root / "web_ui" / "app.js").write_text("console.log('ok');")
    monkeypatch.setenv("KIS_WEB_DASHBOARD_PASSWORD", "secret")
    monkeypatch.setenv("KIS_WEB_DASHBOARD_SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("KIS_WEB_DASHBOARD_INSECURE_HTTP", "1")
    return root


@pytest.fixture()
def client(workspace: Path) -> TestClient:
    return TestClient(create_app(root_dir=workspace, dashboard_service=FakeDashboardService()))


def login(client: TestClient) -> str:
    response = client.post("/api/login", json={"password": "secret"})
    assert response.status_code == 200
    return response.json()["csrf_token"]


def test_login_sets_session_and_session_endpoint_reports_authenticated(client: TestClient):
    response = client.post("/api/login", json={"password": "wrong"})
    assert response.status_code == 401

    csrf_token = login(client)
    session = client.get("/api/session")
    assert session.status_code == 200
    assert session.json()["authenticated"] is True
    assert session.json()["csrf_token"] == csrf_token


def test_logout_clears_session(client: TestClient):
    login(client)
    response = client.post("/api/logout")
    assert response.status_code == 200
    assert response.json()["authenticated"] is False
    assert client.get("/api/session").status_code == 401


def test_watchlist_crud_uses_market_specific_files(client: TestClient, workspace: Path):
    csrf_token = login(client)

    current = client.get("/api/watchlist", params={"market": "kr"})
    assert current.status_code == 200
    assert current.json()["market"] == "kr"
    assert current.json()["items"] == []

    created = client.post(
        "/api/watchlist",
        json={"market": "kr", "code": "000660", "name": "SK Hynix"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert created.status_code == 200
    assert created.json()["items"][0]["code"] == "000660"

    kr_watchlist = json.loads((workspace / "config" / "watchlist.kr.json").read_text())
    assert [item["code"] for item in kr_watchlist] == ["000660"]

    deleted = client.delete(
        "/api/watchlist/000660",
        params={"market": "kr"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert deleted.status_code == 200
    assert deleted.json()["items"] == []


def test_dashboard_returns_live_data(client: TestClient):
    login(client)
    response = client.get("/api/dashboard", params={"market": "us", "interval_minutes": 30})
    assert response.status_code == 200
    payload = response.json()
    assert payload["market"] == "us"
    assert payload["interval_minutes"] == 30


def test_dashboard_requires_auth(client: TestClient):
    response = client.get("/api/dashboard", params={"market": "kr"})
    assert response.status_code == 401
