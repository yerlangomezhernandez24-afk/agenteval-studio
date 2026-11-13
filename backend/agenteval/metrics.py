"""Explicit denominators; no infrastructure errors hidden as model errors."""

from collections import Counter
from math import ceil
from statistics import median

from agenteval.models import REQUIRED, CaseResult, Metrics, Rate, Suite


def rate(passed: int, assessed: int, na: int) -> Rate:
    return Rate(
        numerator=passed,
        denominator=assessed,
        percent=100.0 * passed / assessed if assessed else None,
        not_evaluable=na,
    )


def aggregate(suite: Suite, results: list[CaseResult]) -> Metrics:
    if [r.case_id for r in results] != [c.id for c in suite.cases]:
        raise ValueError("Results must correspond exactly to suite cases in order")
    counts = Counter(r.status for r in results)
    criteria: dict[str, Rate] = {}
    for name in REQUIRED:
        outcomes = Counter(c.outcome for r in results for c in r.checks if c.criterion == name)
        assessed = outcomes["pass"] + outcomes["fail"]
        criteria[name] = rate(outcomes["pass"], assessed, len(results) - assessed)
    # Retrieval duration, including synthetic error paths. Never LLM inference latency.
    durations = sorted(r.latency_ms for r in results if r.latency_ms is not None)
    critical = {c.id for c in suite.cases if c.criticality == "critical"}
    assessed = counts["passed"] + counts["failed"]
    return Metrics(
        total=len(results),
        executed=len(results) - counts["skipped"],
        passed=counts["passed"],
        failed=counts["failed"],
        errors=counts["error"],
        skipped=counts["skipped"],
        not_evaluable=counts["not_evaluable"],
        pass_rate=rate(counts["passed"], assessed, len(results) - assessed),
        criteria=criteria,
        error_distribution=dict(Counter(r.error_code for r in results if r.error_code)),
        critical_failures=[
            r.case_id for r in results if r.case_id in critical and r.status != "passed"
        ],
        latency_samples=len(durations),
        latency_median_ms=float(median(durations)) if durations else None,
        latency_p95_ms=durations[ceil(0.95 * len(durations)) - 1] if len(durations) >= 20 else None,
    )
