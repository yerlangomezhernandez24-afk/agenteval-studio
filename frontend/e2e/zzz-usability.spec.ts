import { test, expect } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import path from "node:path";

test("keyboard focus and sampled contrast at three widths", async ({
  page,
}) => {
  const evidence = path.resolve(
    process.env.AGENTEVAL_PHASE_EVIDENCE ?? "../docs/evidence-phase5",
  );
  mkdirSync(evidence, { recursive: true });
  await page.goto("/#/overview");
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("link", { name: "Saltar al contenido" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
  await page.getByRole("link", { name: "03 Evaluation Runs" }).focus();
  await page.keyboard.press("Enter");
  await expect(
    page.getByRole("heading", { name: "Evaluation Runs", exact: true }),
  ).toBeVisible();
  const selector = page.getByRole("combobox", {
    name: "Proveedor",
    exact: true,
  });
  await selector.focus();
  await page.keyboard.press("ArrowDown");
  await expect(
    page.getByRole("button", { name: "Comprobar disponibilidad" }),
  ).toBeEnabled();
  await selector.focus();
  await page.keyboard.press("Tab");
  await expect(
    page.getByRole("button", { name: "Comprobar disponibilidad" }),
  ).toBeFocused();
  const samples = await page.evaluate(() => {
    const luminance = (color: string) => {
      const c = color
        .match(/[\d.]+/g)!
        .slice(0, 3)
        .map(Number)
        .map((v) => v / 255)
        .map((v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
      return c[0] * 0.2126 + c[1] * 0.7152 + c[2] * 0.0722;
    };
    return [
      ".ollama-panel h2",
      ".ollama-panel button",
      ".sidebar nav a[aria-current]",
    ].map((selector) => {
      const el = document.querySelector(selector)!;
      const style = getComputedStyle(el);
      let bg = style.backgroundColor,
        parent = el.parentElement;
      while (bg === "rgba(0, 0, 0, 0)" && parent) {
        bg = getComputedStyle(parent).backgroundColor;
        parent = parent.parentElement;
      }
      const a = luminance(style.color),
        b = luminance(bg);
      return {
        selector,
        foreground: style.color,
        background: bg,
        ratio: (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05),
      };
    });
  });
  samples.forEach((sample) => expect(sample.ratio).toBeGreaterThanOrEqual(4.5));
  writeFileSync(
    path.join(evidence, "contrast-samples.json"),
    JSON.stringify(
      {
        scope: "Three sampled text pairs, not a full accessibility audit",
        samples,
      },
      null,
      2,
    ),
  );
  for (const width of [1366, 768, 390]) {
    await page.setViewportSize({ width, height: 950 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({
      path: path.join(evidence, `keyboard-${width}.png`),
      fullPage: true,
    });
  }
});
