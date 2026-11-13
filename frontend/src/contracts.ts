// Explicit mirror of Pydantic HTTP fields used by UI, validated before rendering.
import { z } from "zod";

export const statuses = [
  "passed",
  "failed",
  "error",
  "skipped",
  "not_evaluable",
] as const;
export const statusSchema = z.enum(statuses);
export type Status = z.infer<typeof statusSchema>;
export const criteria = [
  "json_valid",
  "schema_valid",
  "category",
  "priority",
  "escalation",
  "content",
] as const;
const category = z.enum([
  "network",
  "account",
  "hardware",
  "software",
  "other",
]);
const expected = z.object({
  category,
  priority: z.enum(["low", "medium", "high"]),
  requires_human: z.boolean(),
});
export const caseSchema = z.object({
  id: z.string(),
  name: z.string(),
  input: z.string(),
  expected,
  rationale: z.string(),
  category,
  tags: z.array(z.string()),
  criticality: z.enum(["normal", "critical"]),
  contains: z.array(z.string()),
  excludes: z.array(z.string()),
});
export const suiteSchema = z.object({
  id: z.string(),
  version: z.string(),
  synthetic: z.literal(true),
  description: z.string(),
  criteria_version: z.enum(["1.0", "1.1"]),
  criteria: z.array(z.enum(criteria)),
  prompt_version: z.string(),
  prompt: z.string(),
  replay_version: z.string(),
  cases: z.array(caseSchema),
});
export const rateSchema = z
  .object({
    numerator: z.number().int().nonnegative(),
    denominator: z.number().int().nonnegative(),
    percent: z.number().min(0).max(100).nullable(),
    not_evaluable: z.number().int().nonnegative(),
  })
  .refine(
    (r) =>
      r.numerator <= r.denominator &&
      (r.denominator === 0 ? r.percent === null : r.percent !== null),
    "Inconsistent rate",
  );
const count = z.number().int().nonnegative();
export const metricsSchema = z.object({
  total: count,
  executed: count,
  passed: count,
  failed: count,
  errors: count,
  skipped: count,
  not_evaluable: count,
  pass_rate: rateSchema,
  criteria: z.record(z.enum(criteria), rateSchema),
  error_distribution: z.record(z.string(), count),
  critical_failures: z.array(z.string()),
  latency_samples: count,
  latency_median_ms: z.number().nonnegative().nullable(),
  latency_p95_ms: z.number().nonnegative().nullable(),
});
export const resultSchema = z.object({
  case_id: z.string(),
  status: statusSchema,
  checks: z.array(
    z.object({
      criterion: z.enum(criteria),
      outcome: z.enum(["pass", "fail", "not_evaluable"]),
      reason: z.string(),
    }),
  ),
  raw_output: z.string().nullable(),
  latency_ms: z.number().nonnegative().nullable(),
  error_code: z.string().nullable(),
  reason: z.string(),
});
const runBase = z.object({
  id: z.uuid(),
  created_utc: z.iso.datetime({ offset: true }),
  engine_version: z.string(),
  provider: z.literal("ReplayProvider"),
  label: z.literal("REPLAY / SIMULATED OUTPUT"),
  dataset_hash: z.string(),
  cases_hash: z.string(),
  prompt_hash: z.string(),
  replay_hash: z.string(),
  suite: suiteSchema,
  results: z.array(resultSchema),
  metrics: metricsSchema,
});
export const modelSchema = z.object({
  name: z.string().min(1).max(128),
  digest: z.string().regex(/^[a-f0-9]{64}$/),
  size: z.number().int().positive(),
  modified_at: z.string(),
  family: z.string(),
  parameter_size: z.string(),
  quantization_level: z.string(),
});
export const optionsSchema = z.object({
  temperature: z.number().min(0).max(1),
  seed: z.number().int().nonnegative(),
  num_predict: z.number().int().min(16).max(128),
  num_ctx: z.literal(2048),
});
export const provenanceSchema = z.enum(["local_ollama", "http_test_double"]);
export const promptSchema = z.enum(["support-json-v1", "support-concise-v1"]);
const localRunSchema = runBase.extend({
  snapshot_version: z.literal(2),
  provider: z.literal("OllamaLocal"),
  label: z.literal("LOCAL LLM / EXPERIMENTAL"),
  engine_version: z.literal("0.2.0-local"),
  evaluator_version: z.literal("1.1"),
  provenance: provenanceSchema,
  model: z.string(),
  model_info: modelSchema,
  ollama_version: z.string().nullable(),
  options: optionsSchema,
  parameters: z.record(z.string(), z.string()),
  completion: z.enum(["completed", "cancelled"]),
  snapshot_hash: z.string(),
  attempts: z
    .array(
      z.object({
        case_id: z.string(),
        code: z.enum([
          "response",
          "timeout",
          "connection_error",
          "http_error",
          "invalid_response",
          "limit_exceeded",
          "cancelled",
          "not_started",
        ]),
        elapsed_ms: z.number().nonnegative().nullable(),
        generation_duration_ns: z.number().nonnegative().nullable(),
        total_duration_ns: z.number().nonnegative().nullable(),
        eval_count: z.number().int().nonnegative().nullable(),
      }),
    )
    .length(3),
});
export const runSchema = z
  .discriminatedUnion("provider", [runBase, localRunSchema])
  .refine(
    (r) =>
      r.results.length === r.suite.cases.length &&
      r.metrics.total === r.results.length &&
      r.results.every(
        (result, index) => result.case_id === r.suite.cases[index].id,
      ),
    "Inconsistent run",
  );
export type Suite = z.infer<typeof suiteSchema>;
export type TestCase = z.infer<typeof caseSchema>;
export type Run = z.infer<typeof runSchema>;
export type Metrics = z.infer<typeof metricsSchema>;
export type Rate = z.infer<typeof rateSchema>;
export type CaseResult = z.infer<typeof resultSchema>;
