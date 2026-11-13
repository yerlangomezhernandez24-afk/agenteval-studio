"""Phase 4 adds HTTP and v2 checks without changing replay oracles."""

import json
import time
from threading import Event

import pytest
from fastapi.testclient import TestClient
from ollama_double import MODEL, serve_double
from sqlalchemy import update

from agenteval.api import create_app
from agenteval.integrity import SnapshotCorruption, restore
from agenteval.local_models import GenerationOptions
from agenteval.local_snapshot import snapshot_digest
from agenteval.ollama import OllamaClient, OllamaFailure
from agenteval.storage import Store


@pytest.fixture
def local(tmp_path):
    with serve_double() as (state, port):
        transport = OllamaClient.for_test_server(port)
        db = tmp_path / "phase4.sqlite3"
        with TestClient(
            create_app(db, ollama_client=transport), base_url="http://127.0.0.1:8765"
        ) as api:
            headers = {"X-CSRF-Token": api.get("/api/session").json()["csrf_token"]}
            yield state, transport, api, headers, db


def start(api, headers):
    response = api.post("/api/ollama/jobs", params={"model": MODEL["name"]}, headers=headers)
    assert response.status_code == 202, response.text
    return response.json()["id"]


def finish(api, job):
    for _ in range(200):
        data = api.get(f"/api/ollama/jobs/{job}").json()
        if data["status"] in {"completed", "cancelled", "error"}:
            assert data["status"] != "error", data
            return data
        time.sleep(0.01)
    pytest.fail("Bounded local job did not finish")


def test_http_snapshot_restart_and_exports(local, monkeypatch):
    state, transport, api, headers, db = local
    status = api.get("/api/ollama/status").json()
    assert status["available"] and status["provenance"] == "http_test_double"
    job = finish(api, start(api, headers))
    assert job["completed_cases"] == 3
    result = api.get(f"/api/runs/{job['run_id']}")
    assert result.status_code == 200
    run = result.json()
    assert run["provider"] == "OllamaLocal" and run["snapshot_version"] == 2
    assert run["metrics"]["total"] == 3 and run["metrics"]["not_evaluable"] == 1
    assert run["results"][1]["status"] == "failed"
    requests = [payload for method, path, payload in state.requests if path == "/api/generate"]
    assert len(requests) == 3
    assert requests[0] == {
        "model": MODEL["name"],
        "system": run["suite"]["prompt"],
        "prompt": run["suite"]["cases"][0]["input"],
        "stream": False,
        "format": "json",
        "keep_alive": 0,
        "options": run["options"],
    }
    monkeypatch.setattr(OllamaClient, "_request", lambda *a, **kw: pytest.fail("Reinference"))
    store = Store(db)
    saved = store.get(job["run_id"])
    assert saved.model_dump(mode="json") == run
    store.close()
    for format in ("json", "csv"):
        response = api.get(f"/api/runs/{job['run_id']}/export?format={format}")
        assert response.status_code == 200
        assert "http_test_double" in response.text and "LOCAL LLM / EXPERIMENTAL" in response.text
    replay = api.post("/api/runs", headers=headers).json()
    report = api.get("/api/comparisons", params={"a": replay["id"], "b": job["run_id"]}).json()
    assert not report["compatible"] and not report["cases"]


@pytest.mark.parametrize("field", ["raw_output", "metrics", "model", "case_id", "snapshot_hash"])
def test_corruption_409(local, field):
    _, _, api, headers, db = local
    job = finish(api, start(api, headers))
    run = api.get(f"/api/runs/{job['run_id']}").json()
    if field == "raw_output":
        run["results"][0][field] = "secret corrupted raw"
    elif field == "case_id":
        run["attempts"][0][field] = "missing"
    elif field == "metrics":
        run["metrics"]["passed"] += 1
    else:
        run[field] = "corrupted"
    store = Store(db)
    with store.engine.begin() as conn:
        conn.execute(
            update(store.runs)
            .where(store.runs.c.id == job["run_id"])
            .values(snapshot=json.dumps(run))
        )
    store.close()
    for suffix in ("", "/export?format=json", "/export?format=csv"):
        response = api.get(f"/api/runs/{job['run_id']}{suffix}")
        assert response.status_code == 409 and "secret corrupted raw" not in response.text


