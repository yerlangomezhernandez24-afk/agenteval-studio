"""Local CLI. No activation, shell commands, network APIs or Ollama needed."""

import argparse
import sys
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from agenteval.engine import run_suite
from agenteval.integrity import SnapshotCorruption
from agenteval.io import export_run, load_suite
from agenteval.local_models import LocalRun
from agenteval.models import Run
from agenteval.storage import Store


def main() -> int:
    parser = argparse.ArgumentParser(description="AgentEval — REPLAY / SIMULATED OUTPUT")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--suite", type=Path)
    run_parser = commands.add_parser("run")
    run_parser.add_argument("--suite", type=Path)
    run_parser.add_argument("--db", type=Path, default=Path("data/agenteval.sqlite3"))
    run_parser.add_argument("--output", type=Path)
    export = commands.add_parser("export")
    export.add_argument("run_id")
    export.add_argument("--db", type=Path, default=Path("data/agenteval.sqlite3"))
    export.add_argument("--output", type=Path, required=True)
    serve = commands.add_parser("serve")
    serve.add_argument("--db", type=Path, default=Path("data/agenteval.sqlite3"))
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument(
        "--dev-ui", action="store_true", help="Allow exact Vite origin 127.0.0.1:5173"
    )
    serve.add_argument("--ui-dir", type=Path, help="Trusted compiled UI directory")
    args = parser.parse_args()
    store: Store | None = None
    run: Run | LocalRun
    try:
        if args.command == "serve":
            import uvicorn

            from agenteval.api import create_app

            uvicorn.run(
                create_app(args.db, port=args.port, dev_ui=args.dev_ui, ui_dir=args.ui_dir),
                host="127.0.0.1",
                port=args.port,
                access_log=False,
                proxy_headers=False,
            )
        elif args.command == "validate":
            suite = load_suite(args.suite)
            print(f"Valid synthetic suite: {suite.id}@{suite.version}; {len(suite.cases)} cases")
        else:
            store = Store(args.db)
            if args.command == "run":
                run = run_suite(load_suite(args.suite))
                store.save(run)
                print(f"{run.label}\nRun persisted: {run.id}")
                print(run.metrics.model_dump_json(indent=2))
            else:
                saved = store.get(args.run_id)
                if saved is None:
                    raise ValueError("Run not found")
                run = saved
            if args.output:
                export_run(run, args.output)
        return 0
    except SnapshotCorruption:
        print("Stored snapshot integrity check failed; record unchanged.", file=sys.stderr)
        return 3
    except (ValueError, OSError, SQLAlchemyError):
        print(
            "Operation failed: invalid data/path, existing export, or unavailable storage. "
            "Check local inputs and permissions; no response content is logged.",
            file=sys.stderr,
        )
        return 2
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
