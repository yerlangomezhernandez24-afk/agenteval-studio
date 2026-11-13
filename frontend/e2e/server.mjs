import { spawn } from "node:child_process";
import path from "node:path";
import process from "node:process";

const child = spawn(
  process.env.AGENTEVAL_PYTHON,
  process.env.AGENTEVAL_E2E_LOCAL_MOCK === "1"
    ? [
        path.resolve("../tests/serve_phase4_e2e.py"),
        process.env.AGENTEVAL_E2E_DB,
        path.resolve("dist"),
      ]
    : [
        "-m",
        "agenteval.cli",
        "serve",
        "--db",
        process.env.AGENTEVAL_E2E_DB,
        "--ui-dir",
        path.resolve("dist"),
        "--dev-ui",
      ],
  {
    windowsHide: true,
    stdio: "inherit",
    env: { ...process.env, PYTHONIOENCODING: "utf-8" },
  },
);
for (const signal of ["SIGTERM", "SIGINT"])
  process.on(signal, () => child.kill());
child.on("exit", (code) => process.exit(code ?? 1));
