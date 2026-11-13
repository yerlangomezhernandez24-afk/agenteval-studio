"""Installed-wheel HTTP verification using disposable project-local databases."""

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from sqlalchemy import update

import agenteval
from agenteval.storage import Store


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    evidence = root / "docs/evidence-phase4"
    assert "site-packages" in str(agenteval.__file__)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}/api"
    opener = build_opener(ProxyHandler({}))
    observed = {}

    def request(path, expected, *, method="GET", headers=None, decode_json=True):
        try:
            response = opener.open(
                Request(base + path, method=method, headers=headers or {}), timeout=5
            )
        except HTTPError as error:
            response = error
        with response:
            status, body = response.status, response.read()
        assert status == expected, (path, status, expected)
        return json.loads(body) if decode_json else body.decode("utf-8")

    @contextmanager
    def server(db):
        with (evidence / "http-server.log").open("a", encoding="utf-8") as log:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "agenteval.cli",
                    "serve",
                    "--db",
                    str(db),
                    "--port",
                    str(port),
                ],
                stdout=log,
                stderr=log,
                cwd=evidence,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            try:
                for _ in range(100):
                    try:
                        assert request("/health", 200)["status"] == "ok"
                        break
                    except (URLError, OSError):
                        assert process.poll() is None
                        time.sleep(0.1)
                else:
                    raise AssertionError("Server readiness timeout")
                yield
            finally:
                process.terminate()
                process.wait(timeout=10)

    with TemporaryDirectory(prefix="phase4-http-", dir=root / "data") as directory:
        db = Path(directory) / "original.sqlite3"
        with server(db):
            token = request("/session", 200)["csrf_token"]
            run = request("/runs", 201, method="POST", headers={"X-CSRF-Token": token})
            metrics = run["metrics"]
            for key, expected in {
                "total": 36,
                "passed": 16,
                "failed": 16,
                "errors": 2,
                "skipped": 1,
                "not_evaluable": 1,
            }.items():
                assert metrics[key] == expected
            assert request("/runs/" + run["id"], 200) == run
            variant = request(
                "/runs?variant=mixed-v1", 201, method="POST", headers={"X-CSRF-Token": token}
            )
            assert request("/variants", 200)[1]["id"] == "mixed-v1"
            query = f"?a={run['id']}&b={variant['id']}"
            comparison = request("/comparisons" + query, 200)
            assert comparison["counts"] == {
                "improvement": 2,
                "regression": 2,
                "unchanged": 30,
                "not_comparable": 2,
            }
            assert comparison["critical_regressions"] == ["outage"]
            assert request("/comparisons/export" + query + "&format=json", 200) == comparison
            csv_report = request(
                "/comparisons/export" + query + "&format=csv", 200, decode_json=False
            )
            assert "'outage" in csv_report and "'regression" in csv_report
            request(
                "/runs?variant=../../private", 422, method="POST", headers={"X-CSRF-Token": token}
            )
            request("/runs?variant=mixed-v1", 403, method="POST")
            for route in ("/comparisons" + query, "/comparisons/export" + query, "/variants"):
                request(route, 403, headers={"Origin": "https://evil.example"})
                request(route, 400, headers={"Host": "rebind.example"})
            for origin in ("https://evil.example", "null", f"http://localhost:{port}"):
                request(
                    "/runs", 403, method="POST", headers={"Origin": origin, "X-CSRF-Token": token}
                )
            request("/runs", 403, method="POST")
            request("/health", 400, headers={"Host": f"rebind.example:{port}"})
            for offset in ("-1", "9223372036854775808", "9" * 5000):
                request("/runs?offset=" + offset, 422)
            request("/runs?offset=1000000", 200)
        with server(db):
            assert request("/runs/" + run["id"], 200) == run
            assert request("/comparisons" + query, 200) == comparison
        damaged_db = Path(directory) / "tampered-copy.sqlite3"
        shutil.copyfile(db, damaged_db)
        damaged = Store(damaged_db)
        with damaged.engine.begin() as connection:
            connection.execute(update(damaged.runs).values(snapshot='{ "PRIVATE":'))
        damaged.close()
        with server(damaged_db):
            rejected = request("/runs/" + run["id"], 409)
            assert rejected["code"] == "snapshot_corrupt"
            assert "PRIVATE" not in json.dumps(rejected)
            assert request("/comparisons" + query, 409)["code"] == "snapshot_corrupt"
            assert request("/comparisons/export" + query, 409)["code"] == "snapshot_corrupt"
        original = Store(db)
        assert original.get(run["id"]) is not None
        original.close()
        observed.update(
            health=200,
            session=200,
            post=201,
            get=200,
            restart_get=200,
            external_null_localhost_origin=403,
            missing_csrf=403,
            invalid_host=400,
            invalid_offsets=422,
            maximum_offset=200,
            tampered_copy=409,
            original_unchanged=True,
            metrics=metrics,
            comparison=comparison,
            comparison_restart_exact=True,
            comparison_export_json=200,
            comparison_export_csv=200,
            comparison_corrupt=409,
            invalid_variant=422,
        )
    observed.update(
        installed_wheel=True,
        python=sys.version,
        servers_stopped=True,
        temporary_databases_removed=True,
    )
    (evidence / "http-smoke.json").write_text(json.dumps(observed, indent=2), encoding="utf-8")
    print("Real /api HTTP, replay counts, restart, attacks and tampered copy: verified.")


if __name__ == "__main__":
    main()
