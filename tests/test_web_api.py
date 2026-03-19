import importlib
import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient


WORKTREE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKTREE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKTREE_ROOT))


def make_client(monkeypatch, tmp_path, subprocess_run=None):
    monkeypatch.setenv("KIS_DASHBOARD_ADMIN_PASSWORD", "secret-password")
    monkeypatch.setenv("KIS_DASHBOARD_SESSION_SECRET", "session-secret")
    monkeypatch.setenv("KIS_DASHBOARD_ROOT", str(tmp_path))
    monkeypatch.setenv("KIS_DASHBOARD_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("KIS_DASHBOARD_ARTIFACT_DIR", str(tmp_path / "tmp" / "artifacts"))

    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "watchlist.kr.json").write_text(
        json.dumps(
            [
                {"type": "stock", "name": "Samsung Elec.", "code": "005930", "market": "005930"},
            ],
            ensure_ascii=False,
        )
    )
    (config_dir / "watchlist.us.json").write_text(
        json.dumps(
            [
                {"type": "stock", "name": "Apple", "code": "AAPL", "market": "NASDAQ", "excd": "NAS"},
            ],
            ensure_ascii=False,
        )
    )

    module = importlib.import_module("web_api.main")
    importlib.reload(module)
    app = module.create_app()

    if subprocess_run is not None:
        monkeypatch.setattr(module.subprocess, "run", subprocess_run)

    return TestClient(app)


def login(client: TestClient):
    response = client.post("/api/login", json={"password": "secret-password"})
    assert response.status_code == 200
    return response


def test_login_sets_session_and_session_endpoint_reports_authenticated(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)

    response = client.post("/api/login", json={"password": "wrong"})
    assert response.status_code == 401

    login(client)

    session = client.get("/api/session")
    assert session.status_code == 200
    assert session.json()["authenticated"] is True
    assert session.json()["user"] == "admin"


def test_logout_clears_session(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    login(client)

    response = client.post("/api/logout")
    assert response.status_code == 200

    session = client.get("/api/session")
    assert session.json()["authenticated"] is False


def test_watchlist_crud_uses_market_specific_files(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    login(client)

    current = client.get("/api/watchlist", params={"market": "kr"})
    assert current.status_code == 200
    assert current.json()["market"] == "kr"
    assert current.json()["items"][0]["code"] == "005930"

    created = client.post(
        "/api/watchlist",
        json={"market": "kr", "code": "000660", "name": "SK Hynix"},
    )
    assert created.status_code == 201
    assert created.json()["code"] == "000660"

    kr_watchlist = json.loads((tmp_path / "config" / "watchlist.kr.json").read_text())
    assert [item["code"] for item in kr_watchlist] == ["005930", "000660"]

    deleted = client.delete("/api/watchlist/000660", params={"market": "kr"})
    assert deleted.status_code == 200
    assert deleted.json()["removed"] is True

    kr_watchlist = json.loads((tmp_path / "config" / "watchlist.kr.json").read_text())
    assert [item["code"] for item in kr_watchlist] == ["005930"]


def test_generate_creates_artifact_and_calls_cli(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, check, env=None, cwd=None):
        calls.append({"cmd": cmd, "env": env, "cwd": cwd})
        out_dir = Path(env["KIS_DASHBOARD_OUT_DIR"])
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "kis_market_dashboard.us.json").write_text(json.dumps({"market": "us"}))
        (out_dir / "kis_market_dashboard.us.png").write_bytes(b"fake-png")
        return None

    client = make_client(monkeypatch, tmp_path, subprocess_run=fake_run)
    login(client)

    response = client.post("/api/generate", json={"market": "us"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["market"] == "us"
    assert payload["artifact_id"]
    assert payload["image"]["path"].endswith(".png")
    assert payload["json"]["path"].endswith(".json")
    assert len(calls) == 1
    assert calls[0]["cmd"][:4] == ["uv", "run", "python", "kis_market_dashboard.py"]
    assert calls[0]["cmd"][4:8] == ["generate", "--market", "us", "--out-dir"]
    assert calls[0]["cmd"][8] == calls[0]["env"]["KIS_DASHBOARD_OUT_DIR"]


def test_artifact_download_returns_image_bytes(monkeypatch, tmp_path):
    def fake_run(cmd, check, env=None, cwd=None):
        out_dir = Path(env["KIS_DASHBOARD_OUT_DIR"])
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "kis_market_dashboard.kr.json").write_text(json.dumps({"market": "kr"}))
        (out_dir / "kis_market_dashboard.kr.png").write_bytes(b"png-bytes")
        return None

    client = make_client(monkeypatch, tmp_path, subprocess_run=fake_run)
    login(client)

    generated = client.post("/api/generate", json={"market": "kr"})
    artifact_id = generated.json()["artifact_id"]

    download = client.get(f"/api/artifacts/{artifact_id}/download")
    assert download.status_code == 200
    assert download.content == b"png-bytes"
    assert download.headers["content-type"].startswith("image/png")
