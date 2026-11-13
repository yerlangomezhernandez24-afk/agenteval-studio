import { test, expect } from "@playwright/test";
import { runSchema } from "../src/contracts";

test("case URL changes synchronize detail and selection without reload", async ({
  page,
  request,
}) => {
  const session = await request.get("/api/session");
  const { csrf_token: token } = (await session.json()) as {
    csrf_token: string;
  };
  const response = await request.post("/api/runs", {
    headers: { "X-CSRF-Token": token },
  });
  expect(response.status()).toBe(201);
  const run = runSchema.parse(await response.json());
  const assertCase = async (id: string) => {
    const item = run.suite.cases.find((c) => c.id === id)!;
    const result = run.results.find((r) => r.case_id === id)!;
    const detail = page.getByRole("region", { name: "Detalle del caso" });
    await expect(
      detail.getByRole("heading", { name: item.name, exact: true }),
    ).toBeVisible();
    await expect(detail.locator(".input-box")).toContainText(item.input);
    await expect(detail.locator(".section-heading")).toContainText(
      result.status,
    );
    await expect(detail.locator(".raw-output")).toHaveText(
      result.raw_output ?? "Sin respuesta del proveedor",
    );
    await expect(
      page.getByRole("button", {
        name: `${id}: ${result.status}`,
        exact: true,
      }),
    ).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator('.case-list [aria-pressed="true"]')).toHaveCount(
      1,
    );
  };
  await page.goto(`/#/explorer?run=${run.id}&case=secret-leak`);
  await assertCase("secret-leak");
  await page.evaluate(() => {
    document.documentElement.dataset.navigationMarker = "same-document";
  });
  await page.evaluate((id) => {
    window.location.hash = `/explorer?run=${id}&case=vpn`;
  }, run.id);
  await assertCase("vpn");
  expect(
    await page.locator("html").getAttribute("data-navigation-marker"),
  ).toBe("same-document");
  await page
    .getByRole("button", { name: "secret-leak: failed", exact: true })
    .click();
  await expect(page).toHaveURL(new RegExp("case=secret-leak$"));
  await assertCase("secret-leak");
  await page.goBack();
  await assertCase("vpn");
  await page
    .getByRole("combobox", { name: "Estado", exact: true })
    .selectOption("passed");
  await page.getByLabel("Buscar por ID o categoría").fill("network");
  await page.evaluate((id) => {
    window.location.hash = `/explorer?run=${id}&case=secret-leak`;
  }, run.id);
  const detail = page.getByRole("region", { name: "Detalle del caso" });
  await expect(detail.locator(".eyebrow")).toHaveText("secret-leak");
  await expect(
    page.getByText(/El caso seleccionado queda fuera/),
  ).toBeVisible();
  await expect(
    page.getByRole("combobox", { name: "Estado", exact: true }),
  ).toHaveValue("passed");
  await expect(page.getByLabel("Buscar por ID o categoría")).toHaveValue(
    "network",
  );
  await page.getByRole("button", { name: "vpn: passed", exact: true }).click();
  await assertCase("vpn");
  await page
    .getByRole("combobox", { name: "Estado", exact: true })
    .selectOption("all");
  await page.getByLabel("Buscar por ID o categoría").fill("");
  const secondResponse = await request.post("/api/runs", {
    headers: { "X-CSRF-Token": token },
  });
  expect(secondResponse.status()).toBe(201);
  const second = runSchema.parse(await secondResponse.json());
  await page.evaluate((id) => {
    window.location.hash = `/explorer?run=${id}&case=secret-leak`;
  }, second.id);
  await expect(page.getByText(second.id, { exact: true })).toBeVisible();
  await assertCase("secret-leak");
  await page.goBack();
  await expect(page.getByText(run.id, { exact: true })).toBeVisible();
  await assertCase("vpn");
  await page.reload();
  await assertCase("vpn");
});
