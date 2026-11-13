import config from "./playwright.config";
import { defineConfig } from "@playwright/test";

// Existing unrelated app owns 5173. Exercise compiled UI without disturbing it.
export default defineConfig({
  ...config,
  webServer: Array.isArray(config.webServer)
    ? [config.webServer[0]]
    : config.webServer,
  grepInvert: /legitimate Vite proxy preserves browser Origin and executes/,
});
