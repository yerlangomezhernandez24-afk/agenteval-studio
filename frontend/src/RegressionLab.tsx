import { useCallback, useState } from "react";
import { api } from "./api";
import { changeNames, changes } from "./comparison";
import type { Comparison } from "./comparison";
import {
  Badge,
  Empty,
  ErrorBanner,
  RateValue,
  StatusCards,
} from "./components";
import { explorerLink, useRemote } from "./hooks";
import "./regression.css";

function link(params: URLSearchParams, changes: Record<string, string>) {
  const next = new URLSearchParams(params);
  Object.entries(changes).forEach(([key, value]) =>
    value ? next.set(key, value) : next.delete(key),
  );
  return `#/regression?${next}`;
}
function RunOption({ id }: { id: string }) {
  const resource = useRemote(
    id,
    useCallback((signal) => api.run(id, signal), [id]),
  );
  return (
    <option value={id}>
      {resource.data
        ? `${resource.data.provider} · ${resource.data.provider === "OllamaLocal" ? resource.data.model + " / " + resource.data.provenance : resource.data.suite.replay_version} · ${id}`
        : `${id}${resource.error ? " · no disponible" : ""}`}
    </option>
  );
}

export default function RegressionLab({ params }: { params: URLSearchParams }) {
  const a = params.get("a") ?? "",
    b = params.get("b") ?? "";
  const rawOffset = Number(params.get("offset") ?? 0);
  const offset =
    Number.isInteger(rawOffset) && rawOffset >= 0 && rawOffset <= 1_000_000
      ? rawOffset
      : 0;
  const history = useRemote(
    `lab-history-${offset}`,
    useCallback((signal) => api.runs(offset, signal), [offset]),
  );
  const report = useRemote(
    `compare-${a}-${b}`,
    useCallback(
      (signal) =>
        a && b ? api.comparison(a, b, signal) : Promise.resolve(null),
      [a, b],
    ),
  );
  const [downloadError, setDownloadError] = useState<Error>();
  const [downloading, setDownloading] = useState(false);
  const [notice, setNotice] = useState("");
  async function download(format: "json" | "csv") {
    if (downloading) return;
    setDownloading(true);
    setDownloadError(undefined);
    setNotice("");
    try {
      const blob = await api.download(a, b, format);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `agenteval-comparison.${format}`;
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      setNotice("Descarga preparada desde el informe verificado.");
    } catch (error) {
      setDownloadError(
        error instanceof Error ? error : new Error("No se pudo descargar."),
      );
    } finally {
      setDownloading(false);
    }
  }
  const ids = history.data?.run_ids ?? [];
  return (
    <>
      <section className="panel lab-intro">
        <p className="eyebrow">A → B · CAMBIOS OBSERVABLES</p>
        <h2>La misma suite. Dos ejecuciones.</h2>
        <p>
          Compara contratos y revisa cada regresión. Un porcentaje global puede
          ocultar un caso crítico.
        </p>
        <div className="lab-selectors">
          {[
            ["a", a, "A · referencia"],
            ["b", b, "B · candidata"],
          ].map(([key, value, label]) => (
            <label key={key}>
              {label}
              <select
                value={value}
                onChange={(event) => {
                  window.location.hash = link(params, {
                    [key]: event.target.value,
                    case: "",
                  });
                }}
              >
                <option value="">Selecciona una ejecución</option>
                {value && !ids.includes(value) && <RunOption id={value} />}
                {ids.map((id) => (
                  <RunOption key={id} id={id} />
                ))}
              </select>
            </label>
          ))}
        </div>
        <div className="pagination">
          <button
            disabled={offset === 0}
            onClick={() => {
              window.location.hash = link(params, {
                offset: String(Math.max(0, offset - 10)),
              });
            }}
          >
            ← Ejecuciones anteriores
          </button>
          <span>Página {offset / 10 + 1} · 10 por página</span>
          <button
            disabled={ids.length < 10 || offset === 1_000_000}
            onClick={() => {
              window.location.hash = link(params, {
                offset: String(Math.min(1_000_000, offset + 10)),
              });
            }}
          >
            Más ejecuciones →
          </button>
        </div>
      </section>
      {history.error && <ErrorBanner error={history.error} />}
      {!history.loading && !history.error && ids.length === 0 && !a && !b && (
        <Empty title="Todavía no hay ejecuciones">
          <p>Ejecuta la base y la variante mixta desde Evaluation Runs.</p>
          <a href="#/runs">Ir a ejecutar →</a>
        </Empty>
      )}
      {(!a || !b) && (
        <p role="status">Elige A y B para calcular la comparación.</p>
      )}
      {a && b && report.loading && (
        <p role="status">Verificando snapshots y comparabilidad…</p>
      )}
      {report.error && <ErrorBanner error={report.error} />}
      {report.data && (
        <>
          <div className="toolbar">
            <button
              disabled={downloading}
              onClick={() => void download("json")}
            >
              Descargar JSON
            </button>
            <button disabled={downloading} onClick={() => void download("csv")}>
              Descargar CSV
            </button>
            <span aria-live="polite">{notice}</span>
          </div>
          {downloadError && <ErrorBanner error={downloadError} />}
          <ComparisonView report={report.data} params={params} />
        </>
      )}
    </>
  );
}

