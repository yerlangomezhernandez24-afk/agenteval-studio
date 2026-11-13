"""One-command local demo. Only launches owned processes; Ctrl+C closes them."""

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="AgentEval Studio local UI")
    parser.add_argument("--dev", action="store_true", help="Start Vite and backend in development")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if not args.dev and not (root / "frontend/dist/index.html").is_file():
        print("Missing UI build. Run npm ci and npm run build inside frontend.", file=sys.stderr)
        return 2
    if args.dev and not (root / "frontend/node_modules/vite").exists():
        print("Missing frontend dependencies. Run npm ci inside frontend.", file=sys.stderr)
        return 2
    node = shutil.which("node")
    if args.dev and node is None:
        print("Node 24 required for development.", file=sys.stderr)
        return 2
    for port in [8765, 5173] if args.dev else [8765]:
        try:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", port))
        except OSError:
            print(
                f"Port {port} is occupied. Close the previous local process first.", file=sys.stderr
            )
            return 2
    backend = [
        sys.executable,
        "-m",
        "agenteval.cli",
        "serve",
        "--db",
        str(root / "data/agenteval.sqlite3"),
    ]
    backend += ["--dev-ui"] if args.dev else ["--ui-dir", str(root / "frontend/dist")]
    children: list[subprocess.Popen[bytes]] = []
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        children.append(subprocess.Popen(backend, cwd=root, creationflags=flags))
        if args.dev:
            assert node is not None
            children.append(
                subprocess.Popen(
                    [node, str(root / "frontend/node_modules/vite/bin/vite.js")],
                    cwd=root / "frontend",
                    creationflags=flags,
                )
            )
        port = 5173 if args.dev else 8765
        print(f"AgentEval Studio: http://127.0.0.1:{port}", flush=True)
        print(
            "Local synthetic evaluation; optional Ollama is experimental. "
            "Ctrl+C closes owned processes.",
            flush=True,
        )
        while all(child.poll() is None for child in children):
            time.sleep(0.25)
        print("A process stopped. Read the preceding diagnostic and restart.", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
