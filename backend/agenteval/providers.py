"""Replay is fixture lookup, never inference. Providers do not see expected labels."""

from typing import Protocol

from agenteval.models import ReplayRecord


class ProviderTimeout(Exception):
    pass


class ProviderError(Exception):
    pass


class CaseSkipped(Exception):
    pass


class Provider(Protocol):
    def respond(self, case_id: str, input_text: str, prompt: str) -> str: ...


class ReplayProvider:
    def __init__(self, records: dict[str, ReplayRecord]) -> None:
        self.records = {key: value.model_copy(deep=True) for key, value in records.items()}

    def respond(self, case_id: str, input_text: str, prompt: str) -> str:
        record = self.records[case_id]
        if record.kind == "timeout":
            raise ProviderTimeout("Synthetic timeout; no network request or waiting")
        if record.kind == "provider_error":
            raise ProviderError("Synthetic provider failure")
        if record.kind == "skipped":
            raise CaseSkipped("Explicit synthetic omission")
        assert record.output is not None
        return record.output