def test_cancel_and_shared_gate(local):
    state, _, api, headers, _ = local
    state.delay = 5
    job = start(api, headers)
    assert state.entered.wait(2)
    assert api.post("/api/runs", headers=headers).status_code == 409
    assert (
        api.post("/api/ollama/jobs", params={"model": MODEL["name"]}, headers=headers).status_code
        == 409
    )
    assert api.post(f"/api/ollama/jobs/{job}/cancel", headers=headers).status_code == 200
    result = finish(api, job)
    assert result["status"] == "cancelled" and result["completed_cases"] == 1
    run = api.get(f"/api/runs/{result['run_id']}").json()
    assert [a["code"] for a in run["attempts"]] == ["cancelled", "not_started", "not_started"]
    assert run["metrics"]["errors"] == 1 and run["metrics"]["skipped"] == 2
    assert api.post("/api/runs", headers=headers).status_code == 201


@pytest.mark.parametrize(
    "models",
    [
        None,
        {},
        [None],
        [{**MODEL, "name": "x" * 129}],
        [{**MODEL, "digest": "invalid"}],
        [MODEL, MODEL],
    ],
)
def test_invalid_catalog(local, models):
    state, _, api, _, _ = local
    state.models = models
    result = api.get("/api/ollama/status").json()
    assert not result["available"] and result["models"] == []


def test_empty_and_cloud_catalog(local):
    state, _, api, headers, _ = local
    state.models = [{**MODEL, "remote_host": "https://cloud.invalid"}]
    assert api.get("/api/ollama/status").json()["models"] == []
    assert (
        api.post("/api/ollama/jobs", params={"model": MODEL["name"]}, headers=headers).status_code
        == 422
    )
    assert api.post("/api/runs", headers=headers).status_code == 201


@pytest.mark.parametrize("status", [302, 400, 500])
def test_http_status_rejected(local, status):
    state, transport, _, _, _ = local
    state.status = status
    with pytest.raises(OllamaFailure, match="http_error"):
        transport.models()


@pytest.mark.parametrize(
    "headers",
    [
        {"Content-Type": "text/html"},
        {"Location": "https://outside.invalid"},
        {"Set-Cookie": "secret=1"},
        {"Content-Encoding": "gzip"},
        {"Content-Length": "9999999"},
        {"Content-Length": "1000"},
    ],
)
def test_untrusted_headers(local, headers):
    state, transport, _, _, _ = local
    state.headers = headers
    with pytest.raises(OllamaFailure):
        transport.models()


@pytest.mark.parametrize(
    "raw",
    [
        b"not json",
        b'{"models":[],"untrusted":"\\ud800"}',
        b"{}{}",
        b'{"models":[],"models":[]}',
        b"[]",
        b"x" * 65537,
    ],
)
def test_untrusted_envelope(local, raw):
    state, transport, _, _, _ = local
    state.raw = raw
    with pytest.raises(OllamaFailure):
        transport.models()


@pytest.mark.parametrize(
    "override",
    [
        {"done": False},
        {"model": "unauthorized"},
        {"response": "x" * 16001},
        {"eval_count": 129},
        {"eval_count": True},
        {"total_duration": -1},
    ],
)
def test_untrusted_generation(local, override):
    state, transport, _, _, _ = local
    model = transport.models()[0]
    state.response_overrides = override
    with pytest.raises(OllamaFailure):
        transport.generate(model, "test", "synthetic", GenerationOptions(), Event())


def test_timeout_and_no_proxy(local, monkeypatch):
    state, transport, _, _, _ = local
    monkeypatch.setenv("HTTP_PROXY", "http://outside.invalid:8080")
    monkeypatch.setenv("ALL_PROXY", "http://outside.invalid:8080")
    assert transport.models()[0].name == MODEL["name"]
    state.delay = 1
    with pytest.raises(OllamaFailure, match="timeout"):
        transport._request("/api/generate", {}, timeout=0.05)
    assert not transport._active


@pytest.mark.parametrize("mutation", ["host", "port", "path"])
def test_destination_guard(mutation):
    client = OllamaClient()
    path = "/api/tags"
    if mutation == "host":
        client._host = "example.com"
    elif mutation == "port":
        client._port = 80
    else:
        path = "/api/pull"
    with pytest.raises(OllamaFailure, match="invalid_response"):
        client._request(path)


@pytest.mark.parametrize(
    "params",
    [
        {"num_predict": 1000},
        {"temperature": "nan"},
        {"seed": -1},
        {"prompt": "free text"},
        {"model": "http://outside"},
    ],
)
def test_query_bounds(local, params):
    _, _, api, headers, _ = local
    assert (
        api.post(
            "/api/ollama/jobs", params={"model": MODEL["name"], **params}, headers=headers
        ).status_code
        == 422
    )


