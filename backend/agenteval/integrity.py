"""Detect internal inconsistency, not authenticity against a malicious database owner."""

from datetime import datetime, timedelta
from math import isfinite
from uuid import UUID

from agenteval.engine import run_suite
from agenteval.io import digest, parse_json
from agenteval.local_models import LocalRun
from agenteval.local_snapshot import verify_local
from agenteval.metrics import aggregate
from agenteval.models import Run


class SnapshotCorruption(ValueError):
    """Stored JSON or versioned invariants are invalid. Never expose its content."""


def restore(raw: str, row_id: str, row_created: str) -> Run | LocalRun:
    try:
        data = parse_json(raw)
        if isinstance(data, dict) and (
            data.get("provider") == "OllamaLocal" or "snapshot_version" in data
        ):
            local = LocalRun.model_validate(data)
            verify_local(local, row_id, row_created)
            return local
        run = Run.model_validate(data)
        verify(run, row_id, row_created)
        return run
    except (ValueError, TypeError, KeyError, RecursionError, OverflowError) as exc:
        raise SnapshotCorruption("Stored snapshot integrity check failed") from exc


def verify(run: Run, row_id: str, row_created: str) -> None:
    if run.id != row_id or str(UUID(run.id)) != run.id or run.created_utc != row_created:
        raise ValueError("Row metadata mismatch")
    if datetime.fromisoformat(run.created_utc).utcoffset() != timedelta(0):
        raise ValueError("UTC required")
    if run.engine_version not in {"0.1.0", "0.1.1"}:
        raise ValueError("Unsupported engine version")
    if run.engine_version == "0.1.0" and run.suite.criteria_version != "1.0":
        raise ValueError("Unsupported historical criteria")
    expected = run_suite(run.suite)
    for name in ("dataset_hash", "cases_hash", "prompt_hash", "replay_hash", "parameters"):
        if getattr(run, name) != getattr(expected, name):
            raise ValueError("Fingerprint or provider parameters mismatch")
    if len(run.results) != len(expected.results):
        raise ValueError("Result count mismatch")
    for actual, computed in zip(run.results, expected.results, strict=True):
        if actual.model_dump(exclude={"latency_ms"}) != computed.model_dump(exclude={"latency_ms"}):
            raise ValueError("Result, raw output or check mismatch")
        latency = actual.latency_ms
        if actual.status == "skipped":
            if latency is not None:
                raise ValueError("Skipped latency must be absent")
        elif latency is None or not isfinite(latency) or latency < 0:
            raise ValueError("Invalid measured latency")
    if digest(run.metrics.model_dump()) != digest(aggregate(run.suite, run.results).model_dump()):
        raise ValueError("Stored metrics mismatch")
