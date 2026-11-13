import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select, update

from agenteval.api import create_app
from agenteval.engine import run_suite
from agenteval.evaluators import evaluate
from agenteval.integrity import SnapshotCorruption
from agenteval.io import digest, load_suite
from agenteval.models import Response, Run
from agenteval.storage import MAX_OFFSET, Store


def test_escaped_forbidden_marker():
    case = next(c for c in load_suite().cases if c.id == "secret-leak")
    raw = json.dumps({**case.expected.model_dump(), "summary": "FAKE_SECRET_CANARY"})
    raw = raw.replace("CANARY", r"CAN\u0041RY")
    checks = {c.criterion: c.outcome for c in evaluate(case, raw)}
    assert checks["content"] == "fail"


def test_escaped_required_marker():
    case = next(c for c in load_suite().cases if c.id == "required-text")
    raw = json.dumps({**case.expected.model_dump(), "summary": "Requires human review."})
    raw = raw.replace("review", r"revi\u0065w")
    checks = {c.criterion: c.outcome for c in evaluate(case, raw)}
    assert checks["content"] == "pass"


@pytest.mark.parametrize("summary", ["human REVIEW", "HUMAN REVIEW", "human review"])
def test_decoded_casefold(summary):
    case = next(c for c in load_suite().cases if c.id == "required-text")
    checks = evaluate(case, json.dumps({"summary": summary}))
    assert checks[-1].outcome == "pass"  # independent of other missing fields


@pytest.mark.parametrize("rule,text", [("café", "CAFE\u0301"), ("cafe\u0301", "CAFÉ")])
def test_canonical_unicode(rule, text):
    case = load_suite().cases[0].model_copy(update={"contains": [rule], "excludes": []})
    assert evaluate(case, json.dumps({"summary": text}))[-1].outcome == "pass"
    case.contains, case.excludes = [], [rule]
    assert evaluate(case, json.dumps({"summary": text}))[-1].outcome == "fail"


@pytest.mark.parametrize("raw", ["{}", '{"summary":42}', '{"summary":null}', "{", "[]"])
def test_unavailable_decoded_text(raw):
    case = next(c for c in load_suite().cases if c.id == "secret-leak")
    assert evaluate(case, raw)[-1].outcome == "not_evaluable"


def test_content_scope_is_only_summary():
    case = next(c for c in load_suite().cases if c.id == "secret-leak")
    raw = json.dumps({"summary": "Allowed", "other": "FAKE_SECRET_CANARY"})
    checks = {c.criterion: c.outcome for c in evaluate(case, raw)}
    assert checks["content"] == "pass"
    assert checks["schema_valid"] == "fail"


@pytest.mark.parametrize("summary", ["   ", "\t\n", "\u2003"])
def test_blank_summary_versioned(summary):
    case = load_suite().cases[0]
    data = {**case.expected.model_dump(), "summary": summary}
    with pytest.raises(ValidationError):
        Response.model_validate(data)
    assert evaluate(case, json.dumps(data), "1.0")[1].outcome == "pass"
    assert evaluate(case, json.dumps(data), "1.1")[1].outcome == "fail"


@pytest.mark.parametrize("summary", ["Valid summary", "\tcontent\n", "é"])
def test_meaningful_summary(summary):
    data = {**load_suite().cases[0].expected.model_dump(), "summary": summary}
    assert Response.model_validate(data).summary == summary


def test_replay_change_does_not_change_cases_hash():
    suite = load_suite()
    a = run_suite(suite)
    suite.replay["vpn"].output = "{}"
    b = run_suite(suite)
    assert a.cases_hash == b.cases_hash
    assert a.dataset_hash != b.dataset_hash  # legacy name: whole suite fingerprint
    assert a.replay_hash != b.replay_hash
    assert a.prompt_hash == b.prompt_hash


def test_36_cases_unchanged_and_versioned_checks():
    original = load_suite(Path("backend/agenteval/data/support-v1.json"))
    current = load_suite()
    assert original.criteria_version == "1.0"
    assert current.criteria_version == "1.1"
    assert original.cases == current.cases
    assert original.replay == current.replay
    a, b = run_suite(original), run_suite(current)
    assert a.cases_hash == b.cases_hash
    assert a.replay_hash == b.replay_hash
    assert a.dataset_hash != b.dataset_hash
    for left, right in zip(a.results, b.results, strict=True):
        assert left.status == right.status
        assert [(c.criterion, c.outcome) for c in left.checks] == [
            (c.criterion, c.outcome) for c in right.checks
        ]
    assert a.metrics.model_dump(exclude={"latency_median_ms", "latency_p95_ms"}) == (
        b.metrics.model_dump(exclude={"latency_median_ms", "latency_p95_ms"})
    )
    # Four applicable content-check explanations change; outcomes do not.
    assert (
        sum(left.checks != right.checks for left, right in zip(a.results, b.results, strict=True))
        == 4
    )