def test_new_web_security(local):
    _, _, api, headers, _ = local
    assert api.post("/api/ollama/jobs", params={"model": MODEL["name"]}).status_code == 403
    for path in ("/api/ollama/status", "/api/ollama/jobs/00000000-0000-0000-0000-000000000000"):
        for unsafe in (
            {"Origin": "null"},
            {"Origin": "https://outside.invalid"},
            {"Sec-Fetch-Mode": "navigate"},
        ):
            assert api.get(path, headers=unsafe).status_code == 403
        assert api.get(path, headers={"Host": "outside.invalid"}).status_code == 400


def test_reevaluation_even_if_hash_recomputed(local):
    _, _, api, headers, db = local
    job = finish(api, start(api, headers))
    store = Store(db)
    run = store.get(job["run_id"])
    run.results[0].checks[0].outcome = "fail"
    run.snapshot_hash = snapshot_digest(run)
    with pytest.raises(SnapshotCorruption):
        restore(run.model_dump_json(), run.id, run.created_utc)
    store.close()


def test_unavailable_and_replay_survives(tmp_path):
    with serve_double() as (_, port):
        transport = OllamaClient.for_test_server(port)
    with TestClient(
        create_app(tmp_path / "absent.sqlite3", ollama_client=transport),
        base_url="http://127.0.0.1:8765",
    ) as api:
        status = api.get("/api/ollama/status").json()
        assert not status["available"] and status["error"] in {"connection_error", "timeout"}
        headers = {"X-CSRF-Token": api.get("/api/session").json()["csrf_token"]}
        assert (
            api.post(
                "/api/ollama/jobs", params={"model": MODEL["name"]}, headers=headers
            ).status_code
            == 503
        )
        assert api.post("/api/runs", headers=headers).json()["metrics"]["passed"] == 16


def test_persistence_failure_releases_gate(local, monkeypatch):
    _, _, api, headers, _ = local

    def fail(*args):
        raise OSError("private path must not leak")

    original = Store.save
    monkeypatch.setattr(Store, "save", fail)
    job = start(api, headers)
    for _ in range(200):
        data = api.get(f"/api/ollama/jobs/{job}").json()
        if data["status"] == "error":
            break
        time.sleep(0.01)
    assert data["status"] == "error" and data["run_id"] is None
    assert "private path" not in str(data)
    monkeypatch.setattr(Store, "save", original)
    assert api.post("/api/runs", headers=headers).status_code == 201


def test_llm_comparison_compatibility(local):
    from agenteval.comparison import compare_runs

    _, _, api, headers, db = local
    job = finish(api, start(api, headers))
    store = Store(db)
    run = store.get(job["run_id"])
    assert compare_runs(run, run).compatible
    other = run.model_copy(deep=True)
    other.provenance = "local_ollama"
    assert not compare_runs(run, other).compatible
    other = run.model_copy(deep=True)
    other.completion = "cancelled"
    assert not compare_runs(run, other).compatible
    other = run.model_copy(deep=True)
    other.engine_version = "unsupported"
    assert not compare_runs(run, other).compatible
    store.close()


@pytest.mark.parametrize(
    "raw,status",
    [
        (
            '{"category":"network","priority":"medium","requires_human":false,"summary":"VPN"}',
            "passed",
        ),
        (
            '{"category":"network","priority":"medium","requires_human":false,"summary":"VPN","command":"whoami"}',
            "failed",
        ),
        (
            '{"category":"network","priority":"medium","requires_human":false,"summary":"\\u0056PN"}',
            "passed",
        ),
        ("", "not_evaluable"),
        ("invalid", "failed"),
    ],
)
def test_raw_contract_evaluation(local, raw, status):
    state, _, api, headers, _ = local
    state.outputs = [raw]
    job = finish(api, start(api, headers))
    run = api.get(f"/api/runs/{job['run_id']}").json()
    assert run["results"][0]["case_id"] == "vpn"
    assert run["results"][0]["status"] == status
    assert run["results"][0]["raw_output"] == raw


def test_changed_digest_prevents_generation(local):
    state, transport, _, _, _ = local
    model = transport.models()[0]
    state.models = [{**MODEL, "digest": "b" * 64}]
    with pytest.raises(OllamaFailure, match="invalid_response"):
        transport.generate(model, "test", "synthetic", GenerationOptions(), Event())
    assert not any(path == "/api/generate" for _, path, _ in state.requests)
