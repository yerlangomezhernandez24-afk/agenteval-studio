import { render, screen, waitFor, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import OllamaControls from "../src/OllamaControls";

afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.unstubAllGlobals();
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
  version: "http-double-only",
  error: null,
  provenance: "http_test_double",
  prompts: ["support-json-v1"],
};
function mock(data: unknown, ok = true) {
  const fetcher = vi
    .fn()
    .mockResolvedValue({ ok, status: ok ? 200 : 503, json: async () => data });
  vi.stubGlobal("fetch", fetcher);
  return fetcher;
}
test("absent Ollama leaves inference disabled and explains replay", async () => {
  mock({ ...status, available: false, models: [], error: "connection_error" });
  render(<OllamaControls onComplete={() => {}} />);
  expect(await screen.findByText(/Ollama no disponible/)).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Ejecutar 3 casos con Ollama" }),
  ).toBeDisabled();
});
test("available without models never downloads or selects", async () => {
  const fetcher = mock({ ...status, models: [] });
  render(<OllamaControls onComplete={() => {}} />);
  expect(
    await screen.findByText(/disponible sin modelos locales/),
  ).toBeVisible();
  expect(fetcher).toHaveBeenCalledTimes(1);
});
test("malformed response is rejected", async () => {
  mock({ available: true, models: "untrusted" });
  render(<OllamaControls onComplete={() => {}} />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "contrato esperado",
  );
});
test("network error keeps execution disabled", async () => {
  mock({}, false);
  render(<OllamaControls onComplete={() => {}} />);
  expect(await screen.findByRole("alert")).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Ejecutar 3 casos con Ollama" }),
  ).toBeDisabled();
});
test("explicit model selection, CSRF job and authentic terminal state", async () => {
  const fetcher = mock(status);
  const user = userEvent.setup();
  const completed = vi.fn();
  render(<OllamaControls onComplete={completed} />);
  await screen.findByText(/Ollama disponible · 1/);
  const button = screen.getByRole("button", {
    name: "Ejecutar 3 casos con Ollama",
  });
  expect(button).toBeDisabled();
  await user.selectOptions(screen.getByLabelText("Modelo local"), model.name);
  expect(button).toBeEnabled();
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
    .mockResolvedValueOnce({ ok: true, json: async () => job })
    .mockResolvedValue({
      ok: true,
      json: async () => ({
        ...job,
        status: "completed",
        completed_cases: 3,
        run_id: "00000000-0000-4000-8000-000000000002",
      }),
    });
  await user.click(button);
  await waitFor(() => expect(completed).toHaveBeenCalled());
  expect(
    await screen.findByRole("link", { name: /Ver snapshot experimental/ }),
  ).toBeVisible();
  expect(fetcher.mock.calls[2][0]).toContain(
    "/api/ollama/jobs?model=synthetic-test%3Atiny",
  );
  expect(fetcher.mock.calls[2][1].headers).toEqual({
    "X-CSRF-Token": "a".repeat(44),
  });
});