@pytest.mark.parametrize("name", ["replay-a.json", "replay-b.json"])
def test_historical_snapshots_read_without_mutation(name, tmp_path):
    original = Path("docs/evidence", name).read_text(encoding="utf-8")
    run = Run.model_validate_json(original)
    assert run.engine_version == "0.1.0"
    store = Store(tmp_path / "history.sqlite3")
    store.save(run)
    assert store.get(run.id) == run
    with store.engine.connect() as conn:
        assert conn.execute(select(store.runs.c.snapshot)).scalar() == run.model_dump_json()
    store.close()


def corrupt(store, run, mutation):
    data = run.model_dump()
    if mutation == "case":
        data["suite"]["cases"][0]["input"] = "PRIVATE_CHANGED_CONTENT"
    elif mutation == "replay":
        data["suite"]["replay"]["vpn"]["output"] = "CHANGED"
    elif mutation == "prompt":
        data["suite"]["prompt"] = "CHANGED"
    elif mutation == "metrics":
        data["metrics"]["passed"] += 1
    elif mutation == "id":
        data["id"] = "00000000-0000-0000-0000-000000000000"
    elif mutation == "checks":
        data["results"][0]["checks"][0]["outcome"] = "fail"
    elif mutation == "missing_check":
        data["results"][0]["checks"].pop()
    elif mutation == "result_id":
        data["results"][0]["case_id"] = "wrong-id"
    elif mutation == "missing_result":
        data["results"].pop()
    elif mutation == "raw":
        data["results"][0]["raw_output"] = "{}"
    elif mutation == "latency":
        data["results"][0]["latency_ms"] = -1.0
    elif mutation == "engine":
        data["engine_version"] = "9.9.9"
    elif mutation == "rehash":
        # Consistent source hashes alone do not validate stored results.
        data["suite"]["replay"]["vpn"]["output"] = "{}"
        data["replay_hash"] = digest(data["suite"]["replay"])
        data["dataset_hash"] = digest(data["suite"])
    raw = '{"PRIVATE":' if mutation == "json" else json.dumps(data)
    with store.engine.begin() as conn:
        conn.execute(update(store.runs).where(store.runs.c.id == run.id).values(snapshot=raw))
    return raw


@pytest.mark.parametrize(
    "mutation",
    [
        "case",
        "replay",
        "prompt",
        "metrics",
        "id",
        "checks",
        "missing_check",
        "result_id",
        "missing_result",
        "raw",
        "latency",
        "engine",
        "rehash",
        "json",
    ],
)
def test_corruption_rejected_record_preserved(tmp_path, mutation):
    store = Store(tmp_path / "corrupt.sqlite3")
    run = run_suite(load_suite())
    store.save(run)
    raw = corrupt(store, run, mutation)
    with pytest.raises(SnapshotCorruption, match="integrity"):
        store.get(run.id)
    with store.engine.connect() as conn:
        assert conn.execute(select(store.runs.c.snapshot)).scalar() == raw
    store.close()


def test_corruption_cli_and_http_controlled(tmp_path):
    path = tmp_path / "corrupt.sqlite3"
    store = Store(path)
    run = run_suite(load_suite())
    store.save(run)
    corrupt(store, run, "json")
    store.close()
    output = tmp_path / "export.json"
    cli = subprocess.run(
        [
            sys.executable,
            "-m",
            "agenteval.cli",
            "export",
            run.id,
            "--db",
            str(path),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )
    assert cli.returncode == 3
    assert "integrity" in cli.stderr
    assert "PRIVATE" not in cli.stderr and "Traceback" not in cli.stderr
    assert not output.exists()
    with TestClient(create_app(path), base_url="http://127.0.0.1:8765") as client:
        response = client.get(f"/runs/{run.id}")
        assert response.status_code == 409
        assert response.json()["code"] == "snapshot_corrupt"
        assert "PRIVATE" not in response.text


@pytest.mark.parametrize("offset", [-1, 9223372036854775808, 10**100, True, 1.5])
def test_store_offset_rejected(tmp_path, offset):
    store = Store(tmp_path / "offset.sqlite3")
    with pytest.raises(ValueError):
        store.list_ids(offset=offset)
    store.close()


@pytest.mark.parametrize(
    "offset,status",
    [("-1", 422), ("9223372036854775808", 422), ("9" * 5000, 422), (str(MAX_OFFSET), 200)],
)
def test_http_offset_boundaries(tmp_path, offset, status):
    with TestClient(
        create_app(tmp_path / "offset.sqlite3"), base_url="http://127.0.0.1:8765"
    ) as client:
        assert client.get("/runs?offset=" + offset).status_code == status


def test_store_offset_limit_allowed(tmp_path):
    store = Store(tmp_path / "offset.sqlite3")
    assert store.list_ids(offset=MAX_OFFSET) == []
    store.close()
