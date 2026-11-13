"""Minimal loopback API: bundled suite only, no remote paths or arbitrary providers."""

from asyncio import to_thread
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import Response
from starlette.staticfiles import StaticFiles

from agenteval.comparison import Comparison, compare_runs
from agenteval.engine import run_suite
from agenteval.integrity import SnapshotCorruption
from agenteval.io import load_suite
from agenteval.local_jobs import Job, JobBusy, JobManager, JobUnavailable
from agenteval.local_models import GenerationOptions, LocalRun, PromptId
from agenteval.local_snapshot import PROMPTS
from agenteval.models import Run, Suite
from agenteval.ollama import OllamaClient, OllamaFailure
from agenteval.reports import comparison_csv, run_csv
from agenteval.security import WebPolicy, response_headers
from agenteval.storage import MAX_OFFSET, Store
from agenteval.variants import VariantId, catalog, load_variant


def create_app(
    db_path: Path = Path("data/agenteval.sqlite3"),
    *,
    port: int = 8765,
    dev_ui: bool = False,
    ui_dir: Path | None = None,
    ollama_client: OllamaClient | None = None,
) -> FastAPI:
    policy = WebPolicy(port, dev_ui)
    store = Store(db_path)
    gate = Lock()
    local_client = ollama_client or OllamaClient()
    jobs = JobManager(store, gate, local_client)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        await to_thread(jobs.close)
        store.close()

    app = FastAPI(
        title="AgentEval Studio — local evaluation",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        version="0.5.0",
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1"])
    router = APIRouter()

    @app.middleware("http")
    async def local_only(request: Request, call_next: object) -> Response:
        from typing import cast

        from starlette.middleware.base import RequestResponseEndpoint

        rejection = policy.reject(request)
        if rejection is not None:
            return response_headers(rejection)
        # This API takes no request bodies; streaming detection also rejects chunked payloads.
        async for chunk in request.stream():
            if chunk:
                return response_headers(
                    JSONResponse({"detail": "Request bodies are not supported"}, status_code=413)
                )
        return response_headers(await cast(RequestResponseEndpoint, call_next)(request))

    @app.exception_handler(SQLAlchemyError)
    async def storage_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        return JSONResponse({"detail": "Local persistence unavailable"}, status_code=503)

    @app.exception_handler(SnapshotCorruption)
    async def corrupt_snapshot(request: Request, exc: SnapshotCorruption) -> JSONResponse:
        return JSONResponse(
            {"detail": "Stored snapshot integrity check failed", "code": "snapshot_corrupt"},
            status_code=409,
        )

    @router.get("/session")
    def session() -> dict[str, str]:
        return {"csrf_token": policy.token}

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "provider": "REPLAY / SIMULATED OUTPUT"}

    @router.get("/suite", response_model=Suite)
    def suite() -> Suite:
        return load_suite()

    @router.post("/runs", response_model=Run, status_code=201)
    def execute(variant: VariantId = "baseline-v1") -> Run | JSONResponse:
        if not gate.acquire(blocking=False):
            return JSONResponse(
                {"detail": "An evaluation is already running", "code": "run_busy"}, status_code=409
            )
        try:
            run = run_suite(load_variant(variant))
            store.save(run)
            return run
        finally:
            gate.release()

    @router.get("/runs")
    def list_runs(
        limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0, le=MAX_OFFSET)
    ) -> dict[str, list[str]]:
        return {"run_ids": store.list_ids(limit, offset)}

    @router.get("/runs/{run_id}", response_model=Run | LocalRun)
    def get_run(run_id: UUID) -> Run | LocalRun:
        run = store.get(str(run_id))
        if run is None:
            raise HTTPException(404, "Run not found")
        return run

    @router.get("/ollama/status")
    def ollama_status() -> dict[str, object]:
        try:
            models = local_client.models()
            return {
                "available": True,
                "models": [m.model_dump() for m in models],
                "version": local_client.version(),
                "error": None,
                "provenance": local_client.provenance,
                "prompts": list(PROMPTS),
            }
        except OllamaFailure as exc:
            return {
                "available": False,
                "models": [],
                "version": None,
                "error": exc.code,
                "provenance": local_client.provenance,
                "prompts": list(PROMPTS),
            }

    @router.post("/ollama/jobs", response_model=Job, status_code=202)
    def start_local(
        model: str = Query(
            min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}$"
        ),
        prompt: PromptId = "support-json-v1",
        temperature: float = Query(0.0, ge=0, le=1, allow_inf_nan=False),
        seed: int = Query(42, ge=0, le=2147483647),
        num_predict: int = Query(64, ge=16, le=128),
    ) -> Job:
        try:
            return jobs.start(
                model,
                prompt,
                GenerationOptions(temperature=temperature, seed=seed, num_predict=num_predict),
            )
        except JobBusy:
            raise HTTPException(409, "An evaluation is already running") from None
        except JobUnavailable:
            raise HTTPException(503, "Local worker unavailable") from None
        except OllamaFailure:
            raise HTTPException(503, "Local Ollama unavailable") from None
        except ValueError:
            raise HTTPException(422, "Select an installed local model") from None

    @router.get("/ollama/jobs/{job_id}", response_model=Job)
    def local_job(job_id: UUID) -> Job:
        job = jobs.get(str(job_id))
        if job is None:
            raise HTTPException(404, "Job not found or expired")
        return job

    @router.post("/ollama/jobs/{job_id}/cancel", response_model=Job)
    def cancel_local(job_id: UUID) -> Job:
        job = jobs.cancel(str(job_id))
        if job is None:
            raise HTTPException(404, "Job not found or expired")
        return job

    @router.get("/runs/{run_id}/export")
    def export_snapshot(run_id: UUID, format: Literal["json", "csv"] = "json") -> Response:
        run = get_run(run_id)
        return Response(
            content=run.model_dump_json(indent=2) if format == "json" else run_csv(run),
            media_type="application/json" if format == "json" else "text/csv",
            headers={"Content-Disposition": f'attachment; filename="agenteval-run.{format}"'},
        )

    @router.get("/variants")
    def variants() -> list[dict[str, str]]:
        return catalog()

    def comparison(a: UUID, b: UUID) -> Comparison:
        left, right = store.get(str(a)), store.get(str(b))
        if left is None or right is None:
            raise HTTPException(404, "Run not found")
        return compare_runs(left, right)

    @router.get("/comparisons", response_model=Comparison)
    def compare(a: UUID, b: UUID) -> Comparison:
        return comparison(a, b)

    @router.get("/comparisons/export")
    def export_comparison(a: UUID, b: UUID, format: Literal["json", "csv"] = "json") -> Response:
        report = comparison(a, b)
        content = report.model_dump_json(indent=2) if format == "json" else comparison_csv(report)
        return Response(
            content=content,
            media_type="application/json" if format == "json" else "text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="agenteval-comparison.{format}"'
            },
        )

    app.include_router(router)
    app.include_router(router, prefix="/api")
    if ui_dir is not None:
        if not (ui_dir / "index.html").is_file():
            raise ValueError("Build frontend first; index.html missing")
        app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
    return app
