import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import OllamaControls from "../src/OllamaControls";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});
const model = {
  name: "synthetic-test:tiny",
  digest: "a".repeat(64),
  size: 1024,
  modified_at: "2026-11-06T00:00:00Z",
  family: "test",
  parameter_size: "",
  quantization_level: "",
};
const status = {
  available: true,
  models: [model],
  version: "double",
  error: null,
  provenance: "http_test_double",
  prompts: ["support-json-v1"],
};
test("storage denied does not crash experimental controls", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: async () => status }),
  );
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new DOMException("Denied", "SecurityError");
  });
  render(<OllamaControls onComplete={() => {}} />);
  expect(await screen.findByText(/Ollama disponible · 1/)).toBeVisible();
});
test("storage write failure cannot lose the accepted job", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue({ ok: true, json: async () => status });
  vi.stubGlobal("fetch", fetcher);
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new DOMException("Quota", "QuotaExceededError");
  });
  const user = userEvent.setup();
  render(<OllamaControls onComplete={() => {}} />);
  await screen.findByText(/Ollama disponible · 1/);
  await user.selectOptions(screen.getByLabelText("Modelo local"), model.name);
  const job = {
    id: "00000000-0000-4000-8000-000000000001",
    status: "running",
    completed_cases: 0,
    total_cases: 3,
    run_id: null,
    error: null,
    provenance: "http_test_double",
    model: model.name,
    elapsed_ms: 0,
  };
  fetcher
    .mockResolvedValueOnce({
      ok: true,
      json: async () => ({ csrf_token: "a".repeat(44) }),
    })
    .mockResolvedValue({ ok: true, json: async () => job });
  await user.click(
    screen.getByRole("button", { name: "Ejecutar 3 casos con Ollama" }),
  );
  expect(
    await screen.findByRole("button", { name: "Cancelar ejecución local" }),
  ).toBeVisible();
});

test("expired job stops polling and releases controls after server restart", async () => {
  const id = "00000000-0000-4000-8000-000000000001";
  sessionStorage.setItem("agenteval-local-job", id);
  let reads = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.endsWith("/ollama/status"))
        return { ok: true, json: async () => status };
      if (++reads === 1)
        return {
          ok: true,
          json: async () => ({
            id,
            status: "running",
            completed_cases: 0,
            total_cases: 3,
            run_id: null,
            error: null,
            provenance: "http_test_double",
            model: model.name,
            elapsed_ms: 0,
          }),
        };
      return {
        ok: false,
        status: 404,
        json: async () => ({ detail: "expired" }),
      };
    }),
  );
  render(<OllamaControls onComplete={() => {}} />);
  expect(
    await screen.findByText(/Job no disponible tras reinicio/),
  ).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "Cancelar ejecución local" }),
  ).not.toBeInTheDocument();
  expect(sessionStorage.getItem("agenteval-local-job")).toBeNull();
  expect(reads).toBe(2);
});
