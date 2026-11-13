"""Test-only seed for an isolated E2E database. Never exposed through HTTP."""

import argparse
from pathlib import Path

from sqlalchemy import update

from agenteval.engine import run_suite
from agenteval.io import load_suite
from agenteval.storage import Store


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("db", type=Path)
    parser.add_argument("mode", choices=["varied", "legacy", "corrupt"])
    args = parser.parse_args()
    if not args.db.name.startswith("e2e-"):
        raise ValueError("Only dedicated E2E databases")
    suite = load_suite()
    if args.mode == "varied":
        suite.replay["vpn"].output = "{}"
    if args.mode == "legacy":
        suite.criteria_version = "1.0"
    run = run_suite(suite)
    store = Store(args.db)
    try:
        store.save(run)
        if args.mode == "corrupt":
            with store.engine.begin() as conn:
                conn.execute(
                    update(store.runs)
                    .where(store.runs.c.id == run.id)
                    .values(snapshot='{"PRIVATE":')
                )
        print(run.id)
    finally:
        store.close()


if __name__ == "__main__":
    main()
