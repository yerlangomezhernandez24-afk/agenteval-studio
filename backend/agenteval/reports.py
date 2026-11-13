"""Bounded comparison downloads. No raw provider outputs, paths or exception text."""

import csv
import io
from collections.abc import Sequence

from agenteval.comparison import Comparison
from agenteval.local_models import LocalRun
from agenteval.models import Run


def csv_cell(value: object) -> str:
    # Every text cell is literal, including whitespace/control-prefixed formulas.
    # CSV readers see the apostrophe; spreadsheet software treats it as text.
    if isinstance(value, str):
        return "'" + value
    if value is None:
        return ""
    if isinstance(value, (int, float, bool)):
        return str(value)
    raise TypeError("Unsupported CSV value")


def comparison_csv(report: Comparison) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\r\n")
    writer.writerow(
        [
            "report_version",
            "source_date_utc",
            "run_a",
            "run_b",
            "label",
            "warning",
            "record",
            "case_id",
            "name",
            "criterion",
            "critical",
            "a_status",
            "b_status",
            "a_error",
            "b_error",
            "a_value",
            "b_value",
            "change",
            "a_numerator",
            "a_denominator",
            "b_numerator",
            "b_denominator",
            "delta_pp",
        ]
    )
    prefix = [
        report.report_version,
        report.source_date_utc,
        report.a_id,
        report.b_id,
        report.label,
        report.warning,
    ]

    def row(values: Sequence[object]) -> None:
        writer.writerow([csv_cell(value) for value in [*prefix, *values]])

    for reason in report.reasons:
        row(["incompatible", "", reason] + [""] * 14)
    for name, rate in report.rates.items():
        row(
            [
                "metric",
                "",
                "",
                name,
                "",
                "",
                "",
                "",
                "",
                rate.a.percent,
                rate.b.percent,
                "",
                rate.a.numerator,
                rate.a.denominator,
                rate.b.numerator,
                rate.b.denominator,
                rate.percentage_points,
            ]
        )
    for name in ("passed", "failed", "errors", "skipped", "not_evaluable"):
        row(
            [
                "status_count",
                "",
                "",
                name,
                "",
                "",
                "",
                "",
                "",
                getattr(report.metrics_a, name),
                getattr(report.metrics_b, name),
                "",
            ]
            + [""] * 5
        )
    for case in report.cases:
        common = [
            case.case_id,
            case.name,
            "",
            case.critical,
            case.a_status,
            case.b_status,
            case.a_error,
            case.b_error,
        ]
        row(["case", *common, case.latency_a_ms, case.latency_b_ms, case.change] + [""] * 5)
        for check in case.checks:
            row(
                [
                    "check",
                    case.case_id,
                    case.name,
                    check.criterion,
                    case.critical,
                    case.a_status,
                    case.b_status,
                    case.a_error,
                    case.b_error,
                    check.a,
                    check.b,
                    check.change,
                ]
                + [""] * 5
            )
    return stream.getvalue()


def run_csv(run: "Run | LocalRun") -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\r\n")
    writer.writerow(
        [
            "run_id",
            "label",
            "provenance",
            "model",
            "case_id",
            "status",
            "error_code",
            "criterion",
            "outcome",
            "http_or_replay_ms",
        ]
    )
    for result in run.results:
        for check in result.checks:
            writer.writerow(
                [
                    csv_cell(value)
                    for value in [
                        run.id,
                        run.label,
                        getattr(run, "provenance", "deterministic_replay"),
                        run.model,
                        result.case_id,
                        result.status,
                        result.error_code,
                        check.criterion,
                        check.outcome,
                        result.latency_ms,
                    ]
                ]
            )
    return stream.getvalue()
