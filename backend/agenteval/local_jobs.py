"""One bounded local inference worker sharing the replay execution gate."""

from _thread import LockType
from datetime import UTC, datetime
from threading import Event, Lock, Thread
from time import monotonic
from typing import Literal
from uuid import uuid4

from pydantic import Field

from agenteval.io import digest
from agenteval.local_models import Attempt, GenerationOptions, LocalRun, ModelInfo, PromptId
from agenteval.local_snapshot import (
    evaluate_attempt,
    local_suite,
    request_parameters,
    snapshot_digest,
)
from agenteval.metrics import aggregate
from agenteval.models import StrictModel
from agenteval.ollama import OllamaClient, OllamaFailure
from agenteval.storage import Store


class Job(StrictModel):
    id: str
    status: Literal["running", "cancelling", "completed", "cancelled", "error"] = "running"
    completed_cases: int = 0
    total_cases: Literal[3] = 3
    run_id: str | None = None
    error: str | None = None
    provenance: Literal["local_ollama", "http_test_double"]
    model: str
    created_utc: str
    elapsed_ms: float = Field(default=0, ge=0)


class JobBusy(Exception):
    pass


class JobUnavailable(RuntimeError):
    pass


class JobManager:
    def __init__(self, store: Store, gate: LockType, client: OllamaClient) -> None:
        self.store, self.gate, self.client = store, gate, client
        self.lock = Lock()
        self.jobs: dict[str, Job] = {}
        self.cancel_event = Event()
        self.thread: Thread | None = None
        self.active_id: str | None = None
        self.lifecycle = Lock()
        self.closed = False

    def start(self, model: str, prompt: PromptId, options: GenerationOptions) -> Job:
        # Serialize preparation/publication with close. The worker never takes
        # this lock, so close can join it without blocking its completion.
        with self.lifecycle:
            if self.closed:
                raise JobBusy()
            return self._start(model, prompt, options)

    def _start(self, model: str, prompt: PromptId, options: GenerationOptions) -> Job:
        if not self.gate.acquire(blocking=False):
            raise JobBusy()
        job: Job | None = None
        try:
            installed = {item.name: item for item in self.client.models()}
            if model not in installed:
                raise ValueError("Select an installed local model")
            version = self.client.version()
            self.cancel_event = Event()
            job = Job(
                id=str(uuid4()),
                provenance=self.client.provenance,
                model=model,
                created_utc=datetime.now(UTC).isoformat(),
            )
            with self.lock:
                while len(self.jobs) >= 20:
                    self.jobs.pop(next(iter(self.jobs)))
                self.jobs[job.id] = job
                self.active_id = job.id
            self.thread = Thread(
                target=self._work,
                args=(job.id, installed[model], prompt, options, version),
                name="agenteval-local",
                daemon=True,
            )
            try:
                self.thread.start()
            except RuntimeError:
                raise JobUnavailable("Local worker unavailable") from None
            with self.lock:
                return job.model_copy(deep=True)
        except BaseException:
            with self.lock:
                if job is not None:
                    self.jobs.pop(job.id, None)
                self.active_id = None
                self.thread = None
            self.gate.release()
            raise

    def get(self, job_id: str) -> Job | None:
        with self.lock:
            job = self.jobs.get(job_id)
            return job.model_copy(deep=True) if job else None

    def cancel(self, job_id: str) -> Job | None:
        with self.lock:
            job = self.jobs.get(job_id)
            if job and job.status in {"running", "cancelling"}:
                job.status = "cancelling"
                self.cancel_event.set()
                self.client.cancel()
            return job.model_copy(deep=True) if job else None

    def close(self) -> None:
        with self.lifecycle:
            self.closed = True
            if self.active_id:
                self.cancel(self.active_id)
            if self.thread:
                self.thread.join(timeout=35)
                if self.thread.is_alive():
                    raise RuntimeError("Local worker did not stop")

    def _work(
        self,
        job_id: str,
        model: ModelInfo,
        prompt: PromptId,
        options: GenerationOptions,
        version: str | None,
    ) -> None:
        started = monotonic()
        try:
            suite = local_suite(prompt)
            results, attempts = [], []
            for case in suite.cases:
                if monotonic() - started >= 100:
                    self.cancel_event.set()
                raw = None
                if self.cancel_event.is_set():
                    attempt = Attempt(case_id=case.id, code="not_started")
                else:
                    request_start = monotonic()
                    try:
                        response = self.client.generate(
                            model, suite.prompt, case.input, options, self.cancel_event
                        )
                        raw = response["response"]
                        attempt = Attempt(
                            case_id=case.id,
                            code="response",
                            elapsed_ms=(monotonic() - request_start) * 1000,
                            generation_duration_ns=response["eval_duration"],
                            total_duration_ns=response["total_duration"],
                            eval_count=response["eval_count"],
                        )
                    except OllamaFailure as exc:
                        attempt = Attempt(
                            case_id=case.id,
                            code=exc.code,
                            elapsed_ms=(monotonic() - request_start) * 1000,
                        )
                attempts.append(attempt)
                results.append(evaluate_attempt(case, raw, attempt))
                with self.lock:
                    if attempt.code != "not_started":
                        self.jobs[job_id].completed_cases += 1
                    self.jobs[job_id].elapsed_ms = (monotonic() - started) * 1000
            completion: Literal["cancelled", "completed"] = (
                "cancelled"
                if any(a.code in {"cancelled", "not_started"} for a in attempts)
                else "completed"
            )
            run = LocalRun(
                id=str(uuid4()),
                created_utc=datetime.now(UTC).isoformat(),
                provenance=self.client.provenance,
                model=model.name,
                model_info=model,
                ollama_version=version,
                options=options,
                parameters=request_parameters(options),
                completion=completion,
                suite=suite,
                attempts=attempts,
                results=results,
                metrics=aggregate(suite, results),
                dataset_hash=digest(suite.model_dump()),
                cases_hash=digest([c.model_dump() for c in suite.cases]),
                prompt_hash=digest(suite.prompt),
                snapshot_hash="0" * 64,
            )
            run.snapshot_hash = snapshot_digest(run)
            from agenteval.local_snapshot import verify_local

            verify_local(run, run.id, run.created_utc)
            self.store.save(run)
            with self.lock:
                self.jobs[job_id].run_id = run.id
                self.jobs[job_id].status = completion
        except Exception:
            # Never echo raw, exception strings, headers or local paths.
            with self.lock:
                self.jobs[job_id].status = "error"
                self.jobs[job_id].error = "No se pudo guardar una ejecución verificada."
        finally:
            with self.lock:
                self.active_id = None
            self.gate.release()
