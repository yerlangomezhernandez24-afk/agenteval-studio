"""Deterministic comparisons of verified snapshots; no transport or persistence."""

from typing import Literal

from agenteval.local_models import LocalRun
from agenteval.models import REQUIRED, CaseResult, Metrics, Outcome, Rate, Run, StrictModel

Change = Literal["improvement", "regression", "unchanged", "not_comparable"]
WARNING = (
    "REPLAY / SIMULATED OUTPUT. Datos sintéticos; latencia de replay local, no inferencia. "
    "Sin significación estadística ni certificación universal de seguridad."
)


class CheckDelta(StrictModel):
    criterion: str
    a: Outcome
    b: Outcome
    change: Change


class CaseDelta(StrictModel):
    case_id: str
    name: str
    critical: bool
    a_status: str
    b_status: str
    a_error: str | None
    b_error: str | None
    change: Change
    checks: list[CheckDelta]
    latency_a_ms: float | None
    latency_b_ms: float | None


class RateDelta(StrictModel):
    a: Rate
    b: Rate
    numerator_delta: int
    denominator_delta: int
    percentage_points: float | None


class Comparison(StrictModel):
    report_version: Literal["1.0"] = "1.0"
    source_date_utc: str
    label: Literal[
        "REPLAY / SIMULATED OUTPUT", "LOCAL LLM / EXPERIMENTAL", "MIXED / INCOMPATIBLE"
    ] = "REPLAY / SIMULATED OUTPUT"
    warning: str = WARNING
    a_id: str
    b_id: str
    compatible: bool
    reasons: list[str]
    fingerprints: dict[str, dict[str, str]]
    metrics_a: Metrics
    metrics_b: Metrics
    rates: dict[str, RateDelta]
    counts: dict[str, int]
    critical_regressions: list[str]
    critical_attention: list[str]
    cases: list[CaseDelta]


def compatibility(a: Run | LocalRun, b: Run | LocalRun) -> list[str]:
    reasons = []
    if a.provider != b.provider:
        reasons.append("Proveedores distintos: replay y LLM no se comparan.")
    if isinstance(a, LocalRun) and isinstance(b, LocalRun):
        if a.provenance != b.provenance:
            reasons.append("Procedencias distintas: doble HTTP y modelo real.")
        if a.completion != "completed" or b.completion != "completed":
            reasons.append("Ejecución parcial cancelada no comparable.")
    if (a.suite.id, a.suite.version) != (b.suite.id, b.suite.version):
        reasons.append("Identidad o versión de suite distinta.")
    if a.cases_hash != b.cases_hash or a.suite.cases != b.suite.cases:
        reasons.append("Casos, etiquetas o cases_hash distintos.")
    if a.suite.criteria_version != b.suite.criteria_version:
        reasons.append("Versiones de criterios distintas; 1.0 es histórico y no equivale a 1.1.")
    if set(a.suite.criteria) != set(b.suite.criteria):
        reasons.append("Conjunto de criterios distinto.")
    if a.engine_version != b.engine_version or a.engine_version not in {
        "0.1.0",
        "0.1.1",
        "0.2.0-local",
    }:
        reasons.append("Semántica/versiones del motor distintas o no soportadas.")
    for label, run in (("A", a), ("B", b)):
        ids = [case.id for case in run.suite.cases]
        if [result.case_id for result in run.results] != ids:
            reasons.append(f"{label}: caso ausente, duplicado o fuera de orden en resultados.")
        if set(run.suite.criteria) != set(REQUIRED):
            reasons.append(f"{label}: criterio ausente o no soportado.")
        if any(
            len(r.checks) != len(REQUIRED) or {c.criterion for c in r.checks} != set(REQUIRED)
            for r in run.results
        ):
            reasons.append(f"{label}: check ausente o duplicado.")
    return reasons


def check_change(a: Outcome, b: Outcome) -> Change:
    if a == b:
        return "unchanged"
    if "not_evaluable" in (a, b):
        return "not_comparable"
    return "improvement" if b == "pass" else "regression"


