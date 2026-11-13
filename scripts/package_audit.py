"""Corrected audit archive: preserve original, redact local paths, verify CRC and hashes."""

import hashlib
import json
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ORIGINAL_SHA256 = "62ed563d3f70f2161a0867de95f4e561f29d7d60331d3fc2b6480e69a761067d"


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    original = root / "reports/agenteval-phase1-audit.zip"
    assert hashlib.sha256(original.read_bytes()).hexdigest() == ORIGINAL_SHA256
    wheel = root / "dist/agenteval_studio-0.1.1-py3-none-any.whl"
    with ZipFile(wheel) as archive, ZipFile(original) as historic:
        fixture = "backend/agenteval/data/support-v1.json"
        assert archive.read("agenteval/data/support-v1.json") == (root / fixture).read_bytes()
        assert historic.read(fixture) == (root / fixture).read_bytes()
        for lock in ("requirements.lock", "requirements-dev.lock"):
            assert historic.read(lock) == (root / lock).read_bytes()
        for path in (root / "backend/agenteval").glob("*.py"):
            assert archive.read(f"agenteval/{path.name}") == path.read_bytes()

    paths = [
        root / name
        for name in (
            ".gitignore",
            "pyproject.toml",
            "requirements.lock",
            "requirements-dev.lock",
            "README.md",
            "README.en.md",
        )
    ]
    suffixes = {".py", ".json", ".md", ".ps1", ".txt", ".xml", ".log"}
    manifest_path = root / "docs/evidence-corrected/bundle-manifest.json"
    for directory in ("backend", "tests", "docs", "datasets", "scripts"):
        for path in (root / directory).rglob("*"):
            if not path.is_file() or path.suffix not in suffixes or path == manifest_path:
                continue
            if "__pycache__" in path.parts:
                continue
            if path.is_relative_to(root / "docs/evidence"):
                # Keep just original snapshots required for historical regression tests.
                if path.name not in {"replay-a.json", "replay-b.json"}:
                    continue
            paths.append(path)

    payloads: dict[str, bytes] = {}
    redacted = []
    for path in sorted(paths):
        assert not path.is_symlink()
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            # Initial Windows server log used the system CP1252 locale.
            if path.name != "http-server.log":
                raise
            text = raw.decode("cp1252")
        for local in (str(root), root.as_posix(), str(root).replace("\\", "\\\\")):
            text = text.replace(local, "<PROJECT>")
        if path.suffix == ".xml":
            text = re.sub(r'hostname="[^"]*"', 'hostname="redacted"', text)
        if text.encode("utf-8") != raw:
            redacted.append(path.relative_to(root).as_posix())
        assert not re.search(r"[A-Za-z]:(?:\\|/)+Users(?:\\|/)", text)
        assert "-----BEGIN " + "PRIVATE KEY-----" not in text
        assert not re.search(r"(?:ghp_|sk_live_)[A-Za-z0-9]{20,}", text)
        payloads[path.relative_to(root).as_posix()] = text.encode("utf-8")
    payloads[wheel.relative_to(root).as_posix()] = wheel.read_bytes()
    manifest = {
        "original_zip_sha256": ORIGINAL_SHA256,
        "redacted_or_utf8_normalized_files": redacted,
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in payloads.items()},
    }
    manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode()
    manifest_path.write_bytes(manifest_bytes)
    payloads[manifest_path.relative_to(root).as_posix()] = manifest_bytes
    target = root / "reports/agenteval-phase1-audit-corrected.zip"
    # Exclusive creation: neither original nor an existing corrected archive is overwritten.
    with ZipFile(target, "x", ZIP_DEFLATED) as archive:
        for name, data in payloads.items():
            archive.writestr(name, data)
    with ZipFile(target) as archive:
        assert archive.testzip() is None
        for name, expected in manifest["files"].items():
            assert hashlib.sha256(archive.read(name)).hexdigest() == expected
    assert hashlib.sha256(original.read_bytes()).hexdigest() == ORIGINAL_SHA256
    sha = hashlib.sha256(target.read_bytes()).hexdigest()
    target.with_suffix(".zip.sha256").write_text(f"{sha}  {target.name}\n", encoding="utf-8")
    print(f"Verified {len(payloads)} entries, CRC, manifest, original ZIP and fixture unchanged.")
    print(f"SHA256: {sha}")


if __name__ == "__main__":
    main()
