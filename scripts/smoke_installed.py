"""Run from an installed environment; real loopback HTTP, restart and replay evidence."""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from sqlalchemy import update

import agenteval
from agenteval.engine import run_suite
from agenteval.io import export_run, load_suite
from agenteval.storage import Store


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, default=root / "docs/evidence-corrected")
    evidence = parser.parse_args().evidence_dir.resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    assert "site-packages" in str(agenteval.__file__), "Must test the installed wheel"
    a, b = run_suite(load_suite()), run_suite(load_suite())
    assert [r.model_dump(exclude={"latency_ms"}) for r in a.results] == [
        r.model_dump(exclude={"latency_ms"}) for r in b.results
    ]
    for label, run in [("a", a), ("b", b)]:
        export_run(run, evidence / f"replay-{label}.json")
    store = Store(root / "data/audit-corrected.sqlite3")
    store.save(a)
    store.save(b)
    store.close()
    store = Store(root / "data/audit-corrected.sqlite3")
    assert store.get(a.id) == a
    store.close()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    opener = build_opener(ProxyHandler({}))
    statuses = []
    offset_statuses = {}
    corrupt_status = None
    run_id = None
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with (evidence / "http-server.log").open("w", encoding="utf-8") as log:
        for _ in range(2):
            server = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "agenteval.cli",
                    "serve",
                    "--db",
                    str(root / "data/http-corrected.sqlite3"),
                    "--port",
                    str(port),
                ],
                cwd=evidence,
                stdout=log,
                stderr=log,
                creationflags=flags,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            try:
                for _attempt in range(100):
                    try:
                        with opener.open(base + "/health", timeout=1) as response:
                            assert response.status == 200
                            response.read()
                        break
                    except (URLError, OSError):
                        if server.poll() is not None:
                            raise RuntimeError("HTTP server exited early") from None
                        time.sleep(0.1)
                else:
                    raise RuntimeError("HTTP server readiness timeout")
                if run_id is None:
                    with opener.open(base + "/session", timeout=5) as session:
                        csrf = json.load(session)["csrf_token"]
                    with opener.open(
                        Request(base + "/runs", method="POST", headers={"X-CSRF-Token": csrf}),
                        timeout=5,
                    ) as response:
                        statuses.append(response.status)
                        result = json.load(response)
                        assert result["metrics"]["failed"] == 16
                        run_id = result["id"]
                else:
                    with opener.open(base + "/runs/" + run_id, timeout=5) as response:
                        statuses.append(response.status)
                        assert json.load(response)["id"] == run_id
                    for offset, expected in [
                        ("-1", 422),
                        ("9223372036854775808", 422),
                        ("9" * 5000, 422),
                        ("1000000", 200),
                    ]:
                        try:
                            with opener.open(
                                base + "/runs?offset=" + offset, timeout=5
                            ) as response:
                                status = response.status
                                response.read()
                        except HTTPError as error:
                            status = error.code
                            error.read()
                            error.close()
                        assert status == expected
                        offset_statuses[offset if len(offset) < 30 else "5000 digits"] = status
                    damaged = Store(root / "data/http-corrected.sqlite3")
                    with damaged.engine.begin() as conn:
                        conn.execute(
                            update(damaged.runs)
                            .where(damaged.runs.c.id == run_id)
                            .values(snapshot='{ "PRIVATE":')
                        )
                    damaged.close()
                    try:
                        opener.open(base + "/runs/" + run_id, timeout=5)
                        raise AssertionError("Corruption was not detected")
                    except HTTPError as error:
                        corrupt_status = error.code
                        body = error.read().decode()
                        error.close()
                        assert corrupt_status == 409 and "PRIVATE" not in body
            finally:
                server.terminate()
                server.wait(timeout=10)
    evidence.joinpath("http-smoke.json").write_text(
        json.dumps(
            {
                "transport": "real HTTP on 127.0.0.1",
                "create_and_restart_get_status": statuses,
                "persisted_run_id": run_id,
                "server_stopped": True,
                "offset_statuses": offset_statuses,
                "corrupt_snapshot_status": corrupt_status,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    evidence.joinpath("clean-install.json").write_text(
        json.dumps(
            {
                "python": sys.version,
                "module_path": str(Path(agenteval.__file__).relative_to(root)),
                "installed_wheel": True,
                "replay_outcomes_reproduced": True,
                "suite_cases": len(a.suite.cases),
                "run_a": a.id,
                "run_b": b.id,
                "dataset_hash": a.dataset_hash,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("Installed wheel: replay, persistence, real HTTP and process restart verified.")


if __name__ == "__main__":
    main()
