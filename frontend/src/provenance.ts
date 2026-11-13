import type { Run } from "./contracts";

export function rawDescription(run?: Run): string {
  if (!run) return "RAW del proveedor";
  if (run.provider === "ReplayProvider")
    return "RAW de replay sintético; sin inferencia de IA";
  return run.provenance === "http_test_double"
    ? "RAW sintético de un doble HTTP de pruebas; sin modelo real"
    : "RAW de inferencia auténtica con Ollama local";
}
