import json
import subprocess
import sys
from uuid import uuid4

from fastapi.testclient import TestClient

from agenteval.api import create_app


def client(path):
    api = TestClient(create_app(path), base_url="http://127.0.0.1:8765")
    api.headers["X-CSRF-Token"] = api.get("/session").json()["csrf_token"]
    return api


def test_api_run_read_restart(tmp_path):
    path = tmp_path / "api.sqlite3"
    with client(path) as api:
        assert api.get("/health").json()["provider"] == "REPLAY / SIMULATED OUTPUT"
        assert len(api.get("/suite").json()["cases"]) == 36
        response = api.post("/runs")
        assert response.status_code == 201
        run = response.json()
        assert run["metrics"]["failed"] == 16
    with client(path) as api:
        assert api.get(f"/runs/{run['id']}").json() == run
        assert api.get("/runs").json() == {"run_ids": [run["id"]]}
        assert api.get(f"/runs/{uuid4()}").status_code == 404
        assert api.get("/runs/not-a-uuid").status_code == 422


def test_api_boundaries(tmp_path):
    with client(tmp_path / "api.sqlite3") as api:
        assert api.get("/health", headers={"Host": "evil.example"}).status_code == 400
        assert api.post("/runs", headers={"Origin": "https://evil.example"}).status_code == 403
        assert api.post("/runs", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
        assert api.post("/runs", json={"path": "../secret"}).status_code == 413
        assert api.get("/runs?limit=101").status_code == 422
        assert api.get("/runs?offset=-1").status_code == 422
        assert api.get("/runs").json() == {"run_ids": []}


def test_api_nonlocal_client_denied(tmp_path):
    with TestClient(
        create_app(tmp_path / "a.sqlite3"),
        base_url="http://127.0.0.1:8765",
        client=("192.0.2.1", 2000),
    ) as api:
        assert api.get("/health").status_code == 403


def test_cli_end_to_end(tmp_path):
    db, report = tmp_path / "cli.sqlite3", tmp_path / "run.json"
    args = [sys.executable, "-m", "agenteval.cli"]
    valid = subprocess.run([*args, "validate"], capture_output=True, text=True)
    assert valid.returncode == 0
    run = subprocess.run(
        [*args, "run", "--db", str(db), "--output", str(report)], capture_output=True, text=True
    )
    assert run.returncode == 0, run.stderr
    assert "REPLAY / SIMULATED OUTPUT" in run.stdout
    content = json.loads(report.read_text(encoding="utf-8"))
    exported = tmp_path / "export.json"
    export = subprocess.run(
        [*args, "export", content["id"], "--db", str(db), "--output", str(exported)],
        capture_output=True,
        text=True,
    )
    assert export.returncode == 0
    assert json.loads(exported.read_text(encoding="utf-8")) == content


def test_cli_malformed_input_controlled(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "agenteval.cli", "validate", "--suite", str(bad)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_concurrent_runs_rejected_and_gate_released(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    import agenteval.api as module

    entered, release = Event(), Event()
    original = module.run_suite

    def blocked(suite):
        entered.set()
        assert release.wait(10)
        return original(suite)

    monkeypatch.setattr(module, "run_suite", blocked)
    with client(tmp_path / "api.sqlite3") as api, ThreadPoolExecutor() as pool:
        first = pool.submit(api.post, "/runs")
        try:
            assert entered.wait(10)
            assert api.post("/runs").status_code == 409
        finally:
            release.set()
        assert first.result(timeout=10).status_code == 201
        assert api.post("/runs").status_code == 201


def test_storage_failure_controlled_and_gate_released(tmp_path, monkeypatch):
    from sqlalchemy.exc import SQLAlchemyError

    from agenteval.storage import Store

    original = Store.save

    def unavailable(self, run):
        raise SQLAlchemyError("Do not expose private storage details")

    with client(tmp_path / "api.sqlite3") as api:
        monkeypatch.setattr(Store, "save", unavailable)
        response = api.post("/runs")
        assert response.status_code == 503
        assert "private" not in response.text
        monkeypatch.setattr(Store, "save", original)
        assert api.post("/runs").status_code == 201
