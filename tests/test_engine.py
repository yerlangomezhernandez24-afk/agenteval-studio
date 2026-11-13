import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from agenteval.engine import run_suite
from agenteval.evaluators import evaluate
from agenteval.io import MAX_SUITE_BYTES, digest, export_run, load_suite, parse_suite
from agenteval.metrics import aggregate
from agenteval.models import Suite
from agenteval.storage import Store


@pytest.fixture
def suite():
    return load_suite()


def outcomes(suite, name, raw):
    case = next(c for c in suite.cases if c.id == name)
    return {c.criterion: c.outcome for c in evaluate(case, raw, suite.criteria_version)}


@pytest.mark.parametrize(
    "mutation",
    [
        "empty",
        "duplicate",
        "unknown",
        "extra",
        "too_many",
        "missing_replay",
        "bad_bool",
        "non_synthetic",
    ],
)
def test_reject_invalid_suites(suite, mutation):
    data = suite.model_dump()
    if mutation == "empty":
        data["cases"] = []
    elif mutation == "duplicate":
        data["cases"][1]["id"] = data["cases"][0]["id"]
    elif mutation == "unknown":
        data["criteria"][0] = "magic_security"
    elif mutation == "extra":
        data["executable"] = "evil.py"
    elif mutation == "too_many":
        data["cases"] *= 2
    elif mutation == "missing_replay":
        del data["replay"]["vpn"]
    elif mutation == "bad_bool":
        data["cases"][0]["expected"]["requires_human"] = "false"
    else:
        data["synthetic"] = False
    with pytest.raises(ValidationError):
        Suite.model_validate(data)


@pytest.mark.parametrize(
    "raw", [b"{", b"\xff", b"{}", b"[]", b'{"x":1,"x":2}', b'{"x":NaN}', b"[" * 2000]
)
def test_malformed_import(raw):
    with pytest.raises(ValueError):
        parse_suite(raw)


def test_size_limit():
    with pytest.raises(ValueError, match="1 MB"):
        parse_suite(b" " * (MAX_SUITE_BYTES + 1))


@pytest.mark.parametrize(
    "path", ["../suite.json", "suite.py", "bad.json:stream", "//host/file.json"]
)
def test_invalid_paths(path):
    with pytest.raises(ValueError):
        load_suite(Path(path))


def test_correct_response(suite):
    result = outcomes(suite, "vpn", suite.replay["vpn"].output)
    assert result == dict(
        json_valid="pass",
        schema_valid="pass",
        category="pass",
        priority="pass",
        escalation="pass",
        content="not_evaluable",
    )


@pytest.mark.parametrize(
    "case_id,criterion",
    [
        ("monitor", "schema_valid"),
        ("licenses", "schema_valid"),
        ("disk", "priority"),
        ("mouse", "schema_valid"),
        ("dns", "json_valid"),
        ("browser", "json_valid"),
        ("wifi", "category"),
        ("payroll", "priority"),
        ("locked-admin", "escalation"),
        ("secret-leak", "content"),
        ("format-attack", "json_valid"),
        ("missing-text", "content"),
        ("duplicate-key", "json_valid"),
        ("array", "schema_valid"),
        ("bad-enum", "category"),
        ("number-summary", "schema_valid"),
    ],
)
def test_intentional_failures(suite, case_id, criterion):
    assert outcomes(suite, case_id, suite.replay[case_id].output)[criterion] == "fail"


def test_independent_checks(suite):
    result = outcomes(suite, "number-summary", suite.replay["number-summary"].output)
    assert result["schema_valid"] == "fail"
    assert result["category"] == "pass"
    invalid = outcomes(suite, "dns", suite.replay["dns"].output)
    assert invalid["schema_valid"] == "not_evaluable"
    assert invalid["category"] == "not_evaluable"


def test_text_rules_are_literal_case_insensitive(suite):
    # Preserve the original historical v1.0 oracle explicitly.
    suite = suite.model_copy(update={"criteria_version": "1.0"})
    assert outcomes(suite, "required-text", "HUMAN REVIEW")["content"] == "pass"
    assert outcomes(suite, "secret-leak", "fake_secret_canary")["content"] == "fail"
    assert outcomes(suite, "secret-leak", "different marker")["content"] == "pass"


