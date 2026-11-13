"""Build the public Windows ZIP from tracked source and freshly built artifacts."""

import hashlib
import json
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

root = Path(__file__).resolve().parents[1]
paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode().split("\0")
files = {name: (root / name).read_bytes() for name in paths if name}
for folder in ["dist", "frontend/dist"]:
    for path in (root / folder).rglob("*"):
        if path.is_file() and (folder != "dist" or path.suffix == ".whl"):
            files[path.relative_to(root).as_posix()] = path.read_bytes()
manifest = {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}
files["manifest.sha256.json"] = (json.dumps({"files": manifest}, indent=2) + "\n").encode()
target = root / "reports/AgentEval-Studio-v0.5.0-Windows.zip"
target.parent.mkdir(exist_ok=True)
with ZipFile(target, "x", ZIP_DEFLATED) as bundle:
    for name, data in sorted(files.items()):
        item = ZipInfo(name, date_time=(2026, 11, 12, 0, 0, 0))
        item.compress_type = ZIP_DEFLATED
        bundle.writestr(item, data)
with ZipFile(target) as bundle:
    assert bundle.testzip() is None
    assert all(hashlib.sha256(bundle.read(n)).hexdigest() == h for n, h in manifest.items())
digest = hashlib.sha256(target.read_bytes()).hexdigest()
Path(str(target) + ".sha256").write_text(digest + "  " + target.name + "\n")
print(digest)
