import { expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import replay from "../../docs/evidence/replay-a.json";
import double from "../../docs/evidence-phase4/http-double-snapshot.json";
import real from "../../docs/evidence-ollama-real/real-snapshot.json";
import { runSchema } from "../src/contracts";
import { CaseDetail } from "../src/components";
import RunExport from "../src/RunExport";

const examples = [
  [replay, "RAW de replay sintético; sin inferencia de IA"],
  [double, "RAW sintético de un doble HTTP de pruebas; sin modelo real"],
  [real, "RAW de inferencia auténtica con Ollama local"],
] as const;

it.each(examples)(
  "identifies stored RAW provenance in case details %#",
  (snapshot, text) => {
    const run = runSchema.parse(snapshot);
    render(
      <CaseDetail
        run={run}
        testCase={run.suite.cases[0]}
        result={run.results[0]}
      />,
    );
    expect(screen.getByText(text, { exact: false })).toBeVisible();
    expect(
      screen.queryByText(/RAW sintético guardado localmente; nunca ejecutado/),
    ).toBeNull();
    expect(screen.getByText(/no se ejecuta como código/)).toBeVisible();
  },
);
it.each(examples)("identifies JSON export provenance %#", (snapshot, text) => {
  render(<RunExport run={runSchema.parse(snapshot)} />);
  expect(
    screen.getByText(`JSON incluye ${text}`, { exact: false }),
  ).toBeVisible();
  expect(screen.getByText(/sin RAW/)).toBeVisible();
});
