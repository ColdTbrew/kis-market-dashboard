from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import create_app


class FakeDashboardService:
    def build_dashboard(self, market: str, interval_minutes: int) -> dict[str, object]:
        return {
            "market": market,
            "title": f"{market.upper()} Market Dashboard",
            "subtitle": "Live dashboard payload",
            "generated_at": "2026-03-19T10:00:00",
            "interval_minutes": interval_minutes,
            "summary_cards": [
                {
                    "name": "KOSPI",
                    "market": "KOSPI",
                    "label": "",
                    "price": "2,700.00",
                    "diff": "+12.00",
                    "pct": "+0.45%",
                }
            ],
            "stock_cards": [
                {
                    "name": "Samsung Elec.",
                    "market": "005930",
                    "price": "209,500",
                    "diff": "+15,600",
                    "pct": "+8.0%",
                    "chart": {
                        "interval_minutes": interval_minutes,
                        "segments": [
                            {
                                "session": "KRX",
                                "color": "#f97316",
                                "points": [
                                    {
                                        "time": "09:00",
                                        "time_raw": "090000",
                                        "price": 209500,
                                        "open": 208000,
                                        "high": 210000,
                                        "low": 207500,
                                        "close": 209500,
                                        "volume": 1200000,
                                        "session": "KRX",
                                    }
                                ],
                            }
                        ],
                        "warnings": [],
                    },
                }
            ],
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
    csrf_token = login(client)

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
        "/api/watchlist/005930",
        params={"market": "kr"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["items"] == []


def test_dashboard_returns_live_payload(client: TestClient) -> None:
    login(client)
    response = client.get("/api/dashboard", params={"market": "kr", "interval_minutes": 15})
    assert response.status_code == 200
    payload = response.json()
    assert payload["market"] == "kr"
    assert payload["interval_minutes"] == 15
    assert payload["summary_cards"][0]["name"] == "KOSPI"
    assert payload["stock_cards"][0]["chart"]["interval_minutes"] == 15


def test_missing_csrf_is_rejected(client: TestClient) -> None:
    login(client)
    response = client.post(
        "/api/watchlist",
        json={"market": "kr", "code": "005930", "name": "Samsung Elec.", "market_label": "005930"},
    )
    assert response.status_code == 403


def test_index_serves_html(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "KIS Command Center" in response.text
