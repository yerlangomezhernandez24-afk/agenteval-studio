"""Coverage gaps found in the phase 5 lifecycle audit; no changed replay oracles."""

from threading import Event, Lock, Thread

import pytest
from ollama_double import MODEL, serve_double

from agenteval.local_jobs import JobBusy, JobManager
from agenteval.local_models import GenerationOptions
from agenteval.ollama import OllamaClient
from agenteval.storage import Store


def test_closed_manager_rejects_new_work(tmp_path):
    with serve_double() as (_, port):
        store = Store(tmp_path / "closed.sqlite3")
        manager = JobManager(store, Lock(), OllamaClient.for_test_server(port))
        manager.close()
        try:
            with pytest.raises(JobBusy):
                manager.start(MODEL["name"], "support-json-v1", GenerationOptions())
        finally:
            manager.close()
            store.close()


def test_thread_start_failure_cleans_job_and_gate(tmp_path, monkeypatch):
    with serve_double() as (_, port):
        store = Store(tmp_path / "thread.sqlite3")
        gate = Lock()
        manager = JobManager(store, gate, OllamaClient.for_test_server(port))
        original_start = Thread.start

        def fail(thread):
            if thread.name == "agenteval-local":
                raise RuntimeError("thread unavailable")
            return original_start(thread)

        monkeypatch.setattr(Thread, "start", fail)
        try:
            with pytest.raises(RuntimeError):
                manager.start(MODEL["name"], "support-json-v1", GenerationOptions())
            assert not gate.locked()
            assert manager.active_id is None
            assert manager.jobs == {}
            manager.close()
        finally:
            store.close()


def test_close_during_http_saves_partial_before_store_shutdown(tmp_path):
    with serve_double() as (state, port):
        state.delay = 5
        store = Store(tmp_path / "shutdown.sqlite3")
        manager = JobManager(store, Lock(), OllamaClient.for_test_server(port))
        job = manager.start(MODEL["name"], "support-json-v1", GenerationOptions())
        assert state.entered.wait(2)
        manager.close()
        saved_job = manager.get(job.id)
        assert saved_job.status == "cancelled"
        run = store.get(saved_job.run_id)
        assert [a.code for a in run.attempts] == ["cancelled", "not_started", "not_started"]
        assert not manager.thread.is_alive()
        assert not manager.gate.locked()
        store.close()
        reopened = Store(tmp_path / "shutdown.sqlite3")
        assert reopened.get(run.id) == run
        reopened.close()


def test_close_waits_for_start_preparation(tmp_path, monkeypatch):
    with serve_double() as (_, port):
        store = Store(tmp_path / "race.sqlite3")
        client = OllamaClient.for_test_server(port)
        manager = JobManager(store, Lock(), client)
        entered, release, closed = Event(), Event(), Event()
        original = client.models

        def blocked(cancel=None):
            entered.set()
            assert release.wait(3)
            return original(cancel)

        monkeypatch.setattr(client, "models", blocked)
        starter = Thread(
            target=lambda: manager.start(MODEL["name"], "support-json-v1", GenerationOptions())
        )

        def close():
            manager.close()
            closed.set()

        closer = Thread(target=close)
        starter.start()
        assert entered.wait(2)
        closer.start()
        try:
            assert not closed.wait(0.1)
        finally:
            release.set()
            starter.join(5)
            closer.join(5)
        assert closed.is_set()
        assert not manager.thread.is_alive()
        assert not manager.gate.locked()
        store.close()


def test_worker_failure_http_is_controlled(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from agenteval.api import create_app

    with serve_double() as (_, port):
        with TestClient(
            create_app(tmp_path / "api.sqlite3", ollama_client=OllamaClient.for_test_server(port)),
            base_url="http://127.0.0.1:8765",
        ) as api:
            original = Thread.start

            def fail(thread):
                if thread.name == "agenteval-local":
                    raise RuntimeError("private diagnostic")
                return original(thread)

            monkeypatch.setattr(Thread, "start", fail)
            headers = {"X-CSRF-Token": api.get("/api/session").json()["csrf_token"]}
            result = api.post("/api/ollama/jobs", params={"model": MODEL["name"]}, headers=headers)
            assert result.status_code == 503
            assert "private diagnostic" not in result.text
            assert api.post("/api/runs", headers=headers).status_code == 201
