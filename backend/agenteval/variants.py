"""Installed replay variants only; cases, labels, prompt and evaluator are unchanged."""

from importlib.resources import files
from typing import Literal

from agenteval.io import digest, load_suite, parse_json
from agenteval.models import Identifier, ReplayRecord, StrictModel, Suite

VariantId = Literal["baseline-v1", "mixed-v1"]


class ReplayVariant(StrictModel):
    id: Literal["mixed-v1"]
    replay_version: Identifier
    description: str
    changes: dict[str, ReplayRecord]


def load_variant(variant: VariantId = "baseline-v1") -> Suite:
    suite = load_suite()
    if variant == "baseline-v1":
        return suite
    if variant != "mixed-v1":
        raise ValueError("Unknown installed variant")
    definition = ReplayVariant.model_validate(
        parse_json(files("agenteval").joinpath("data/replay-mixed-v1.json").read_text("utf-8"))
    )
    if not set(definition.changes) <= set(suite.replay):
        raise ValueError("Variant references unknown case")
    suite.replay.update(definition.changes)
    suite.replay_version = definition.replay_version
    return Suite.model_validate(suite.model_dump())


def catalog() -> list[dict[str, str]]:
    result = []
    for variant in ("baseline-v1", "mixed-v1"):
        suite = load_variant(variant)
        result.append(
            {
                "id": variant,
                "name": "Base histórica" if variant == "baseline-v1" else "Variante mixta",
                "replay_version": suite.replay_version,
                "cases_hash": digest([case.model_dump() for case in suite.cases]),
                "replay_hash": digest(
                    {key: value.model_dump() for key, value in suite.replay.items()}
                ),
            }
        )
    return result
