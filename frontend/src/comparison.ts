import { z } from "zod";
import { metricsSchema, rateSchema, statusSchema, criteria } from "./contracts";

export const changes = [
  "improvement",
  "regression",
  "unchanged",
  "not_comparable",
] as const;
export const changeNames = {
  improvement: "Mejora",
  regression: "Regresión",
  unchanged: "Sin cambio",
  not_comparable: "No comparable",
};
const changeSchema = z.enum(changes);
export const comparisonSchema = z
  .object({
    report_version: z.literal("1.0"),
    source_date_utc: z.iso.datetime({ offset: true }),
    label: z.enum([
      "REPLAY / SIMULATED OUTPUT",
      "LOCAL LLM / EXPERIMENTAL",
      "MIXED / INCOMPATIBLE",
    ]),
    warning: z.string(),
    a_id: z.uuid(),
    b_id: z.uuid(),
    compatible: z.boolean(),
    reasons: z.array(z.string()),
    fingerprints: z.record(z.string(), z.record(z.string(), z.string())),
    metrics_a: metricsSchema,
    metrics_b: metricsSchema,
    rates: z.record(
      z.string(),
      z.object({
        a: rateSchema,
        b: rateSchema,
        numerator_delta: z.number().int(),
        denominator_delta: z.number().int(),
        percentage_points: z.number().nullable(),
      }),
    ),
    counts: z.record(changeSchema, z.number().int().nonnegative()),
    critical_regressions: z.array(z.string()),
    critical_attention: z.array(z.string()),
    cases: z.array(
      z.object({
        case_id: z.string(),
        name: z.string(),
        critical: z.boolean(),
        a_status: statusSchema,
        b_status: statusSchema,
        a_error: z.string().nullable(),
        b_error: z.string().nullable(),
        change: changeSchema,
        latency_a_ms: z.number().nonnegative().nullable(),
        latency_b_ms: z.number().nonnegative().nullable(),
        checks: z.array(
          z.object({
            criterion: z.enum(criteria),
            a: z.enum(["pass", "fail", "not_evaluable"]),
            b: z.enum(["pass", "fail", "not_evaluable"]),
            change: changeSchema,
          }),
        ),
      }),
    ),
  })
  .refine(
    (r) =>
      r.compatible
        ? r.reasons.length === 0 &&
          Object.values(r.counts).reduce((a, b) => a + b, 0) === r.cases.length
        : r.reasons.length > 0 && r.cases.length === 0,
    "Invalid comparison",
  );
export type Comparison = z.infer<typeof comparisonSchema>;
export const variantsSchema = z.array(
  z.object({
    id: z.enum(["baseline-v1", "mixed-v1"]),
    name: z.string(),
    replay_version: z.string(),
    cases_hash: z.string(),
    replay_hash: z.string(),
  }),
);
