import { afterEach, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import fixture from "../../docs/evidence-phase3/comparison.json";
import RegressionLab, { ComparisonView } from "../src/RegressionLab";
import { comparisonSchema } from "../src/comparison";
import { api } from "../src/api";

const report = comparisonSchema.parse(fixture);
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.location.hash = "";
});

it("shows real critical regressions even when aggregate pass rate is unchanged", () => {
  render(
    <ComparisonView
      report={report}
      params={new URLSearchParams("change=regression&case=outage")}
    />,
  );
  expect(screen.getByText("Regresiones críticas: 1")).toBeVisible();
  expect(screen.getByText("2 cambios visibles")).toBeVisible();
  expect(screen.getAllByText("16 / 32 evaluables")).toHaveLength(2);
  const detail = screen.getByRole("region", { name: "Detalle de comparación" });
  expect(within(detail).getByText(/outage/)).toBeVisible();
  expect(screen.getByRole("link", { name: "Inspeccionar B" })).toHaveAttribute(
    "href",
    expect.stringContaining("case=outage&return="),
  );
});
it("incompatible snapshots show reasons and no change scores", () => {
  render(
    <ComparisonView
      report={{
        ...report,
        compatible: false,
        reasons: ["Versiones de criterios distintas"],
        cases: [],
        rates: {},
      }}
      params={new URLSearchParams()}
    />,
  );
  expect(screen.getByText("Ejecuciones no comparables")).toBeVisible();
  expect(screen.queryByText("Cambios por caso")).not.toBeInTheDocument();
});
it("changes filters through the URL while preserving selections and case detail", async () => {
  const user = userEvent.setup();
  render(
    <ComparisonView
      report={report}
      params={
        new URLSearchParams(`a=${report.a_id}&b=${report.b_id}&case=outage`)
      }
    />,
  );
  await user.selectOptions(
    screen.getByLabelText("Filtrar cambios"),
    "regression",
  );
  expect(window.location.hash).toContain("change=regression");
  expect(window.location.hash).toContain("case=outage");
  expect(window.location.hash).toContain(`a=${report.a_id}`);
});
it("has a useful empty history state", async () => {
  vi.spyOn(api, "runs").mockResolvedValue({ run_ids: [] });
  render(<RegressionLab params={new URLSearchParams()} />);
  expect(await screen.findByText("Todavía no hay ejecuciones")).toBeVisible();
  expect(
    screen.queryByRole("button", { name: "Descargar JSON" }),
  ).not.toBeInTheDocument();
});
it("shows comparison API errors without success or download actions", async () => {
  vi.spyOn(api, "runs").mockResolvedValue({ run_ids: [] });
  vi.spyOn(api, "run").mockRejectedValue(new Error("No disponible"));
  vi.spyOn(api, "comparison").mockRejectedValue(
    new Error("Comparación rechazada"),
  );
  render(
    <RegressionLab
      params={new URLSearchParams(`a=${report.a_id}&b=${report.b_id}`)}
    />,
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Comparación rechazada",
  );
  expect(
    screen.queryByRole("button", { name: "Descargar JSON" }),
  ).not.toBeInTheDocument();
});
it("never downloads an HTTP error as a successful report", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ code: "snapshot_corrupt" }), {
        status: 409,
      }),
    ),
  );
  await expect(
    api.download(report.a_id, report.b_id, "csv"),
  ).rejects.toMatchObject({ status: 409, code: "snapshot_corrupt" });
});
