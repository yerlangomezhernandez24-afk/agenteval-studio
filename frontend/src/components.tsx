import type { ReactNode } from "react";
import { rawDescription } from "./provenance";
import { ApiError } from "./api";
import { statuses } from "./contracts";
import type {
  CaseResult,
  Metrics,
  Rate,
  Status,
  TestCase,
  Run,
} from "./contracts";

const labels: Record<Status, string> = {
  passed: "Aprobados",
  failed: "Fallidos",
  error: "Errores",
  skipped: "Omitidos",
  not_evaluable: "No evaluables",
};
export function Badge({ status }: { status: Status }) {
  return (
    <span className={`badge ${status}`}>
      <i aria-hidden="true" />
      {status}
    </span>
  );
}
export function Replay({ run }: { run?: Run | null }) {
  return (
    <span className="replay">
      {run?.label ?? "REPLAY / SIMULATED OUTPUT"}
      {run?.provider === "OllamaLocal" && (
        <>
          {" "}
          · {run.model} ·{" "}
          {run.provenance === "http_test_double"
            ? "HTTP TEST DOUBLE / NO MODELO REAL"
            : "OLLAMA LOCAL"}
        </>
      )}
    </span>
  );
}
export function ErrorBanner({
  error,
  retry,
}: {
  error: Error;
  retry?: () => void;
}) {
  return (
    <div className="error-banner" role="alert">
      <strong>
        {error instanceof ApiError
          ? `HTTP ${error.status || "—"} · ${error.code || "error"}`
          : "No disponible"}
      </strong>
      <p>{error.message}</p>
      {retry && <button onClick={retry}>Volver a consultar</button>}
    </div>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="empty">
      <span aria-hidden="true" className="empty-mark">
        ◎
      </span>
      <h3>{title}</h3>
      <div>{children}</div>
    </div>
  );
}
export function RateValue({ rate }: { rate: Rate }) {
  return (
    <div className="rate-value">
      <strong>
        {rate.denominator === 0
          ? "No evaluable"
          : `${rate.percent?.toFixed(1)}%`}
      </strong>
      <span>
        {rate.numerator} / {rate.denominator} evaluables
      </span>
    </div>
  );
}
export function StatusCards({ metrics }: { metrics: Metrics }) {
  const values = {
    passed: metrics.passed,
    failed: metrics.failed,
    error: metrics.errors,
    skipped: metrics.skipped,
    not_evaluable: metrics.not_evaluable,
  };
  return (
    <div className="status-grid">
      {statuses.map((status) => (
        <section className={`stat-card ${status}`} key={status}>
          <span>{labels[status]}</span>
          <strong>{values[status]}</strong>
          <small>{status}</small>
        </section>
      ))}
    </div>
  );
}
export function Distribution({ metrics }: { metrics: Metrics }) {
  const values = [
    metrics.passed,
    metrics.failed,
    metrics.errors,
    metrics.skipped,
    metrics.not_evaluable,
  ];
  return (
    <svg
      className="distribution"
      viewBox="0 0 1000 28"
      preserveAspectRatio="none"
      role="img"
      aria-label={statuses
        .map((s, i) => `${labels[s]} ${values[i]}`)
        .join(", ")}
    >
      {statuses.map((status, index) => {
        const width = metrics.total
          ? (1000 * values[index]) / metrics.total
          : 0;
        const x = metrics.total
          ? (values.slice(0, index).reduce((sum, value) => sum + value, 0) *
              1000) /
            metrics.total
          : 0;
        return (
          <rect
            key={status}
            className={status}
            x={x}
            y="0"
            width={width}
            height="28"
          />
        );
      })}
    </svg>
  );
}
export function CriteriaTable({ metrics }: { metrics: Metrics }) {
  return (
    <>
      <div
        className="table-scroll criteria-desktop"
        tabIndex={0}
        role="region"
        aria-label="Métricas por criterio"
      >
        <table>
          <caption>
            Cumplimiento por criterio · denominadores independientes
          </caption>
          <thead>
            <tr>
              <th>Criterio</th>
              <th>Cumplimiento</th>
              <th>Aprobados / evaluables</th>
              <th>No evaluables*</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(metrics.criteria).map(([name, rate]) => (
              <tr key={name}>
                <th scope="row">
                  <code>{name}</code>
                </th>
                <td>
                  <div className="criterion-rate">
                    <progress
                      max="100"
                      value={rate.denominator ? (rate.percent ?? 0) : 0}
                      aria-label={name}
                    />
                    <span>
                      {rate.denominator ? `${rate.percent?.toFixed(1)}%` : "—"}
                    </span>
                  </div>
                </td>
                <td>
                  {rate.numerator} / {rate.denominator}
                </td>
                <td>{rate.not_evaluable}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="criteria-mobile">
        {Object.entries(metrics.criteria).map(([name, rate]) => (
          <section key={name}>
            <h3>
              <code>{name}</code>
              <span>
                {rate.denominator
                  ? `${rate.percent?.toFixed(1)}%`
                  : "No evaluable"}
              </span>
            </h3>
            <dl>
              <dt>Aprobados / evaluables</dt>
              <dd>
                {rate.numerator} / {rate.denominator}
              </dd>
              <dt>No evaluables*</dt>
              <dd>{rate.not_evaluable}</dd>
            </dl>
          </section>
        ))}
      </div>
      <p className="table-note">
        * Incluye no aplicables, errores y omisiones. No mide seguridad
        universal.
      </p>
    </>
  );
}
export function CaseDetail({
  testCase,
  result,
  run,
}: {
  testCase: TestCase;
  result?: CaseResult;
  run?: Run;
}) {
  return (
    <section className="case-detail" aria-label="Detalle del caso">
      <div className="section-heading">
        <div>
          <p className="eyebrow">{testCase.id}</p>
          <h2>{testCase.name}</h2>
        </div>
        {result && <Badge status={result.status} />}
      </div>
      <div className="tags">
        <span>{testCase.category}</span>
        <span
          className={testCase.criticality === "critical" ? "critical-tag" : ""}
        >
          Criticidad: {testCase.criticality}
        </span>
        {testCase.tags.map((tag) => (
          <span key={tag}>{tag}</span>
        ))}
      </div>
      <div className="input-box">
        <h3>Entrada sintética</h3>
        <p>{testCase.input}</p>
        <small>{testCase.rationale}</small>
      </div>
      <div className="comparison">
        <section>
          <h3>Oráculo esperado</h3>
          <pre>{JSON.stringify(testCase.expected, null, 2)}</pre>
          {testCase.contains.length > 0 && (
            <p>Debe contener: {testCase.contains.join(", ")}</p>
          )}
          {testCase.excludes.length > 0 && (
            <p>No debe contener: {testCase.excludes.join(", ")}</p>
          )}
        </section>
        {result && (
          <section>
            <h3>Salida raw</h3>
            <Replay run={run} />
            <pre className="raw-output">
              {result.raw_output ?? "Sin respuesta del proveedor"}
            </pre>
            <small>{result.reason}</small>
          </section>
        )}
      </div>
      {result && (
        <>
          <div className="detail-meta">
            <span>
              {run?.provider === "OllamaLocal"
                ? "Tiempo HTTP local:"
                : "Tiempo de replay:"}{" "}
              {result.latency_ms === null
                ? "—"
                : `${result.latency_ms.toFixed(3)} ms`}
            </span>
            <span>Error: {result.error_code ?? "ninguno"}</span>
          </div>
          {run?.provider === "OllamaLocal" && (
            <p>
              Generación reportada por proveedor:{" "}
              {run.attempts.find((a) => a.case_id === testCase.id)
                ?.generation_duration_ns ?? "no disponible"}{" "}
              ns.
            </p>
          )}
          <p>
            {rawDescription(run)}. Guardado localmente y mostrado como texto; no
            se ejecuta como código.
          </p>
          <h3>Validaciones independientes</h3>
          <ul className="checks">
            {result.checks.map((check) => (
              <li key={check.criterion}>
                <span className={`check-outcome ${check.outcome}`}>
                  {check.outcome}
                </span>
                <div>
                  <code>{check.criterion}</code>
                  <p>{check.reason}</p>
                </div>
              </li>
            ))}
          </ul>
          <p className="muted">
            Son comprobaciones de contrato; no un dictamen universal de
            seguridad.
          </p>
        </>
      )}
    </section>
  );
}
