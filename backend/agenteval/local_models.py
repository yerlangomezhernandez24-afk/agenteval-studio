"""Explicit v2 local inference contract; the historical Run remains untouched."""

from typing import Annotated, Literal

from pydantic import Field

from agenteval.models import CaseResult, Metrics, StrictModel, Suite

ModelName = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}$")]
Hash = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Provenance = Literal["local_ollama", "http_test_double"]
PromptId = Literal["support-json-v1", "support-concise-v1"]
TransportCode = Literal[
    "response",
    "timeout",
    "connection_error",
    "http_error",
    "invalid_response",
    "limit_exceeded",
    "cancelled",
    "not_started",
]


class ModelInfo(StrictModel):
    name: ModelName
    digest: Hash
    size: int = Field(gt=0, le=1_000_000_000_000)
    modified_at: str = Field(min_length=1, max_length=64)
    family: str = Field(default="", max_length=80)
    parameter_size: str = Field(default="", max_length=40)
    quantization_level: str = Field(default="", max_length=40)


class GenerationOptions(StrictModel):
    temperature: float = Field(default=0.0, ge=0, le=1, allow_inf_nan=False)
    seed: int = Field(default=42, ge=0, le=2_147_483_647)
    num_predict: int = Field(default=64, ge=16, le=128)
    num_ctx: Literal[2048] = 2048


class Attempt(StrictModel):
    case_id: str
    code: TransportCode
    elapsed_ms: float | None = Field(default=None, ge=0, le=120_000, allow_inf_nan=False)
    generation_duration_ns: int | None = Field(default=None, ge=0, le=120_000_000_000)
    total_duration_ns: int | None = Field(default=None, ge=0, le=120_000_000_000)
    eval_count: int | None = Field(default=None, ge=0, le=128)


class LocalRun(StrictModel):
    snapshot_version: Literal[2] = 2
    id: str
    created_utc: str
    engine_version: Literal["0.2.0-local"] = "0.2.0-local"
    evaluator_version: Literal["1.1"] = "1.1"
    provider: Literal["OllamaLocal"] = "OllamaLocal"
    label: Literal["LOCAL LLM / EXPERIMENTAL"] = "LOCAL LLM / EXPERIMENTAL"
    provenance: Provenance
    model: ModelName
    model_info: ModelInfo
    ollama_version: str | None = Field(default=None, max_length=80)
    options: GenerationOptions
    parameters: dict[str, str]
    completion: Literal["completed", "cancelled"]
    dataset_hash: Hash
    cases_hash: Hash
    prompt_hash: Hash
    replay_hash: Literal["not-applicable"] = "not-applicable"
    suite: Suite
    attempts: list[Attempt] = Field(min_length=3, max_length=3)
    results: list[CaseResult] = Field(min_length=3, max_length=3)
    metrics: Metrics
    snapshot_hash: Hash
