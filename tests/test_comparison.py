import csv
import io
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from agenteval.api import create_app
from agenteval.comparison import Comparison, check_change, compare_runs
from agenteval.engine import run_suite
from agenteval.io import load_suite
from agenteval.models import ReplayRecord
from agenteval.reports import comparison_csv, csv_cell
from agenteval.storage import Store
from agenteval.variants import catalog, load_variant


@pytest.fixture
def pair():
    return run_suite(load_variant()), run_suite(load_variant("mixed-v1"))


def test_versioned_variant_preserves_cases_prompt_and_original():
    original = load_suite()
    variant = load_variant("mixed-v1")
    assert variant.cases == original.cases and variant.criteria == original.criteria
    assert variant.criteria_version == original.criteria_version == "1.1"
    assert variant.prompt == original.prompt
    assert variant.replay_version != original.replay_version
    assert load_suite() == original
    assert catalog()[0]["cases_hash"] == catalog()[1]["cases_hash"]
    assert catalog()[0]["replay_hash"] != catalog()[1]["replay_hash"]
    with pytest.raises(ValueError):
        load_variant("../../private")


def test_real_mixed_outcomes_and_critical_regression(pair):
    a, b = pair
    report = compare_runs(a, b)
    assert report.compatible
    assert report.counts == dict(improvement=2, regression=2, unchanged=30, not_comparable=2)
    assert report.critical_regressions == ["outage"]
    assert report.metrics_a.pass_rate == report.metrics_b.pass_rate
    changes = {case.case_id: case for case in report.cases}
    assert changes["disk"].change == changes["secret-leak"].change == "improvement"
    assert changes["vpn"].change == changes["outage"].change == "regression"
    assert changes["password"].b_status == "error"
    assert changes["password"].change == changes["calendar"].change == "not_comparable"
    assert changes["scheduled"].a_status == changes["scheduled"].b_status == "skipped"
    assert changes["empty"].b_status == "not_evaluable"
    assert report.rates["category"].denominator_delta == -2
    assert compare_runs(a, b) == report
    assert compare_runs(b, a).critical_regressions == ["disk", "secret-leak"]
    assert report.fingerprints["a"]["replay_hash"] != report.fingerprints["b"]["replay_hash"]


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("hash", "cases_hash"),
        ("criteria", "criterio"),
        ("case", "caso"),
        ("check", "check"),
        ("legacy", "1.0"),
        ("engine", "motor"),
        ("suite", "suite"),
        ("label", "etiquetas"),
    ],
)
def test_incompatible_snapshots_are_not_compared(pair, mutation, reason):
    a, b = pair
    if mutation == "hash":
        b.cases_hash = "0" * 64
    elif mutation == "criteria":
        b.suite.criteria.pop()
    elif mutation == "case":
        b.results.pop()
    elif mutation == "check":
        b.results[0].checks.pop()
    elif mutation == "legacy":
        b.suite.criteria_version = "1.0"
    elif mutation == "engine":
        b.engine_version = "0.1.0"
    elif mutation == "suite":
        b.suite.version = "2.0.0"
    else:
        b.suite.cases[0].expected.priority = "high"
    report = compare_runs(a, b)
    assert not report.compatible and any(reason in item for item in report.reasons)
    assert report.cases == [] and report.rates == {} and not any(report.counts.values())


def test_same_legacy_is_explicitly_comparable():
    suite = load_suite().model_copy(update={"criteria_version": "1.0"})
    a, b = run_suite(suite), run_suite(suite)
    assert compare_runs(a, b).compatible
    assert compare_runs(a, b).fingerprints["a"]["criteria_version"] == "1.0"


@pytest.mark.parametrize(
    "a,b,change",
    [
        ("pass", "fail", "regression"),
        ("fail", "pass", "improvement"),
        ("pass", "not_evaluable", "not_comparable"),
        ("not_evaluable", "pass", "not_comparable"),
        ("not_evaluable", "not_evaluable", "unchanged"),
    ],
)
def test_check_transitions(a, b, change):
    assert check_change(a, b) == change


