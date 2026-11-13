import { afterEach, expect, it, vi } from "vitest";
import { z } from "zod";
import { api, request } from "../src/api";
import historic from "../../docs/evidence/replay-a.json";

afterEach(() => vi.unstubAllGlobals());
it("rejects malformed successful responses instead of rendering partial data", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(JSON.stringify({ bad: true }))),
  );
  await expect(
    request("/health", z.object({ status: z.literal("ok") })),
  ).rejects.toMatchObject({ code: "invalid_response" });
});
it("fetches a CSRF token and sends it only as a header with credentials omitted", async () => {
  const mock = vi
    .fn()
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ csrf_token: "x".repeat(43) })),
    )
    .mockResolvedValueOnce(
      new Response(JSON.stringify(historic), { status: 201 }),
    );
  vi.stubGlobal("fetch", mock);
  await api.execute();
  expect(mock.mock.calls[1][0]).toBe("/api/runs");
  expect(mock.mock.calls[1][1]).toMatchObject({
    credentials: "omit",
    method: "POST",
    headers: { "X-CSRF-Token": "x".repeat(43) },
  });
  expect(localStorage.length).toBe(0);
});
it("encodes run IDs in URLs", async () => {
  const mock = vi
    .fn()
    .mockResolvedValue(new Response(JSON.stringify(historic)));
  vi.stubGlobal("fetch", mock);
  await api.run("a/b?c");
  expect(mock.mock.calls[0][0]).toBe("/api/runs/a%2Fb%3Fc");
});
it("does not retry a rejected write", async () => {
  const mock = vi
    .fn()
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ csrf_token: "x".repeat(43) })),
    )
    .mockResolvedValueOnce(
      new Response(JSON.stringify({ code: "run_busy" }), { status: 409 }),
    );
  vi.stubGlobal("fetch", mock);
  await expect(api.execute()).rejects.toMatchObject({
    status: 409,
    code: "run_busy",
  });
  expect(mock).toHaveBeenCalledTimes(2);
});