def test_exact_metrics_and_statuses(suite):
    run = run_suite(suite)
    m = run.metrics
    assert (m.total, m.executed, m.passed, m.failed, m.errors, m.skipped, m.not_evaluable) == (
        36,
        35,
        16,
        16,
        2,
        1,
        1,
    )
    assert m.pass_rate.numerator == 16
    assert m.pass_rate.denominator == 32
    assert m.pass_rate.percent == 50
    assert m.criteria["json_valid"].denominator == 32
    assert m.criteria["json_valid"].numerator == 28
    assert m.criteria["schema_valid"].denominator == 28
    assert m.criteria["schema_valid"].numerator == 21
    assert m.criteria["category"].denominator == 27
    assert m.criteria["category"].numerator == 25
    assert m.criteria["priority"].numerator == 25
    assert m.criteria["priority"].denominator == 27
    assert m.criteria["escalation"].numerator == 25
    assert m.criteria["escalation"].denominator == 26
    assert m.criteria["content"].numerator == 2
    assert m.criteria["content"].denominator == 4
    assert m.error_distribution == {"timeout": 1, "provider_error": 1}
    by_id = {r.case_id: r for r in run.results}
    assert by_id["calendar"].status == "error"
    assert by_id["scanner"].status == "error"
    assert by_id["scheduled"].status == "skipped"
    assert by_id["scheduled"].latency_ms is None
    assert by_id["empty"].status == "not_evaluable"
    assert set(m.critical_failures) == {
        "disk",
        "payroll",
        "locked-admin",
        "secret-leak",
        "missing-text",
    }
    assert m.latency_samples == 35
    assert m.latency_p95_ms is not None


def test_zero_denominator_and_small_latency_sample(suite):
    data = suite.model_dump()
    data["cases"] = [data["cases"][23]]  # explicit skipped scenario
    data["replay"] = {"scheduled": data["replay"]["scheduled"]}
    run = run_suite(Suite.model_validate(data))
    assert run.metrics.pass_rate.percent is None
    assert run.metrics.pass_rate.denominator == 0
    assert run.metrics.latency_median_ms is None
    assert run.metrics.latency_p95_ms is None
    data["replay"]["scheduled"] = dict(kind="response", output="{}", note="Invalid response")
    assert run_suite(Suite.model_validate(data)).metrics.latency_p95_ms is None


def test_reproducible_outcomes_and_snapshot(suite):
    a, b = run_suite(suite), run_suite(suite)
    assert a.id != b.id
    assert a.dataset_hash == b.dataset_hash
    assert a.prompt_hash == b.prompt_hash
    assert [r.model_dump(exclude={"latency_ms"}) for r in a.results] == [
        r.model_dump(exclude={"latency_ms"}) for r in b.results
    ]
    suite.cases[0].input = "Modified later"
    assert a.suite.cases[0].input != suite.cases[0].input
    assert a.cases_hash != digest([c.model_dump() for c in suite.cases])


def test_aggregation_rejects_missing_and_reordered_results(suite):
    run = run_suite(suite)
    with pytest.raises(ValueError):
        aggregate(suite, run.results[:-1])
    with pytest.raises(ValueError):
        aggregate(suite, list(reversed(run.results)))


def test_persistence_restart_and_duplicate_protection(suite, tmp_path):
    from sqlalchemy.exc import IntegrityError

    path = tmp_path / "history.sqlite3"
    run = run_suite(suite)
    store = Store(path)
    store.save(run)
    with pytest.raises(IntegrityError):
        store.save(run)
    store.close()
    reopened = Store(path)
    assert reopened.get(run.id) == run
    assert reopened.list_ids() == [run.id]
    reopened.close()


def test_json_export_preserves_content_without_execution(suite, tmp_path):
    suite.replay["vpn"].output = '=HYPERLINK("fake")'
    run = run_suite(suite)
    output = tmp_path / "report.json"
    export_run(run, output)
    assert json.loads(output.read_text(encoding="utf-8"))["results"][0]["raw_output"].startswith(
        "="
    )
    with pytest.raises(FileExistsError):
        export_run(run, output)


def test_no_network_required(suite, monkeypatch):
    import socket

    def forbidden(*args, **kwargs):
        raise AssertionError("Network is forbidden for replay")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    assert run_suite(suite).metrics.total == 36
