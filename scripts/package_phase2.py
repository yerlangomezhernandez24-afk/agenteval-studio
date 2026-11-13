"""Create an exclusive Phase 2 archive; verify sources, history, CRC and SHA256."""

import hashlib
import json
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

HISTORY = {
    "agenteval-phase1-audit.zip": (
        "62ed563d3f70f2161a0867de95f4e561f29d7d60331d3fc2b6480e69a761067d"
    ),
    "agenteval-phase1-audit-corrected.zip": (
        "e5ef2da42c7c4ee552bfba3e7d0686009825534152237d4b344736a91b391a08"
    ),
    "agenteval-phase2-audit.zip": (
        "8ead1ab0fc4c79f5d1b475e372c9e4f5624928a527b18fcd744d6d2d76909d96"
    ),
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    target = root / "reports/agenteval-phase2-audit-corrected.zip"
    if target.exists():
        raise FileExistsError("Phase 2 archive exists; refusing to overwrite it")
    for name, expected in HISTORY.items():
        assert sha((root / "reports" / name).read_bytes()) == expected, name
    wheel = root / "dist/agenteval_studio-0.2.0-py3-none-any.whl"
    with ZipFile(root / "reports/agenteval-phase1-audit-corrected.zip") as old:
        preserved = ["requirements.lock", "requirements-dev.lock"]
        preserved += [
            f"backend/agenteval/{name}.py"
            for name in (
                "__init__",
                "engine",
                "evaluators",
                "integrity",
                "io",
                "metrics",
                "models",
                "providers",
                "storage",
            )
        ]
        preserved.append("backend/agenteval/data/support-v1.json")
        for name in preserved:
            assert old.read(name) == (root / name).read_bytes(), name
    with ZipFile(wheel) as built:
        for source in (root / "backend/agenteval").glob("*.py"):
            assert built.read(f"agenteval/{source.name}") == source.read_bytes(), source
        assert (
            built.read("agenteval/data/support-v1.json")
            == (root / "backend/agenteval/data/support-v1.json").read_bytes()
        )

    paths = {
        root / name
        for name in (
            ".gitignore",
            "pyproject.toml",
            "requirements.lock",
            "requirements-dev.lock",
            "README.md",
            "README.en.md",
        )
    }
    suffixes = {".py", ".json", ".md", ".ps1", ".txt", ".xml", ".log"}
    manifest_path = root / "docs/evidence-phase2-corrected/bundle-manifest.json"
    for directory in ("backend", "tests", "docs", "datasets", "scripts"):
        for path in (root / directory).rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts or path == manifest_path:
                continue
            relative = path.relative_to(root).as_posix()
            if relative.startswith("docs/evidence"):
                if not relative.startswith(
                    ("docs/evidence-phase2/", "docs/evidence-phase2-corrected/")
                ) and relative not in {
                    "docs/evidence/replay-a.json",
                    "docs/evidence/replay-b.json",
                }:
                    continue
            if path.suffix in suffixes or (
                relative.startswith(
                    ("docs/evidence-phase2/screenshots/", "docs/evidence-phase2-corrected/")
                )
                and path.suffix == ".png"
            ):
                paths.add(path)
    for path in (root / "frontend").rglob("*"):
        relative = path.relative_to(root / "frontend")
        if any(
            part in {"node_modules", "test-results", "playwright-report"} for part in relative.parts
        ):
            continue
        if path.is_file() and path.suffix in {
            ".ts",
            ".tsx",
            ".js",
            ".mjs",
            ".json",
            ".css",
            ".html",
        }:
            paths.add(path)

    payloads = {}
    redacted = []
    for path in sorted(paths):
        assert not path.is_symlink(), path
        name = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        if path.suffix != ".png":
            text = raw.decode("utf-8-sig")
            for local in (str(root), root.as_posix(), str(root).replace("\\", "\\\\")):
                text = re.sub(re.escape(local), lambda _: "<PROJECT>", text, flags=re.IGNORECASE)
            # Installer logs can contain user-local temporary directories outside root.
            home = Path.home()
            for local in (str(home), home.as_posix(), str(home).replace("\\", "\\\\")):
                text = re.sub(re.escape(local), lambda _: "<USER>", text, flags=re.IGNORECASE)
            if path.suffix == ".xml":
                text = re.sub(r'hostname="[^"]*"', 'hostname="redacted"', text)
            assert not re.search(r"[A-Za-z]:(?:\\|/)+Users(?:\\|/)", text), name
            assert "-----BEGIN " + "PRIVATE KEY-----" not in text, name
            assert not re.search(r"(?:ghp_|sk_live_)[A-Za-z0-9]{20,}", text), name
            raw = text.encode("utf-8")
            if raw != path.read_bytes():
                redacted.append(name)
        payloads[name] = raw
    payloads[wheel.relative_to(root).as_posix()] = wheel.read_bytes()
    manifest = {
        "phase": 2,
        "application_version": "0.2.0",
        "engine_version": "0.1.1",
        "preserved_archives_sha256": HISTORY,
        "preserved_core_and_locks": preserved,
        "redacted_or_utf8_normalized_files": redacted,
        "files": {name: sha(data) for name, data in sorted(payloads.items())},
    }
    manifest_bytes = (json.dumps(manifest, indent=2) + "\n").encode()
    manifest_path.write_bytes(manifest_bytes)
    payloads[manifest_path.relative_to(root).as_posix()] = manifest_bytes
    with ZipFile(target, "x", ZIP_DEFLATED) as archive:
        for name, data in sorted(payloads.items()):
            archive.writestr(name, data)
    with ZipFile(target) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(payloads)
        for name, expected in manifest["files"].items():
            assert sha(archive.read(name)) == expected, name
    for name, expected in HISTORY.items():
        assert sha((root / "reports" / name).read_bytes()) == expected
    digest = sha(target.read_bytes())
    target.with_suffix(".zip.sha256").write_text(f"{digest}  {target.name}\n", encoding="utf-8")
    print(f"Verified {len(payloads)} entries, CRC and SHA256 manifest; historical ZIPs unchanged.")
    print(f"SHA256: {digest}")


if __name__ == "__main__":
    main()
