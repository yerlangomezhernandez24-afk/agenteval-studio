import { rawDescription } from "./provenance";
import { useState } from "react";
import type { Run } from "./contracts";
import { ErrorBanner } from "./components";

export default function RunExport({ run }: { run: Run }) {
  const [error, setError] = useState<Error>();
  const [pending, setPending] = useState(false);
  async function download(format: "json" | "csv") {
    setPending(true);
    setError(undefined);
    try {
      const response = await fetch(
        `/api/runs/${encodeURIComponent(run.id)}/export?format=${format}`,
        {
          credentials: "omit",
          cache: "no-store",
          signal: AbortSignal.timeout(15000),
        },
      );
      if (!response.ok)
        throw new Error(
          `HTTP ${response.status}. No se descargó el snapshot; vuelve a consultar su integridad.`,
        );
      if (
        !response.headers
          .get("content-type")
          ?.startsWith(format === "json" ? "application/json" : "text/csv")
      )
        throw new Error("Formato de exportación inesperado");
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = `agenteval-${run.provider}-${run.id}.${format}`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError(e instanceof Error ? e : new Error("Exportación fallida"));
    } finally {
      setPending(false);
    }
  }
  return (
    <div className="panel">
      <p>
        Exportar {run.label}. JSON incluye {rawDescription(run)}; CSV incluye
        checks y procedencia, sin RAW.
      </p>
      <div className="toolbar">
        <button disabled={pending} onClick={() => void download("json")}>
          Exportar snapshot JSON
        </button>
        <button disabled={pending} onClick={() => void download("csv")}>
          Exportar snapshot CSV
        </button>
      </div>
      {error && <ErrorBanner error={error} />}
    </div>
  );
}