export function ComparisonView({
  report,
  params,
}: {
  report: Comparison;
  params: URLSearchParams;
}) {
  const filter = params.get("change") ?? "all";
  const rows = report.cases.filter(
    (c) => filter === "all" || c.change === filter,
  );
  const selected = report.cases.find((c) => c.case_id === params.get("case"));
  const detailLink = (run: string, id: string) =>
    `${explorerLink(run, id)}&return=${encodeURIComponent(link(params, {}))}`;
  return (
    <>
      <section
        className={`panel ${report.compatible ? "" : "lab-incompatible"}`}
        aria-label="Compatibilidad"
      >
        <h2>
          {report.compatible
            ? "Ejecuciones comparables"
            : "Ejecuciones no comparables"}
        </h2>
        {report.reasons.map((reason) => (
          <p key={reason}>{reason}</p>
        ))}
        <p>{report.warning}</p>
        <div className="tags">
          {["a", "b"].map((side) => (
            <span key={side}>
              {side.toUpperCase()}: {report.fingerprints[side]?.provider}{" "}
              {report.fingerprints[side]?.model ??
                report.fingerprints[side]?.replay_version}{" "}
              ·{" "}
              {report.fingerprints[side]?.provenance ?? "deterministic_replay"}{" "}
              · criterios {report.fingerprints[side]?.criteria_version}
              {report.fingerprints[side]?.criteria_version === "1.0"
                ? " · HISTÓRICO / LEGADO"
                : ""}
            </span>
          ))}
        </div>
      </section>
      {report.compatible && (
        <>
          <div className="lab-counts">
            {changes.map((change) => (
              <article className="panel" key={change}>
                <span>{changeNames[change]}</span>
                <strong>{report.counts[change]}</strong>
              </article>
            ))}
          </div>
          <section className="panel critical-panel">
            <h2>Regresiones críticas: {report.critical_regressions.length}</h2>
            <p>
              {report.critical_regressions.join(", ") ||
                "Ninguna en esta comparación."}
            </p>
            <p>
              Casos críticos sin aprobar en B:{" "}
              {report.critical_attention.join(", ") || "ninguno"}.
            </p>
          </section>
          <div className="lab-metrics">
            {[
              ["A", report.metrics_a],
              ["B", report.metrics_b],
            ].map(
              ([label, metrics]) =>
                typeof metrics !== "string" && (
                  <section className="panel" key={String(label)}>
                    <h3>Estados {String(label)}</h3>
                    <StatusCards metrics={metrics} />
                    <RateValue rate={metrics.pass_rate} />
                  </section>
                ),
            )}
          </div>
          <section className="panel">
            <h2>Denominadores a la vista</h2>
            <div className="table-scroll">
              <table>
                <caption>
                  Cambios B − A. pp = puntos porcentuales; — = no evaluable.
                </caption>
                <thead>
                  <tr>
                    <th>Criterio</th>
                    <th>A</th>
                    <th>B</th>
                    <th>Δ pp</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(report.rates).map(([name, rate]) => (
                    <tr key={name}>
                      <th>{name}</th>
                      <td>
                        {rate.a.numerator} / {rate.a.denominator} ·{" "}
                        {rate.a.percent === null
                          ? "No evaluable"
                          : `${rate.a.percent.toFixed(1)}%`}
                      </td>
                      <td>
                        {rate.b.numerator} / {rate.b.denominator} ·{" "}
                        {rate.b.percent === null
                          ? "No evaluable"
                          : `${rate.b.percent.toFixed(1)}%`}
                      </td>
                      <td>{rate.percentage_points?.toFixed(1) ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
          <section className="panel">
            <div className="section-heading">
              <h2>Cambios por caso</h2>
              <label>
                Filtrar cambios
                <select
                  value={filter}
                  onChange={(event) => {
                    window.location.hash = link(params, {
                      change: event.target.value,
                    });
                  }}
                >
                  <option value="all">Todos</option>
                  {changes.map((change) => (
                    <option key={change} value={change}>
                      {changeNames[change]}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <p aria-live="polite">{rows.length} cambios visibles</p>
            <div className="lab-cases">
              {rows.map((c) => (
                <button
                  key={c.case_id}
                  aria-pressed={selected?.case_id === c.case_id}
                  onClick={() => {
                    window.location.hash = link(params, { case: c.case_id });
                  }}
                >
                  <strong>{c.case_id}</strong>
                  <span>
                    {changeNames[c.change]}
                    {c.critical ? " · CRÍTICO" : ""}
                  </span>
                  <span>
                    <Badge status={c.a_status} /> →{" "}
                    <Badge status={c.b_status} />
                  </span>
                </button>
              ))}
            </div>
          </section>
          {selected && (
            <section className="panel" aria-label="Detalle de comparación">
              <h2>{selected.name}</h2>
              <p>
                {selected.case_id} · {changeNames[selected.change]}
              </p>
              <div className="toolbar">
                <a
                  className="button"
                  href={detailLink(report.a_id, selected.case_id)}
                >
                  Inspeccionar A
                </a>
                <a
                  className="button"
                  href={detailLink(report.b_id, selected.case_id)}
                >
                  Inspeccionar B
                </a>
              </div>
              <p>
                Error A: {selected.a_error ?? "ninguno"} · B:{" "}
                {selected.b_error ?? "ninguno"}
              </p>
              <p>
                {report.label === "REPLAY / SIMULATED OUTPUT"
                  ? "Latencia de replay local A:"
                  : "Tiempo HTTP local A:"}{" "}
                {selected.latency_a_ms?.toFixed(3) ?? "—"} ms · B:{" "}
                {selected.latency_b_ms?.toFixed(3) ?? "—"} ms. No mide
                inferencia ni significa mejora del modelo.
              </p>
              <ul className="checks">
                {selected.checks.map((c) => (
                  <li key={c.criterion}>
                    <code>{c.criterion}</code>
                    <span>
                      {c.a} → {c.b}
                    </span>
                    <span>{changeNames[c.change]}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </>
  );
}