def case_change(a: CaseResult, b: CaseResult, checks: list[CheckDelta]) -> Change:
    if a.status not in {"passed", "failed"} or b.status not in {"passed", "failed"}:
        return (
            "unchanged"
            if (a.status, a.error_code) == (b.status, b.error_code)
            else "not_comparable"
        )
    if a.status != b.status:
        return "improvement" if b.status == "passed" else "regression"
    changes = {check.change for check in checks}
    # A new failed check is never hidden by another improved check.
    for change in ("regression", "improvement", "not_comparable"):
        if change in changes:
            return change
    return "unchanged"


def rate_delta(a: Rate, b: Rate) -> RateDelta:
    return RateDelta(
        a=a,
        b=b,
        numerator_delta=b.numerator - a.numerator,
        denominator_delta=b.denominator - a.denominator,
        percentage_points=None if a.percent is None or b.percent is None else b.percent - a.percent,
    )


def compare_runs(a: Run | LocalRun, b: Run | LocalRun) -> Comparison:
    reasons = compatibility(a, b)
    cases = []
    if not reasons:
        for case, left, right in zip(a.suite.cases, a.results, b.results, strict=True):
            right_checks = {check.criterion: check for check in right.checks}
            checks = [
                CheckDelta(
                    criterion=c.criterion,
                    a=c.outcome,
                    b=right_checks[c.criterion].outcome,
                    change=check_change(c.outcome, right_checks[c.criterion].outcome),
                )
                for c in left.checks
            ]
            cases.append(
                CaseDelta(
                    case_id=case.id,
                    name=case.name,
                    critical=case.criticality == "critical",
                    a_status=left.status,
                    b_status=right.status,
                    a_error=left.error_code,
                    b_error=right.error_code,
                    change=case_change(left, right, checks),
                    checks=checks,
                    latency_a_ms=left.latency_ms,
                    latency_b_ms=right.latency_ms,
                )
            )
    rates = (
        {"pass_rate": rate_delta(a.metrics.pass_rate, b.metrics.pass_rate)} if not reasons else {}
    )
    if not reasons:
        rates.update(
            {
                name: rate_delta(a.metrics.criteria[name], b.metrics.criteria[name])
                for name in REQUIRED
            }
        )
    return Comparison(
        source_date_utc=max(a.created_utc, b.created_utc),
        label=a.label if a.provider == b.provider else "MIXED / INCOMPATIBLE",
        warning=WARNING
        if a.provider == b.provider == "ReplayProvider"
        else (
            "LOCAL LLM / EXPERIMENTAL. Sin determinismo garantizado ni significación estadística. "
            "HTTP test double no demuestra calidad de un modelo real."
        ),
        a_id=a.id,
        b_id=b.id,
        compatible=not reasons,
        reasons=reasons,
        fingerprints={
            label: {
                "cases_hash": run.cases_hash,
                "dataset_hash": run.dataset_hash,
                "replay_hash": run.replay_hash,
                "prompt_hash": run.prompt_hash,
                "engine_version": run.engine_version,
                "criteria_version": run.suite.criteria_version,
                "replay_version": run.suite.replay_version,
                "prompt_version": run.suite.prompt_version,
                "provider": run.provider,
                **(
                    {
                        "provenance": run.provenance,
                        "model": run.model,
                        "model_digest": run.model_info.digest,
                    }
                    if isinstance(run, LocalRun)
                    else {}
                ),
            }
            for label, run in (("a", a), ("b", b))
        },
        metrics_a=a.metrics,
        metrics_b=b.metrics,
        rates=rates,
        counts={
            change: sum(c.change == change for c in cases)
            for change in ("improvement", "regression", "unchanged", "not_comparable")
        },
        critical_regressions=[c.case_id for c in cases if c.critical and c.change == "regression"],
        critical_attention=[c.case_id for c in cases if c.critical and c.b_status != "passed"],
        cases=cases,
    )
