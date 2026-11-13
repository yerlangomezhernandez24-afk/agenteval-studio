import { useEffect, useState } from "react";
import { z } from "zod";
import { ApiError, request } from "./api";
import { modelSchema, promptSchema, provenanceSchema } from "./contracts";
import { ErrorBanner } from "./components";
import { explorerLink, useRemote } from "./hooks";

const statusSchema = z.object({
  available: z.boolean(),
  models: z.array(modelSchema),
  version: z.string().nullable(),
  error: z.string().nullable(),
  provenance: provenanceSchema,
  prompts: z.array(promptSchema),
});
const jobSchema = z.object({
  id: z.uuid(),
  status: z.enum(["running", "cancelling", "completed", "cancelled", "error"]),
  completed_cases: z.number().int().min(0).max(3),
  total_cases: z.literal(3),
  run_id: z.uuid().nullable(),
  error: z.string().nullable(),
  provenance: provenanceSchema,
  model: z.string(),
  elapsed_ms: z.number().nonnegative(),
});
type Job = z.infer<typeof jobSchema>;
async function post(path: string) {
  const session = await request(
    "/session",
    z.object({ csrf_token: z.string().min(40) }),
  );
  return request(path, jobSchema, {
    method: "POST",
    headers: { "X-CSRF-Token": session.csrf_token },
  });
}
// Persistence is optional; browser privacy/quota restrictions must not lose a job.
function rememberedJob(value?: string | null): string | null {
  try {
    if (value === null) sessionStorage.removeItem("agenteval-local-job");
    else if (value !== undefined)
      sessionStorage.setItem("agenteval-local-job", value);
    return sessionStorage.getItem("agenteval-local-job");
  } catch {
    return null;
  }
}
const loadStatus = (signal?: AbortSignal) =>
  request("/ollama/status", statusSchema, { signal });
