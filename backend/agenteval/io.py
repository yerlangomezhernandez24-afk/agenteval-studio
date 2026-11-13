"""Bounded JSON input and explicit local paths; never load executable plugins."""

import hashlib
import json
from importlib.resources import files
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agenteval.local_models import LocalRun

from pathlib import Path
from typing import Any

from agenteval.models import Run, Suite

MAX_SUITE_BYTES = 1_000_000


def reject_constant(value: str) -> None:
    raise ValueError(f"Non-JSON constant: {value}")


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def parse_json(raw: str) -> Any:
    return json.loads(raw, parse_constant=reject_constant, object_pairs_hook=unique_object)


def digest(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def parse_suite(raw: bytes) -> Suite:
    if len(raw) > MAX_SUITE_BYTES:
        raise ValueError("Suite exceeds 1 MB")
    try:
        return Suite.model_validate(parse_json(raw.decode("utf-8")))
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("Invalid UTF-8 or excessive nesting") from exc


def checked_path(path: Path, suffix: str) -> Path:
    if path.is_reserved() or (path.drive and not path.root):
        raise ValueError("Reserved and drive-relative paths are not supported")
    if ".." in path.parts or path.suffix.lower() != suffix:
        raise ValueError(f"Expected a {suffix} path without parent traversal")
    if any(part.is_symlink() or part.is_junction() for part in [path, *path.parents]):
        raise ValueError("Symlinks and junctions are not supported")
    if str(path).startswith(("\\\\", "//")) or ":" in str(path)[2:]:
        raise ValueError("Network paths and alternate streams are not supported")
    return path


def load_suite(path: Path | None = None) -> Suite:
    if path is None:
        original = parse_suite(files("agenteval").joinpath("data/support-v1.json").read_bytes())
        return original.model_copy(update={"criteria_version": "1.1"})
    checked_path(path, ".json")
    with path.open("rb") as source:
        return parse_suite(source.read(MAX_SUITE_BYTES + 1))


def export_run(run: "Run | LocalRun", path: Path) -> None:
    checked_path(path, ".json")
    # Exclusive creation: exporting never silently overwrites another report.
    with path.open("x", encoding="utf-8", newline="\n") as target:
        target.write(run.model_dump_json(indent=2))
        target.write("\n")
