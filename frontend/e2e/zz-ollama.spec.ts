import { test, expect } from "@playwright/test";
import { mkdirSync, writeFileSync, readFileSync } from "node:fs";
import path from "node:path";

test("experimental local HTTP double: selection, job, RAW, exports, mobile and cancellation", async ({
  page,
}) => {
  test.skip(
    process.env.AGENTEVAL_E2E_LOCAL_MOCK !== "1",
    "Requires explicit local HTTP double server",
  );
  const evidence = path.resolve(
    process.env.AGENTEVAL_PHASE_EVIDENCE ?? "../docs/evidence-phase4",
  );
  mkdirSync(evidence, { recursive: true });
  await page.goto("/#/runs");
  await page
    .getByRole("combobox", { name: "Proveedor", exact: true })
    .selectOption("ollama");
  await expect(
    page.getByText("HTTP TEST DOUBLE / NO MODELO REAL.", { exact: false }),
  ).toBeVisible();
  const execute = page.getByRole("button", {
    name: "Ejecutar 3 casos con Ollama",
  });
  await expect(execute).toBeDisabled();
  await page
    .getByRole("combobox", { name: "Modelo local", exact: true })
    .selectOption("synthetic-test:tiny");
  await expect(execute).toBeEnabled();
  for (const width of [1366, 768, 390]) {
    await page.setViewportSize({ width, height: 950 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: path.join(evidence, `ollama-controls-${width}.png`),
      fullPage: true,
    });
  }
  await page.setViewportSize({ width: 1366, height: 950 });
  const response = page.waitForResponse(
    (r) =>
      new URL(r.url()).pathname === "/api/ollama/jobs" &&
      r.request().method() === "POST",
  );
  await execute.click();
  expect((await response).status()).toBe(202);
  await expect(
    page.getByRole("link", { name: "Ver snapshot experimental" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Ver snapshot experimental" }).click();
  await expect(
    page.getByText("support-local-smoke", { exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByText("HTTP TEST DOUBLE / NO MODELO REAL", { exact: false })
      .first(),
  ).toBeVisible();
  const id = new URLSearchParams(page.url().split("?")[1]).get("run");
  const snapshot = await page.evaluate(
    async (runId) => (await fetch(`/api/runs/${runId}`)).json(),
    id,
  );
  expect(snapshot.provenance).toBe("http_test_double");
  expect(snapshot.metrics.total).toBe(3);
  writeFileSync(
    path.join(evidence, "http-double-snapshot.json"),
    JSON.stringify(snapshot, null, 2),
  );
  for (const format of ["JSON", "CSV"]) {
    const pendingDownload = page.waitForEvent("download");
    await page
      .getByRole("button", { name: `Exportar snapshot ${format}`, exact: true })
      .click();
    const download = await pendingDownload;
    const content = readFileSync((await download.path())!, "utf-8");
    expect(content).toContain("http_test_double");
    expect(content).toContain("LOCAL LLM / EXPERIMENTAL");
    writeFileSync(
      path.join(evidence, `http-double-export.${format.toLowerCase()}`),
      content,
    );
  }
  await page
    .getByRole("heading", { name: "support-local-smoke", exact: true })
    .click();
  for (const width of [1366, 768, 390]) {
    await page.setViewportSize({ width, height: 950 });
    await page.screenshot({
      path: path.join(evidence, `ollama-snapshot-${width}.png`),
      fullPage: true,
    });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBe(true);
  }
  await page.setViewportSize({ width: 1366, height: 950 });
  await page.goto("/#/runs");
  await page
    .getByRole("combobox", { name: "Proveedor", exact: true })
    .selectOption("ollama");
  await page
    .getByRole("combobox", { name: "Modelo local", exact: true })
    .selectOption("synthetic-test:tiny");
  await execute.click();
  await page.getByRole("button", { name: "Cancelar ejecución local" }).click();
  await expect(page.getByText(/cancelled ·/)).toBeVisible();
  await page.screenshot({
    path: path.join(evidence, "ollama-cancelled.png"),
    fullPage: true,
  });
});
