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
    return TestClient(create_app(root_dir=workspace))


def login(client: TestClient) -> str:
    response = client.post("/api/login", json={"password": "secret"})
    assert response.status_code == 200
    return response.json()["csrf_token"]


def test_login_and_session_contract(client: TestClient) -> None:
    assert client.get("/api/session").status_code == 401

    csrf_token = login(client)
    session = client.get("/api/session")
    assert session.status_code == 200
    assert session.json()["authenticated"] is True
    assert session.json()["csrf_token"] == csrf_token


def test_logout_requires_new_session(client: TestClient) -> None:
    login(client)
    response = client.post("/api/logout")
    assert response.status_code == 200
    assert response.json()["authenticated"] is False
    assert client.get("/api/session").status_code == 401


def test_watchlist_crud(client: TestClient, workspace: Path) -> None:
    csrf_token = login(client)

    created = client.post(
        "/api/watchlist",
        json={"market": "kr", "code": "000660", "name": "SK Hynix", "market_label": "000660"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert created.status_code == 200
    assert created.json()["items"][0]["code"] == "000660"

    current = client.get("/api/watchlist", params={"market": "kr"})
    assert current.status_code == 200
    assert current.json()["market"] == "kr"
    assert current.json()["items"][0]["code"] == "000660"

    deleted = client.delete(
        "/api/watchlist/000660", params={"market": "kr"}, headers={"X-CSRF-Token": csrf_token}
    )
    assert deleted.status_code == 200
    assert deleted.json()["items"] == []

    kr_watchlist = json.loads((workspace / "config" / "watchlist.kr.json").read_text())
    assert kr_watchlist == []


def test_generate_returns_artifact_and_dashboard_payload(
    client: TestClient, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf_token = login(client)
    generated_json = {"market": "us", "summary_cards": [], "stock_cards": []}

    def fake_run(command: list[str], cwd: Path, check: bool, capture_output: bool, text: bool):
        assert cwd == workspace
        json_out = Path(command[command.index("--json-out") + 1])
        image_out = Path(command[command.index("--image-out") + 1])
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(generated_json))
        image_out.write_bytes(b"fake-png")

        class Result:
            stdout = str(image_out)
            stderr = ""

        return Result()

    monkeypatch.setattr("app.main.subprocess.run", fake_run)

    response = client.post(
        "/api/generate",
        json={"market": "us"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 200
    artifact = response.json()["artifact"]
    assert artifact["market"] == "us"

    detail = client.get(f"/api/artifacts/{artifact['id']}")
    assert detail.status_code == 200
    assert detail.json()["dashboard"]["market"] == "us"


def test_artifact_download_returns_image_bytes(
    client: TestClient, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    csrf_token = login(client)

    def fake_run(command: list[str], cwd: Path, check: bool, capture_output: bool, text: bool):
        json_out = Path(command[command.index("--json-out") + 1])
        image_out = Path(command[command.index("--image-out") + 1])
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps({"market": "kr", "summary_cards": [], "stock_cards": []}))
        image_out.write_bytes(b"png-bytes")

        class Result:
            stdout = str(image_out)
            stderr = ""

        return Result()

    monkeypatch.setattr("app.main.subprocess.run", fake_run)

    generated = client.post(
        "/api/generate",
        json={"market": "kr"},
        headers={"X-CSRF-Token": csrf_token},
    )
    artifact_id = generated.json()["artifact"]["id"]

    download = client.get(f"/api/artifacts/{artifact_id}/download")
    assert download.status_code == 200
    assert download.content == b"png-bytes"
    assert download.headers["content-type"].startswith("image/png")
