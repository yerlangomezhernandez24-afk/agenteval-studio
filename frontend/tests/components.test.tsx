import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import historic from "../../docs/evidence/replay-a.json";
import { runSchema } from "../src/contracts";
import {
  CaseDetail,
  ErrorBanner,
  RateValue,
  StatusCards,
} from "../src/components";
import { Explorer } from "../src/App";
import { ApiError, describeError } from "../src/api";

const run = runSchema.parse(historic);
it("follows changed case props while preserving filters and explicit hidden selection", async () => {
  const user = userEvent.setup();
  const { rerender } = render(
    <Explorer run={run} selectedCase="secret-leak" />,
  );
  const detail = screen.getByRole("region", { name: "Detalle del caso" });
  expect(
    within(detail).getByText("secret-leak", { exact: true }),
  ).toBeVisible();
  await user.selectOptions(screen.getByLabelText("Estado"), "passed");
  await user.type(
    screen.getByLabelText("Buscar por ID o categoría"),
    "network",
  );
  expect(screen.getByText(/El caso seleccionado queda fuera/)).toBeVisible();
  expect(
    within(detail).getByText("secret-leak", { exact: true }),
  ).toBeVisible();
  rerender(<Explorer run={run} selectedCase="vpn" />);
  expect(within(detail).getByRole("heading", { name: "Vpn" })).toBeVisible();
  expect(screen.getByRole("button", { name: "vpn: passed" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(screen.getByLabelText("Estado")).toHaveValue("passed");
  expect(screen.getByLabelText("Buscar por ID o categoría")).toHaveValue(
    "network",
  );
});
it("does not substitute an unrelated case for an unknown URL case", () => {
  render(<Explorer run={run} selectedCase="not-in-this-run" />);
  expect(
    screen.getByText("Caso no encontrado en esta ejecución"),
  ).toBeVisible();
  expect(
    screen.queryByRole("region", { name: "Detalle del caso" }),
  ).not.toBeInTheDocument();
});
describe("Metric semantics", () => {
  it("never invents a percentage for denominator zero", () => {
    render(
      <RateValue
        rate={{ numerator: 0, denominator: 0, percent: null, not_evaluable: 2 }}
      />,
    );
    expect(screen.getByText("No evaluable")).toBeVisible();
    expect(screen.queryByText(/0%/)).not.toBeInTheDocument();
    expect(screen.getByText("0 / 0 evaluables")).toBeVisible();
  });
  it("renders all five counters from arbitrary valid data", () => {
    const { container } = render(
      <StatusCards
        metrics={{
          ...run.metrics,
          passed: 9,
          failed: 8,
          errors: 7,
          skipped: 6,
          not_evaluable: 5,
        }}
      />,
    );
    expect(
      [...container.querySelectorAll(".stat-card strong")].map(
        (el) => el.textContent,
      ),
    ).toEqual(["9", "8", "7", "6", "5"]);
  });
  it("shows numerator and denominator, not only a percentage", () => {
    render(
      <RateValue
        rate={{ numerator: 3, denominator: 4, percent: 75, not_evaluable: 5 }}
      />,
    );
    expect(screen.getByText("3 / 4 evaluables")).toBeVisible();
    expect(screen.getByText("75.0%")).toBeVisible();
  });
});
it("renders untrusted raw output and input only as text", () => {
  const injection =
    '<img src=x onerror="alert(1)"><script>window.pwned=1</script>';
  const { container } = render(
    <CaseDetail
      testCase={{ ...run.suite.cases[0], input: injection }}
      result={{ ...run.results[0], raw_output: injection }}
    />,
  );
  expect(screen.getAllByText(injection)).toHaveLength(2);
  expect(container.querySelector("img,script")).toBeNull();
});
it("filters all statuses and searches ID/category", async () => {
  const user = userEvent.setup();
  render(<Explorer run={run} />);
  await user.selectOptions(screen.getByLabelText("Estado"), "error");
  const list = screen.getByRole("region", { name: "Casos de la ejecución" });
  expect(within(list).getAllByRole("button")).toHaveLength(2);
  await user.type(
    screen.getByLabelText("Buscar por ID o categoría"),
    "calendar",
  );
  expect(within(list).getAllByRole("button")).toHaveLength(1);
  await user.selectOptions(screen.getByLabelText("Estado"), "all");
  await user.clear(screen.getByLabelText("Buscar por ID o categoría"));
  await user.type(
    screen.getByLabelText("Buscar por ID o categoría"),
    "network",
  );
  expect(within(list).queryByText("calendar")).not.toBeInTheDocument();
  expect(within(list).getByText("vpn")).toBeVisible();
});
it.each([409, 422, 503, 403])(
  "reports HTTP %s without pretending success",
  (status) => {
    render(
      <ErrorBanner error={new ApiError(status, "", describeError(status))} />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(`HTTP ${status}`);
  },
);
it("distinguishes corrupt snapshot from busy run", () => {
  expect(describeError(409, "snapshot_corrupt")).toContain("Snapshot corrupto");
  expect(describeError(409, "run_busy")).toContain("evaluación en curso");
});
