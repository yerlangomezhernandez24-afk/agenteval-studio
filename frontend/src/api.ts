import { z } from "zod";
import { runSchema, suiteSchema } from "./contracts";
import { comparisonSchema, variantsSchema } from "./comparison";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}
export function describeError(status: number, code = ""): string {
  if (status === 409 && code === "snapshot_corrupt")
    return "Snapshot corrupto. No se muestra su contenido. Revisa la integridad del archivo SQLite.";
  if (status === 409)
    return "Ya hay una evaluación en curso. Actualiza el historial antes de volver a ejecutar.";
  if (status === 403)
    return "Acceso rechazado por Origin o CSRF. Usa la URL local autorizada y vuelve a intentarlo.";
  if (status === 422)
    return "La API rechazó los parámetros. Comprueba el identificador y los límites de paginación.";
  if (status === 503)
    return "El servicio local o SQLite no está disponible temporalmente. Comprueba el proveedor y actualiza.";
  if (status === 404) return "La ejecución no existe en esta base local.";
  return "No se pudo completar la petición. Comprueba que el backend local está activo.";
}
export async function request<T>(
  path: string,
  schema: z.ZodType<T>,
  options: RequestInit = {},
): Promise<T> {
  const timeout = AbortSignal.timeout(15_000);
  const signal = options.signal
    ? AbortSignal.any([timeout, options.signal])
    : timeout;
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...options,
      signal,
      credentials: "omit",
      cache: "no-store",
    });
  } catch (error) {
    if (options.signal?.aborted) throw error;
    if (timeout.aborted)
      throw new ApiError(
        0,
        "timeout",
        "Tiempo de espera agotado. La ejecución podría haberse guardado; actualiza el historial. No se reintenta automáticamente.",
      );
    throw new ApiError(0, "network", describeError(0));
  }
  if (!response.ok) {
    const parsed = z
      .object({ code: z.string().optional() })
      .safeParse(await response.json().catch(() => null));
    const code = parsed.success ? (parsed.data.code ?? "") : "";
    throw new ApiError(
      response.status,
      code,
      describeError(response.status, code),
    );
  }
  const parsed = schema.safeParse(await response.json().catch(() => null));
  if (!parsed.success)
    throw new ApiError(
      response.status,
      "invalid_response",
      "La respuesta no cumple el contrato esperado. No se muestran datos parciales.",
    );
  return parsed.data;
}
export const api = {
  health: (signal?: AbortSignal) =>
    request(
      "/health",
      z.object({
        status: z.literal("ok"),
        provider: z.literal("REPLAY / SIMULATED OUTPUT"),
      }),
      { signal },
    ),
  suite: (signal?: AbortSignal) => request("/suite", suiteSchema, { signal }),
  runs: (offset: number, signal?: AbortSignal) =>
    request(
      `/runs?limit=10&offset=${offset}`,
      z.object({ run_ids: z.array(z.uuid()) }),
      { signal },
    ),
  run: (id: string, signal?: AbortSignal) =>
    request(`/runs/${encodeURIComponent(id)}`, runSchema, { signal }),
  variants: (signal?: AbortSignal) =>
    request("/variants", variantsSchema, { signal }),
  comparison: (a: string, b: string, signal?: AbortSignal) =>
    request(`/comparisons?${new URLSearchParams({ a, b })}`, comparisonSchema, {
      signal,
    }),
  download: async (a: string, b: string, format: "json" | "csv") => {
    let response: Response;
    try {
      response = await fetch(
        `/api/comparisons/export?${new URLSearchParams({ a, b, format })}`,
        {
          credentials: "omit",
          cache: "no-store",
          signal: AbortSignal.timeout(15_000),
        },
      );
    } catch {
      throw new ApiError(0, "network", describeError(0));
    }
    if (!response.ok) {
      const error = z
        .object({ code: z.string().optional() })
        .safeParse(await response.json().catch(() => null));
      const code = error.success ? (error.data.code ?? "") : "";
      throw new ApiError(
        response.status,
        code,
        describeError(response.status, code),
      );
    }
    const type = response.headers.get("content-type") ?? "";
    if (!type.startsWith(format === "json" ? "application/json" : "text/csv"))
      throw new ApiError(
        response.status,
        "invalid_response",
        "Formato de descarga inesperado.",
      );
    return response.blob();
  },
  execute: async (variant?: "baseline-v1" | "mixed-v1") => {
    const session = await request(
      "/session",
      z.object({ csrf_token: z.string().min(40) }),
    );
    // Token lives only in this call. No cookies, storage, URLs, logging or automatic POST retry.
    return request(
      variant ? `/runs?variant=${encodeURIComponent(variant)}` : "/runs",
      runSchema,
      {
        method: "POST",
        headers: { "X-CSRF-Token": session.csrf_token },
      },
    );
  },
};
