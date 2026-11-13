"""An existing audit archive must be refused before any manifest mutation."""

import runpy
from pathlib import Path

import pytest


def test_existing_corrected_archive_and_manifest_are_never_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = Path(__file__).resolve().parents[1] / "scripts/package_phase2.py"
    main = runpy.run_path(str(script))["main"]
    monkeypatch.setitem(main.__globals__, "__file__", str(tmp_path / "scripts/package_phase2.py"))
    target = tmp_path / "reports/agenteval-phase2-audit-corrected.zip"
    target.parent.mkdir()
    target.write_bytes(b"existing immutable archive")
    manifest = tmp_path / "docs/evidence-phase2-corrected/bundle-manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_bytes(b"existing immutable manifest")
    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        main()
    assert target.read_bytes() == b"existing immutable archive"
    assert manifest.read_bytes() == b"existing immutable manifest"
