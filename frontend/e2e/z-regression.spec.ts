import { test, expect } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { runSchema } from "../src/contracts";
import { comparisonSchema } from "../src/comparison";

const evidence = path.resolve(
  process.env.AGENTEVAL_PHASE_EVIDENCE ?? "../docs/evidence-phase3",
);
const seed = (mode: string) =>
  execFileSync(
    process.env.AGENTEVAL_PYTHON!,
    [path.resolve("../tests/seed_e2e.py"), process.env.AGENTEVAL_E2E_DB!, mode],
    { encoding: "utf-8", windowsHide: true },
  ).trim();

test("installed variants, real A/B, regression filter, case links, exports and responsive UI", async ({
  page,
}) => {
  test.setTimeout(60_000);
  await page.goto("/#/runs");
  async function execute(variant: string) {
    await page.getByLabel("Variante replay").selectOption(variant);
    const pending = page.waitForResponse(
      (r) =>
        new URL(r.url()).pathname === "/api/runs" &&
        r.request().method() === "POST",
    );
    await page
      .getByRole("button", { name: "Ejecutar suite sintética" })
      .click();
    const response = await pending;
    expect(response.status()).toBe(201);
    const run = runSchema.parse(await response.json());
    await expect(page.getByText(run.id, { exact: true })).toBeVisible();
    return run;
  }
  const a = await execute("baseline-v1");
  await page.goto("/#/runs");
  const b = await execute("mixed-v1");
  expect(a.suite.replay_version).not.toBe(b.suite.replay_version);
  expect(a.cases_hash).toBe(b.cases_hash);
  await page.getByRole("link", { name: /Regression Lab/ }).click();
  await page.getByLabel("A · referencia").selectOption(a.id);
  await page.getByLabel("B · candidata").selectOption(b.id);
  await expect(
    page.getByText("Ejecuciones comparables", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("Regresiones críticas: 1")).toBeVisible();
  await page.getByLabel("Filtrar cambios").selectOption("regression");
  await expect(page.getByText("2 cambios visibles")).toBeVisible();
  await page.getByRole("button", { name: /^outage/ }).click();
  const labHash = await page.evaluate(() => location.hash);
  await page.getByRole("link", { name: "Inspeccionar B" }).click();
  await expect(
    page
      .getByRole("region", { name: "Detalle del caso" })
      .getByRole("heading", { name: "Outage", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".raw-output")).toHaveText("{}");
  await page.getByRole("link", { name: "← Volver a comparación" }).click();
  expect(await page.evaluate(() => location.hash)).toBe(labHash);
  await expect(page.getByLabel("Filtrar cambios")).toHaveValue("regression");
  for (const format of ["json", "csv"] as const) {
    const pending = page.waitForEvent("download");
    await page
      .getByRole("button", { name: `Descargar ${format.toUpperCase()}` })
      .click();
    const download = await pending;
    expect(download.suggestedFilename()).toBe(`agenteval-comparison.${format}`);
    const file = path.join(evidence, `browser-comparison.${format}`);
    await download.saveAs(file);
    if (format === "json")
      expect(
        comparisonSchema.parse(JSON.parse(readFileSync(file, "utf-8"))).counts
          .regression,
      ).toBe(2);
    else expect(readFileSync(file, "utf-8")).toContain("'outage");
  }
  mkdirSync(path.join(evidence, "screenshots"), { recursive: true });
  for (const width of [1366, 768, 390]) {
    await page.setViewportSize({ width, height: 950 });
    await expect(
      page.getByText("REPLAY / SIMULATED OUTPUT").first(),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: path.join(evidence, "screenshots", `regression-${width}.png`),
      fullPage: true,
    });
  }
  const legacy = seed("legacy");
  await page.goto(`/#/regression?a=${a.id}&b=${legacy}`);
  await expect(
    page.getByText("Ejecuciones no comparables", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText(/Versiones de criterios distintas/),
  ).toBeVisible();
  const corrupt = seed("corrupt");
  await page.goto(`/#/regression?a=${a.id}&b=${corrupt}`);
  await expect(page.getByRole("alert")).toContainText("snapshot_corrupt");
  await expect(
    page.getByRole("button", { name: "Descargar JSON" }),
  ).toHaveCount(0);
  await page.goto(`/#/regression?a=invalid&b=${b.id}`);
  await expect(page.getByRole("alert")).toContainText("422");
});
