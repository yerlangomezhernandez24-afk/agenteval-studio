import { useCallback, useRef, useState } from "react";
import { api } from "./api";
import {
  Badge,
  CaseDetail,
  CriteriaTable,
  Distribution,
  Empty,
  ErrorBanner,
  RateValue,
  Replay,
  StatusCards,
} from "./components";
import { statuses } from "./contracts";
import type { Run, Status, Suite } from "./contracts";
import { explorerLink, useRemote, useRoute } from "./hooks";
import RegressionLab from "./RegressionLab";
import OllamaControls from "./OllamaControls";
import RunExport from "./RunExport";

const navigation = [
  ["/overview", "Overview", "01"],
  ["/suites", "Test Suites", "02"],
  ["/runs", "Evaluation Runs", "03"],
  ["/explorer", "Case Explorer", "04"],
  ["/regression", "Regression Lab", "05"],
] as const;
const date = (value: string) =>
  new Intl.DateTimeFormat("es", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));

export default function App() {
  const route = useRoute();
  const [revision, setRevision] = useState(0);
  const [offset, setOffset] = useState(0);
  const [pending, setPending] = useState(false);
  const [provider, setProvider] = useState("replay");
  const lock = useRef(false);
  const [actionError, setActionError] = useState<Error>();
  const [notice, setNotice] = useState("");
  const [variant, setVariant] = useState<"baseline-v1" | "mixed-v1">(
    "baseline-v1",
  );
  const variants = useRemote("variants", api.variants);
  const refresh = () => {
    setRevision((value) => value + 1);
  };
  const health = useRemote(`health-${revision}`, api.health);
  const suite = useRemote(`suite-${revision}`, api.suite);
  const history = useRemote(
    `runs-${offset}-${revision}`,
    useCallback((signal) => api.runs(offset, signal), [offset]),
  );
  const latest = useRemote(
    `latest-${revision}`,
    useCallback(async (signal) => {
      const list = await api.runs(0, signal);
      return list.run_ids[0] ? api.run(list.run_ids[0], signal) : null;
    }, []),
  );
  const requestedId = route.params.get("run");
  const detail = useRemote(
    `detail-${requestedId}-${revision}`,
    useCallback(
      (signal) =>
        requestedId ? api.run(requestedId, signal) : Promise.resolve(null),
      [requestedId],
    ),
  );
  const run = requestedId ? detail.data : latest.data;
  async function execute() {
    if (lock.current) return;
    lock.current = true;
    setPending(true);
    setActionError(undefined);
    setNotice("Ejecutando replay local…");
    try {
      const created = await api.execute(
        variant === "baseline-v1" ? undefined : variant,
      );
      setOffset(0);
      refresh();
      setNotice(
        `HTTP 201 · Ejecución guardada. ${created.metrics.total} casos procesados.`,
      );
      window.location.hash = explorerLink(created.id).slice(1);
    } catch (error) {
      setActionError(
        error instanceof Error ? error : new Error("No se pudo ejecutar"),
      );
      setNotice(
        "No se confirmó la ejecución. Consulta el historial antes de repetir.",
      );
    } finally {
      lock.current = false;
      setPending(false);
    }
  }
  const executeButton = (
    <div className="variant-execute">
      <label>
        Variante replay
        <select
          value={variant}
          disabled={pending}
          onChange={(event) =>
            setVariant(event.target.value as "baseline-v1" | "mixed-v1")
          }
        >
          {variants.data ? (
            variants.data.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} · {item.replay_version}
              </option>
            ))
          ) : (
            <option value="baseline-v1">Base histórica · 1.0.0</option>
          )}
        </select>
      </label>
      <button
        className="primary"
        onClick={() => void execute()}
        disabled={pending || !suite.data || !health.data}
      >
        <span aria-hidden="true">{pending ? "◌" : "▷"}</span>{" "}
        {pending ? "Ejecutando…" : "Ejecutar suite sintética"}
      </button>
      {variants.error && (
        <p role="status">Catálogo no disponible; solo base histórica.</p>
      )}
    </div>
  );
  const pageName =
    navigation.find(([path]) => path === route.page)?.[1] ?? "Overview";
  return (
    <div className="app-shell">
      <a
        className="skip-link"
        href="#main-content"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById("main-content")?.focus();
        }}
      >
        Saltar al contenido
      </a>
      <aside className="sidebar">
        <a href="#/overview" className="brand">
          <span className="brand-mark" aria-hidden="true">
            ae<span>↗</span>
          </span>
          <div>
            AgentEval<span>STUDIO</span>
          </div>
        </a>
        <p className="sidebar-label">QUALITY WORKSPACE</p>
        <nav aria-label="Principal">
          {navigation.map(([path, name, number]) => (
            <a
              key={path}
              href={`#${path}`}
              aria-current={route.page === path ? "page" : undefined}
            >
              <span className="nav-index">{number}</span>
              {name}
              <span className="nav-arrow" aria-hidden="true">
                ↗
              </span>
            </a>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span className="local-indicator" /> ENTORNO LOCAL
          <div>
            Replay y Ollama opcional.
            <br />
            Casos sintéticos; procedencia visible.
          </div>
          <span className="sidebar-version">Fase 5 · UI 0.5.0</span>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div>
            <span className="muted">Workspace</span>
            <span aria-hidden="true"> / </span>
            <strong>{pageName}</strong>
          </div>
          <span className={`connection ${health.data ? "online" : ""}`}>
            <i />
            {health.loading
              ? "Conectando"
              : health.data
                ? "Backend conectado"
                : "Backend no disponible"}
          </span>
        </header>
        <main id="main-content" tabIndex={-1}>
          <div className="page-heading">
            <div>
              <p className="eyebrow">
                AI QUALITY ENGINEERING & EVALUATION PLATFORM
              </p>
              <h1>{pageName}</h1>
            </div>
            <span className="replay">LOCAL EVALUATION · EXPERIMENTAL</span>
          </div>
          <div className="announcements" aria-live="polite">
            {route.page === "/regression" ? "" : notice}
          </div>
          {health.error && <ErrorBanner error={health.error} retry={refresh} />}
          {actionError && <ErrorBanner error={actionError} retry={refresh} />}
          {route.page === "/regression" ? (
            <RegressionLab params={route.params} />
          ) : route.page === "/suites" ? (
            <>
              {suite.loading ? (
                <p role="status">Cargando suite…</p>
              ) : suite.error ? (
                <ErrorBanner error={suite.error} retry={refresh} />
              ) : (
                suite.data && (
                  <Suites suite={suite.data} executeButton={executeButton} />
                )
              )}
            </>
          ) : route.page === "/runs" ? (
            <>
              <section className="section-heading">
                <div>
                  <h2>Historial de evaluaciones</h2>
                  <p className="muted">
                    Snapshots persistidos en SQLite. Replay síncrono y jobs
                    Ollama acotados.
                  </p>
                </div>
                <label>
                  Proveedor
                  <select
                    value={provider}
                    onChange={(e) => setProvider(e.target.value)}
                  >
                    <option value="replay">ReplayProvider (simulado)</option>
                    <option value="ollama">Ollama local (experimental)</option>
                  </select>
                </label>
              </section>
              {provider === "replay" ? (
                executeButton
              ) : (
                <OllamaControls
                  onComplete={() => {
                    setOffset(0);
                    refresh();
                  }}
                />
              )}
              <div className="toolbar">
                <span>
                  {history.data
                    ? `${history.data.run_ids.length} ejecuciones consultadas en esta página`
                    : "Consultando historial…"}
                </span>
                <button onClick={refresh}>Actualizar historial</button>
              </div>
              {history.error && (
                <ErrorBanner error={history.error} retry={refresh} />
              )}
              {history.loading && <p role="status">Cargando historial…</p>}
              {history.data &&
                (history.data.run_ids.length ? (
                  <div className="run-list">
                    {history.data.run_ids.map((id) => (
                      <RunRow key={`${id}-${revision}`} id={id} />
                    ))}
                  </div>
                ) : (
                  <Empty title="No hay ejecuciones en esta página">
                    <p>
                      Ejecuta la suite sintética para guardar tu primer
                      snapshot.
                    </p>
                  </Empty>
                ))}
              <div className="pagination">
                <button
                  disabled={offset === 0 || history.loading}
                  onClick={() => setOffset(Math.max(0, offset - 10))}
                >
                  ← Anterior
                </button>
                <span>Página {offset / 10 + 1} · 10 por página</span>
                <button
                  disabled={
                    history.loading ||
                    !history.data ||
                    history.data.run_ids.length < 10 ||
                    offset >= 1_000_000
                  }
                  onClick={() => setOffset(Math.min(1_000_000, offset + 10))}
                >
                  Siguiente →
                </button>
              </div>
            </>
          ) : route.page === "/explorer" ? (
            <>
              {route.params.get("return")?.startsWith("#/regression?") && (
                <a className="button" href={route.params.get("return")!}>
                  ← Volver a comparación
                </a>
              )}
              {(requestedId ? detail.loading : latest.loading) ? (
                <p role="status">Verificando snapshot…</p>
              ) : (requestedId ? detail.error : latest.error) ? (
                <ErrorBanner
                  error={(requestedId ? detail.error : latest.error)!}
                  retry={refresh}
                />
              ) : run ? (
                <Explorer
                  key={run.id}
                  run={run}
                  selectedCase={route.params.get("case")}
                />
              ) : (
                <Empty title="Selecciona una ejecución">
                  <p>
                    Abre un snapshot del historial para inspeccionar sus casos.
                  </p>
                  <a className="button" href="#/runs">
                    Ir a Evaluation Runs →
                  </a>
                </Empty>
              )}
            </>
          ) : (
            <>
              <section className="hero">
                <div>
                  <p className="eyebrow">EL CONTRATO, BAJO PRUEBA</p>
                  <h2>
                    Haz visibles los fallos.
                    <br />
                    <span>Conserva la evidencia.</span>
                  </h2>
                  <p>
                    Un laboratorio local para comprobar estructura,
                    clasificación y restricciones de respuestas sintéticas.
                  </p>
                  <div className="hero-actions">
                    {executeButton}
                    <a href="#/suites">Explorar suite →</a>
                  </div>
                </div>
                <div className="hero-note">
                  <span className="orbit" aria-hidden="true">
                    ◎
                  </span>
                  <strong>Reproducible por diseño</strong>
                  <p>
                    Casos versionados · checks independientes · snapshots
                    completos
                  </p>
                  <span>ReplayProvider / local-only</span>
                </div>
              </section>
              <div className="overview-context">
                <span>
                  <i className="local-indicator" />{" "}
                  {health.data
                    ? "ReplayProvider disponible"
                    : "Verificando proveedor"}
                </span>
                <span>
                  {history.data
                    ? `${history.data.run_ids.length} ejecuciones consultadas (página ${offset / 10 + 1})`
                    : "Consultando ejecuciones"}
                </span>
                <span>
                  {suite.data
                    ? `${suite.data.cases.length} casos en la suite incorporada`
                    : "Consultando suite"}
                </span>
              </div>
              {history.error && (
                <ErrorBanner error={history.error} retry={refresh} />
              )}
              {suite.error && (
                <ErrorBanner error={suite.error} retry={refresh} />
              )}
              {latest.loading ? (
                <p role="status">Consultando última ejecución…</p>
              ) : latest.error ? (
                <ErrorBanner error={latest.error} retry={refresh} />
              ) : latest.data ? (
                <Overview run={latest.data} />
              ) : (
                <Empty title="Tu primera evaluación empieza aquí">
                  <p>
                    Aún no hay ejecuciones guardadas. Revisa los casos de la
                    suite y ejecuta un replay.
                  </p>
                  <a className="button" href="#/suites">
                    Revisar Test Suites →
                  </a>
                </Empty>
              )}
            </>
          )}
          <footer>
            AgentEval Studio{" "}
            <span>
              Datos sintéticos · Proveedores locales · Sin servicios cloud
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}

function RunMeta({ run }: { run: Run }) {
  return (
    <div className="run-meta">
      <code>{run.id}</code>
      <span>{date(run.created_utc)}</span>
      <span>
        Criterios {run.suite.criteria_version}
        {run.suite.criteria_version === "1.0" ? " · HISTÓRICO / LEGADO" : ""}
      </span>
      <span>Motor {run.engine_version}</span>
      <span>
        {run.provider === "ReplayProvider"
          ? `Replay ${run.suite.replay_version}`
          : `${run.model} · ${run.completion}`}
      </span>
    </div>
  );
}
function Overview({ run }: { run: Run }) {
  return (
    <>
      <div className="section-heading">
        <div>
          <p className="eyebrow">ÚLTIMA EJECUCIÓN DISPONIBLE</p>
          <h2>Resultados del contrato</h2>
        </div>
        <a className="button" href={explorerLink(run.id)}>
          Inspeccionar casos ↗
        </a>
      </div>
      <RunMeta run={run} />
      <Replay run={run} />
      <StatusCards metrics={run.metrics} />
      <div className="analysis-grid">
        <section className="panel rate-panel">
          <p className="eyebrow">PASS RATE</p>
          <RateValue rate={run.metrics.pass_rate} />
          <Distribution metrics={run.metrics} />
          <p>
            {run.metrics.total} casos totales · {run.metrics.executed}{" "}
            ejecutados
          </p>
          <small>
            Los errores, omitidos y no evaluables se muestran por separado.
          </small>
        </section>
        <section className="panel critical-panel">
          <p className="eyebrow">REVISIÓN PRIORITARIA</p>
          <h2>
            {run.metrics.critical_failures.length} casos críticos sin aprobar
          </h2>
          <div className="tags">
            {run.metrics.critical_failures.map((id) => (
              <a href={explorerLink(run.id, id)} key={id}>
                {id} ↗
              </a>
            ))}
          </div>
          <p>Una cifra agregada no debe ocultar estos casos.</p>
        </section>
      </div>
      <section className="panel">
        <div className="section-heading">
          <h2>Una medida por criterio</h2>
          <span className="muted">6 comprobaciones independientes</span>
        </div>
        <CriteriaTable metrics={run.metrics} />
      </section>
      <div className="latency-note">
        <span aria-hidden="true">◷</span>
        <div>
          <strong>
            {run.provider === "ReplayProvider"
              ? "Tiempo de replay local, no inferencia de LLM"
              : "Tiempo HTTP local; generación reportada por separado"}
          </strong>
          <p>
            {run.metrics.latency_samples} muestras · mediana{" "}
            {run.metrics.latency_median_ms?.toFixed(3) ?? "—"} ms · p95{" "}
            {run.metrics.latency_p95_ms?.toFixed(3) ?? "—"} ms.{" "}
            {run.provider === "ReplayProvider"
              ? "Son tiempos de recuperación de fixtures."
              : "Incluyen transporte y errores; no son benchmarks de modelos."}
          </p>
        </div>
      </div>
    </>
  );
}

function Suites({
  suite,
  executeButton,
}: {
  suite: Suite;
  executeButton: React.ReactNode;
}) {
  const [selected, setSelected] = useState(suite.cases[0]?.id);
  const testCase = suite.cases.find((item) => item.id === selected);
  return (
    <>
      <section className="suite-intro panel">
        <div>
          <p className="eyebrow">DATASET FICTICIO · SOLO LECTURA</p>
          <Replay />
          <h2>{suite.id}</h2>
          <p>
            Asistente de soporte empresarial. Casos diseñados para comprobar el
            contrato, incluidos fallos deliberados.
          </p>
          <div className="tags">
            <span>Suite {suite.version}</span>
            <span>Criterios {suite.criteria_version}</span>
            <span>{suite.cases.length} casos</span>
            <span>Replay {suite.replay_version}</span>
          </div>
        </div>
        {executeButton}
      </section>
      <div className="split-view">
        <section className="panel">
          <div className="section-heading">
            <h2>Catálogo de casos</h2>
          </div>
          <div className="table-scroll">
            <table>
              <caption>
                Selecciona un caso para revisar su entrada y oráculo.
              </caption>
              <thead>
                <tr>
                  <th>Caso / título</th>
                  <th>Categoría / criticidad</th>
                  <th>Esperado / etiquetas</th>
                </tr>
              </thead>
              <tbody>
                {suite.cases.map((item) => (
                  <tr
                    key={item.id}
                    className={selected === item.id ? "selected-row" : ""}
                  >
                    <td>
                      <button
                        className="text-button"
                        onClick={() => setSelected(item.id)}
                        aria-pressed={selected === item.id}
                      >
                        {item.id}
                      </button>
                      <small className="block">{item.name}</small>
                    </td>
                    <td>
                      {item.category}
                      <small className="block">{item.criticality}</small>
                    </td>
                    <td>
                      {item.expected.priority} · humano:{" "}
                      {item.expected.requires_human ? "sí" : "no"}
                      <small className="block">{item.tags.join(" · ")}</small>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        {testCase && <CaseDetail testCase={testCase} />}
      </div>
      <section className="panel">
        <h3>Criterios aplicados</h3>
        <div className="tags">
          {suite.criteria.map((c) => (
            <code key={c}>{c}</code>
          ))}
        </div>
        <p className="muted">
          La edición e importación desde la interfaz no están implementadas.
        </p>
      </section>
    </>
  );
}
function RunRow({ id }: { id: string }) {
  const resource = useRemote(
    id,
    useCallback((signal) => api.run(id, signal), [id]),
  );
  if (resource.error)
    return (
      <section className="panel">
        <code>{id}</code>
        <ErrorBanner error={resource.error} />
        <a href={explorerLink(id)}>Abrir estado de ejecución →</a>
      </section>
    );
  if (!resource.data)
    return (
      <section className="panel" role="status">
        Cargando snapshot {id}…
      </section>
    );
  const run = resource.data;
  return (
    <article className="run-row">
      <div>
        <Replay run={run} />
        <h3>
          <a href={explorerLink(id)}>{run.suite.id} ↗</a>
        </h3>
        <RunMeta run={run} />
      </div>
      <div className="run-counts">
        <span>{run.metrics.passed} passed</span>
        <span>{run.metrics.failed} failed</span>
        <span>{run.metrics.errors} error</span>
        <span>{run.metrics.skipped} skipped</span>
        <span>{run.metrics.not_evaluable} not_evaluable</span>
      </div>
      <RateValue rate={run.metrics.pass_rate} />
      <a className="button" href={explorerLink(id)}>
        Explorar →
      </a>
    </article>
  );
}
export function Explorer({
  run,
  selectedCase,
}: {
  run: Run;
  selectedCase?: string | null;
}) {
  const [filter, setFilter] = useState<Status | "all">("all");
  const [search, setSearch] = useState("");
  const rows = run.results.filter((result) => {
    const testCase = run.suite.cases.find((c) => c.id === result.case_id);
    return (
      (filter === "all" || result.status === filter) &&
      `${result.case_id} ${testCase?.category ?? ""}`
        .toLowerCase()
        .includes(search.toLowerCase())
    );
  });
  // An explicit deep link owns selection. Filters only narrow the list, never
  // silently substitute a different detail for the case named in the URL.
  const result = selectedCase
    ? run.results.find((item) => item.case_id === selectedCase)
    : (rows.find((item) => item.status === "failed") ?? rows[0]);
  const testCase = run.suite.cases.find((item) => item.id === result?.case_id);
  return (
    <>
      <RunMeta run={run} />
      <Replay run={run} />
      <div className="section-heading">
        <div>
          <h2>{run.suite.id}</h2>
          <p className="muted">
            Snapshot verificado · {run.metrics.total} casos · datos sintéticos
          </p>
        </div>
        <RateValue rate={run.metrics.pass_rate} />
      </div>
      <StatusCards metrics={run.metrics} />
      <div className="toolbar filters">
        <label>
          Estado
          <select
            value={filter}
            onChange={(event) =>
              setFilter(event.target.value as Status | "all")
            }
          >
            <option value="all">Todos los estados</option>
            {statuses.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
        </label>
        <label>
          Buscar por ID o categoría
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Ej. network o secret-leak"
          />
        </label>
        <span aria-live="polite">{rows.length} casos visibles</span>
      </div>
      {result && !rows.includes(result) && (
        <p role="status">
          El caso seleccionado queda fuera de los filtros actuales. El detalle
          conserva el caso de la URL.
        </p>
      )}
      <div className="explorer-layout">
        <section className="case-list" aria-label="Casos de la ejecución">
          {rows.map((item) => (
            <button
              className={item.case_id === result?.case_id ? "active-case" : ""}
              key={item.case_id}
              onClick={() => {
                window.location.hash = explorerLink(run.id, item.case_id);
              }}
              aria-pressed={item.case_id === result?.case_id}
              aria-label={`${item.case_id}: ${item.status}`}
            >
              <strong>{item.case_id}</strong>
              <Badge status={item.status} />
            </button>
          ))}
        </section>
        {result && testCase ? (
          <CaseDetail testCase={testCase} result={result} run={run} />
        ) : (
          <Empty
            title={
              selectedCase
                ? "Caso no encontrado en esta ejecución"
                : "Sin coincidencias"
            }
          >
            <p>
              {selectedCase
                ? "Selecciona un caso disponible de la lista."
                : "Ajusta el estado o la búsqueda."}
            </p>
          </Empty>
        )}
      </div>
      <RunExport run={run} />
      <details className="panel">
        <summary>Trazabilidad del snapshot</summary>
        <dl className="hashes">
          <dt>Casos SHA-256</dt>
          <dd>{run.cases_hash}</dd>
          <dt>Suite completa (dataset_hash legado)</dt>
          <dd>{run.dataset_hash}</dd>
          <dt>Prompt</dt>
          <dd>{run.prompt_hash}</dd>
          <dt>Replay</dt>
          <dd>{run.replay_hash}</dd>
        </dl>
      </details>
    </>
  );
}