export default function OllamaControls({
  onComplete,
}: {
  onComplete: () => void;
}) {
  const [revision, setRevision] = useState(0);
  const status = useRemote(`ollama-${revision}`, loadStatus);
  const [model, setModel] = useState("");
  const [prompt, setPrompt] = useState("support-json-v1");
  const [temperature, setTemperature] = useState(0);
  const [seed, setSeed] = useState(42);
  const [tokens, setTokens] = useState(64);
  const [job, setJob] = useState<Job>();
  useEffect(() => {
    const saved = rememberedJob();
    if (!saved || !z.uuid().safeParse(saved).success) return;
    const controller = new AbortController();
    void request(`/ollama/jobs/${saved}`, jobSchema, {
      signal: controller.signal,
    })
      .then(setJob)
      .catch(() => {
        if (!controller.signal.aborted) rememberedJob(null);
      });
    return () => controller.abort();
  }, []);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<Error>();
  const active = job?.status === "running" || job?.status === "cancelling";
  const selected = status.data?.models.find((m) => m.name === model);
  const jobId = job?.id;
  useEffect(() => {
    if (!active || !jobId) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const next = await request(`/ollama/jobs/${jobId}`, jobSchema, {
          signal: controller.signal,
        });
        setJob(next);
        setError(undefined);
        if (next.status === "running" || next.status === "cancelling")
          timer = setTimeout(() => void poll(), 500);
        else onComplete();
      } catch (e) {
        if (!controller.signal.aborted) {
          setError(e instanceof Error ? e : new Error("Consulta fallida"));
          if (e instanceof ApiError && e.status === 404) {
            setJob(undefined);
            rememberedJob(null);
            setError(
              new Error(
                "Job no disponible tras reinicio o expiración. Consulta el historial antes de ejecutar de nuevo.",
              ),
            );
          } else timer = setTimeout(() => void poll(), 2000);
        }
      }
    };
    timer = setTimeout(() => void poll(), 300);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [active, jobId, onComplete]);
  async function execute() {
    if (pending || active || !selected) return;
    setPending(true);
    setError(undefined);
    try {
      const next = await post(
        `/ollama/jobs?${new URLSearchParams({ model, prompt, temperature: String(temperature), seed: String(seed), num_predict: String(tokens) })}`,
      );
      setJob(next);
      rememberedJob(next.id);
    } catch (e) {
      setError(e instanceof Error ? e : new Error("Inicio fallido"));
    } finally {
      setPending(false);
    }
  }
  async function cancel() {
    if (!job) return;
    try {
      setJob(await post(`/ollama/jobs/${job.id}/cancel`));
    } catch (e) {
      setError(e instanceof Error ? e : new Error("Cancelación no confirmada"));
    }
  }
  return (
    <section
      className="panel ollama-panel"
      aria-label="Ollama local experimental"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">LOCAL LLM / EXPERIMENTAL</p>
          <h2>Ollama local, bajo control</h2>
        </div>
        <button
          disabled={pending || active || status.loading}
          onClick={() => setRevision((r) => r + 1)}
        >
          Comprobar disponibilidad
        </button>
      </div>
      <p>
        3 casos sintéticos instalados · Sin descargas · Sin herramientas.
        CPU/RAM y duración variables; no se garantiza determinismo.
      </p>
      {status.loading && <p role="status">Consultando Ollama local…</p>}
      {status.error && <ErrorBanner error={status.error} />}
      {status.data && (
        <p role="status">
          {!status.data.available
            ? "Ollama no disponible. Replay sigue disponible; no se instala nada."
            : status.data.models.length
              ? `Ollama disponible · ${status.data.models.length} modelos locales`
              : "Ollama disponible sin modelos locales. No se descarga nada."}
        </p>
      )}
      {status.data?.provenance === "http_test_double" && (
        <p className="error-banner">
          HTTP TEST DOUBLE / NO MODELO REAL. Solo prueba de integración; no mide
          calidad de un LLM.
        </p>
      )}
      <fieldset
        disabled={
          pending ||
          active ||
          !status.data?.available ||
          !status.data.models.length
        }
      >
        <legend>Selección explícita y parámetros</legend>
        <div className="toolbar filters">
          <label>
            Modelo local
            <select value={model} onChange={(e) => setModel(e.target.value)}>
              <option value="">Selecciona un modelo instalado</option>
              {status.data?.models.map((m) => (
                <option key={m.name} value={m.name}>
                  {m.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Prompt versionado
            <select value={prompt} onChange={(e) => setPrompt(e.target.value)}>
              <option>support-json-v1</option>
              <option>support-concise-v1</option>
            </select>
          </label>
          <label>
            Temperatura
            <input
              type="number"
              min="0"
              max="1"
              step="0.1"
              value={temperature}
              onChange={(e) => setTemperature(e.target.valueAsNumber)}
            />
          </label>
          <label>
            Semilla
            <input
              type="number"
              min="0"
              max="2147483647"
              value={seed}
              onChange={(e) => setSeed(e.target.valueAsNumber)}
            />
          </label>
          <label>
            Máximo tokens
            <input
              type="number"
              min="16"
              max="128"
              value={tokens}
              onChange={(e) => setTokens(e.target.valueAsNumber)}
            />
          </label>
        </div>
      </fieldset>
      {selected && (
        <details>
          <summary>Metadatos del modelo seleccionado</summary>
          <dl className="hashes">
            <dt>SHA-256</dt>
            <dd>{selected.digest}</dd>
            <dt>Tamaño instalado</dt>
            <dd>{selected.size} bytes</dd>
            <dt>Familia / parámetros / cuantización</dt>
            <dd>
              {selected.family} / {selected.parameter_size || "no disponible"} /{" "}
              {selected.quantization_level || "no disponible"}
            </dd>
            <dt>Ollama</dt>
            <dd>{status.data?.version ?? "no disponible"}</dd>
          </dl>
        </details>
      )}
      <p>
        El JSON exportado conserva las entradas sintéticas y respuestas RAW en
        SQLite. Sin entradas libres ni datos personales.
      </p>
      <button
        className="primary"
        disabled={
          pending ||
          active ||
          !selected ||
          !status.data?.available ||
          !Number.isFinite(temperature) ||
          temperature < 0 ||
          temperature > 1 ||
          !Number.isInteger(seed) ||
          seed < 0 ||
          seed > 2147483647 ||
          !Number.isInteger(tokens) ||
          tokens < 16 ||
          tokens > 128
        }
        onClick={() => void execute()}
      >
        Ejecutar 3 casos con Ollama
      </button>
      {error && <ErrorBanner error={error} />}
      {job && (
        <div aria-live="polite">
          <p>
            {job.status} · {job.completed_cases} / {job.total_cases} intentos
            terminados · {job.provenance} · {job.model}
          </p>
          {active && (
            <>
              <progress
                max={job.total_cases}
                value={job.completed_cases}
                aria-label="Casos terminados"
              />
              <button
                disabled={job.status === "cancelling"}
                onClick={() => void cancel()}
              >
                Cancelar ejecución local
              </button>
            </>
          )}
          {job.error && <p role="alert">{job.error}</p>}
          {job.run_id && (
            <a className="button" href={explorerLink(job.run_id)}>
              Ver snapshot experimental →
            </a>
          )}
          <small>
            Las omisiones tras cancelar no cuentan como intentos terminados.
            Cambiar de pantalla no cancela el trabajo; el snapshot final aparece
            en el historial.
          </small>
        </div>
      )}
    </section>
  );
}