def test_zero_denominators_and_availability_not_false_improvement():
    suite = load_suite()
    suite.replay = {
        key: ReplayRecord(kind="skipped", note="Synthetic omission") for key in suite.replay
    }
    report = compare_runs(run_suite(suite), run_suite(suite))
    assert report.rates["pass_rate"].a.denominator == 0
    assert report.rates["pass_rate"].percentage_points is None
    assert report.metrics_b.skipped == 36 and report.metrics_b.failed == 0
    assert report.metrics_b.latency_samples == 0


@pytest.mark.parametrize(
    "text",
    ["=1+1", "+cmd", "-cmd", "@SUM(A1)", "\t=1", "\r=1", "\n=1", "  =1", 'a,"b"\n=2', "\ufeff=1"],
)
def test_csv_untrusted_text_is_always_literal(text):
    assert csv_cell(text) == "'" + text


def test_export_roundtrip_and_csv_rows(pair):
    report = compare_runs(*pair)
    restored = Comparison.model_validate_json(report.model_dump_json())
    assert restored == report
    report.cases[0].name = '=HYPERLINK("https://evil.example")'
    rows = list(csv.DictReader(io.StringIO(comparison_csv(report))))
    assert len(rows) == 7 + 5 + 36 * 7
    assert all(None not in row for row in rows)
    assert any(row["name"].startswith("'=HYPERLINK") for row in rows)
    assert all(row["label"] == "'REPLAY / SIMULATED OUTPUT" for row in rows)


def test_api_variants_comparison_exports_security_and_corruption(tmp_path):
    db = tmp_path / "compare.sqlite3"
    with TestClient(create_app(db), base_url="http://127.0.0.1:8765") as client:
        token = client.get("/api/session").json()["csrf_token"]
        client.headers["X-CSRF-Token"] = token
        variants = client.get("/api/variants").json()
        assert [v["id"] for v in variants] == ["baseline-v1", "mixed-v1"]
        a = client.post("/api/runs").json()
        b = client.post("/api/runs?variant=mixed-v1").json()
        query = f"?a={a['id']}&b={b['id']}"
        report = client.get("/api/comparisons" + query).json()
        assert report["counts"]["regression"] == 2
        for fmt in ("csv", "json"):
            response = client.get("/api/comparisons/export" + query + "&format=" + fmt)
            assert response.status_code == 200
            assert response.headers["content-disposition"].endswith(f'.{fmt}"')
            assert response.headers["x-content-type-options"] == "nosniff"
            assert response.headers["cache-control"] == "no-store"
            if fmt == "json":
                assert json.loads(response.content) == report
        assert client.post("/api/runs?variant=../../secret").status_code == 422
        assert client.post("/api/runs?variant=mixed-v1", json={}).status_code == 413
        for path in (
            "/api/variants",
            "/api/comparisons" + query,
            "/api/comparisons/export" + query,
        ):
            assert client.get(path, headers={"Origin": "null"}).status_code == 403
            assert client.get(path, headers={"Sec-Fetch-Mode": "navigate"}).status_code == 403
            assert client.get(path, headers={"Host": "evil.example"}).status_code == 400
        assert client.get("/api/comparisons?a=invalid&b=invalid").status_code == 422
    with TestClient(create_app(db), base_url="http://127.0.0.1:8765") as client:
        assert client.get("/api/comparisons" + query).json() == report
        store = Store(db)
        with store.engine.begin() as connection:
            connection.execute(
                update(store.runs).where(store.runs.c.id == b["id"]).values(snapshot='{ "PRIVATE":')
            )
        store.close()
        response = client.get("/api/comparisons" + query)
        assert response.status_code == 409 and "PRIVATE" not in response.text
