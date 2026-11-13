"""Strict versioned contracts and bounded, non-executable input data."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Identifier = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$")]
Category = Literal["network", "account", "hardware", "software", "other"]
Priority = Literal["low", "medium", "high"]
Criterion = Literal["json_valid", "schema_valid", "category", "priority", "escalation", "content"]
Outcome = Literal["pass", "fail", "not_evaluable"]
Status = Literal["passed", "failed", "error", "skipped", "not_evaluable"]
REQUIRED: tuple[Criterion, ...] = (
    "json_valid",
    "schema_valid",
    "category",
    "priority",
    "escalation",
    "content",
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Expected(StrictModel):
    category: Category
    priority: Priority
    requires_human: bool


class LegacyResponse(Expected):
    summary: str = Field(min_length=1, max_length=2000)


class Response(LegacyResponse):
    @field_validator("summary")
    @classmethod
    def meaningful_summary(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Summary must contain non-whitespace text")
        return value


class Case(StrictModel):
    id: Identifier
    name: str = Field(min_length=1, max_length=160)
    input: str = Field(min_length=1, max_length=8000)
    expected: Expected
    rationale: str = Field(min_length=1, max_length=2000)
    category: Category
    tags: list[Identifier] = Field(max_length=20)
    criticality: Literal["normal", "critical"] = "normal"
    contains: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(
        default_factory=list, max_length=20
    )
    excludes: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(
        default_factory=list, max_length=20
    )


class ReplayRecord(StrictModel):
    kind: Literal["response", "timeout", "provider_error", "skipped"] = "response"
    output: str | None = Field(default=None, max_length=16000)
    note: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def valid_payload(self) -> "ReplayRecord":
        if self.kind == "response" and self.output is None:
            raise ValueError("A response needs output; use empty string to test absent content")
        if self.kind != "response" and self.output is not None:
            raise ValueError("Non-response records cannot contain output")
        return self


class Suite(StrictModel):
    id: Identifier
    version: Identifier
    synthetic: Literal[True]
    description: str = Field(min_length=1, max_length=2000)
    criteria_version: Literal["1.0", "1.1"]
    criteria: list[Criterion] = Field(min_length=6, max_length=6)
    prompt_version: Identifier
    prompt: str = Field(min_length=1, max_length=8000)
    replay_version: Identifier
    cases: list[Case] = Field(min_length=1, max_length=60)
    replay: dict[Identifier, ReplayRecord] = Field(min_length=1, max_length=60)

    @model_validator(mode="after")
    def consistency(self) -> "Suite":
        ids = [case.id for case in self.cases]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate case IDs")
        if set(self.criteria) != set(REQUIRED):
            raise ValueError("Criteria v1.0 requires all six independent criteria exactly once")
        if set(ids) != set(self.replay):
            raise ValueError("Replay keys must exactly match case IDs; omissions must be explicit")
        return self


class Check(StrictModel):
    criterion: Criterion
    outcome: Outcome
    reason: str


class CaseResult(StrictModel):
    case_id: Identifier
    status: Status
    checks: list[Check]
    raw_output: str | None
    latency_ms: float | None
    error_code: str | None = None
    reason: str


class Rate(StrictModel):
    numerator: int
    denominator: int
    percent: float | None
    not_evaluable: int


class Metrics(StrictModel):
    total: int
    executed: int
    passed: int
    failed: int
    errors: int
    skipped: int
    not_evaluable: int
    pass_rate: Rate
    criteria: dict[str, Rate]
    error_distribution: dict[str, int]
    critical_failures: list[str]
    latency_samples: int
    latency_median_ms: float | None
    latency_p95_ms: float | None


class Run(StrictModel):
    id: str
    created_utc: str
    engine_version: str
    provider: Literal["ReplayProvider"]
    label: Literal["REPLAY / SIMULATED OUTPUT"]
    model: None = None
    parameters: dict[str, str]
    dataset_hash: str
    cases_hash: str
    prompt_hash: str
    replay_hash: str
    suite: Suite
    results: list[CaseResult]
    metrics: Metrics
