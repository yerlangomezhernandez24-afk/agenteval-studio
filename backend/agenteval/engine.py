"""Pure orchestration: no FastAPI, SQL or external services required."""

from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from agenteval import __version__
from agenteval.evaluators import evaluate
from agenteval.io import digest
from agenteval.metrics import aggregate
from agenteval.models import REQUIRED, CaseResult, Check, Run, Status, Suite
from agenteval.providers import CaseSkipped, ProviderError, ProviderTimeout, ReplayProvider


def run_suite(suite: Suite) -> Run:
    snapshot = suite.model_copy(deep=True)
    provider = ReplayProvider(snapshot.replay)
    results: list[CaseResult] = []
    for case in snapshot.cases:
        start = perf_counter()
        raw: str | None = None
        latency: float | None = None
        code: str | None = None
        status: Status
        try:
            raw = provider.respond(case.id, case.input, snapshot.prompt)
            latency = (perf_counter() - start) * 1000
            if not raw.strip():
                status, reason, checks = "not_evaluable", "No response content", []
            else:
                checks = evaluate(case, raw, snapshot.criteria_version)
                status = "failed" if any(c.outcome == "fail" for c in checks) else "passed"
                reason = "Deterministic response contract evaluation"
        except CaseSkipped:
            status, reason, checks = "skipped", "Explicit synthetic omission", []
        except ProviderTimeout:
            status, reason, checks, code = "error", "Simulated timeout", [], "timeout"
        except ProviderError:
            status, reason, checks, code = (
                "error",
                "Simulated provider failure",
                [],
                "provider_error",
            )
        if latency is None:
            latency = (perf_counter() - start) * 1000
        if not checks:
            checks = [
                Check(criterion=name, outcome="not_evaluable", reason=reason) for name in REQUIRED
            ]
        results.append(
            CaseResult(
                case_id=case.id,
                status=status,
                checks=checks,
                raw_output=raw,
                latency_ms=None if status == "skipped" else latency,
                error_code=code,
                reason=reason,
            )
        )
    return Run(
        id=str(uuid4()),
        created_utc=datetime.now(UTC).isoformat(),
        engine_version=__version__,
        provider="ReplayProvider",
        label="REPLAY / SIMULATED OUTPUT",
        parameters={"concurrency": "1", "latency": "local replay retrieval wall time only"},
        dataset_hash=digest(snapshot.model_dump()),
        cases_hash=digest([c.model_dump() for c in snapshot.cases]),
        prompt_hash=digest(snapshot.prompt),
        replay_hash=digest({k: v.model_dump() for k, v in snapshot.replay.items()}),
        suite=snapshot,
        results=results,
        metrics=aggregate(snapshot, results),
    )
