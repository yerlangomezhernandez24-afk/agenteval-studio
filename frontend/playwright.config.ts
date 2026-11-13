import { defineConfig } from "@playwright/test";
import { randomUUID } from "node:crypto";
import path from "node:path";

const root = path.resolve("..");
process.env.AGENTEVAL_E2E_DB ??= path.join(
  root,
  "data",
  `e2e-${randomUUID()}.sqlite3`,
);
process.env.AGENTEVAL_PYTHON ??= path.join(
  root,
  ".venv",
  "Scripts",
  "python.exe",
);

export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 30_000,
  expect: { timeout: 10_000 },
  reporter: [
    ["list"],
    [
      "json",
      {
        outputFile:
          process.env.AGENTEVAL_E2E_REPORT ??
          "../docs/evidence-phase2/playwright.json",
      },
    ],
  ],
  use: {
    baseURL: "http://127.0.0.1:8765",
    channel: "chrome",
    headless: true,
    viewport: { width: 1366, height: 950 },
    screenshot: "only-on-failure",
    trace: "off",
  },
  webServer: [
    {
      command: "node e2e/server.mjs",
      url: "http://127.0.0.1:8765/health",
      reuseExistingServer: false,
      timeout: 30_000,
    },
    {
      command: "npm run dev",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
});
