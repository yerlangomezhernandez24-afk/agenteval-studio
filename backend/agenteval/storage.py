"""Append-only application interface storing complete immutable run snapshots."""

from pathlib import Path
from uuid import UUID

from sqlalchemy import Column, MetaData, String, Table, Text, create_engine, insert, select
from sqlalchemy.engine import URL

from agenteval.integrity import restore
from agenteval.io import checked_path
from agenteval.local_models import LocalRun
from agenteval.models import Run

MAX_OFFSET = 1_000_000


class Store:
    def __init__(self, path: Path) -> None:
        checked_path(path, ".sqlite3")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            URL.create("sqlite", database=str(path.resolve())), connect_args={"timeout": 5}
        )
        metadata = MetaData()
        self.runs = Table(
            "runs",
            metadata,
            Column("id", String, primary_key=True),
            Column("created_utc", String, nullable=False),
            Column("snapshot", Text, nullable=False),
        )
        metadata.create_all(self.engine)

    def save(self, run: Run | LocalRun) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                insert(self.runs).values(
                    id=run.id, created_utc=run.created_utc, snapshot=run.model_dump_json()
                )
            )

    def get(self, run_id: str) -> Run | LocalRun | None:
        UUID(run_id)
        with self.engine.connect() as conn:
            row = conn.execute(
                select(self.runs.c.snapshot, self.runs.c.created_utc).where(
                    self.runs.c.id == run_id
                )
            ).first()
        return restore(row.snapshot, run_id, row.created_utc) if row is not None else None

    def list_ids(self, limit: int = 50, offset: int = 0) -> list[str]:
        if type(limit) is not int or type(offset) is not int:
            raise ValueError("Pagination requires integers")
        if not 1 <= limit <= 100 or not 0 <= offset <= MAX_OFFSET:
            raise ValueError("Invalid pagination")
        with self.engine.connect() as conn:
            return list(
                conn.execute(
                    select(self.runs.c.id)
                    .order_by(self.runs.c.created_utc.desc(), self.runs.c.id)
                    .limit(limit)
                    .offset(offset)
                ).scalars()
            )

    def close(self) -> None:
        self.engine.dispose()
