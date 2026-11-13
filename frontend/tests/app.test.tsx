import { afterEach, expect, it, vi } from "vitest";
import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import App from "../src/App";
import { api } from "../src/api";
import { runSchema } from "../src/contracts";
import historic from "../../docs/evidence/replay-a.json";

afterEach(() => {
  vi.restoreAllMocks();
  window.location.hash = "";
});
it("prevents a second synchronous click and confirms the created run", async () => {
  const run = runSchema.parse(historic);
  vi.spyOn(api, "health").mockResolvedValue({
    status: "ok",
    provider: "REPLAY / SIMULATED OUTPUT",
  });
  vi.spyOn(api, "suite").mockResolvedValue(run.suite);
  vi.spyOn(api, "runs").mockResolvedValue({ run_ids: [] });
  vi.spyOn(api, "run").mockResolvedValue(run);
  let finish: (value: typeof run) => void = () => {};
  const execute = vi.spyOn(api, "execute").mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  render(<App />);
  const button = screen.getByRole("button", {
    name: "Ejecutar suite sintética",
  });
  await waitFor(() => expect(button).toBeEnabled());
  fireEvent.click(button);
  fireEvent.click(button);
  expect(execute).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("button", { name: "Ejecutando…" })).toBeDisabled();
  await act(async () => finish(run));
  expect(
    await screen.findByText(
      "HTTP 201 · Ejecución guardada. 36 casos procesados.",
    ),
  ).toBeVisible();
});
