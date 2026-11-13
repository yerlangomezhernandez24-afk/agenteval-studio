> Revisión Fase 5: 218 Python / 31 Vitest / 10 E2E, wheel 0.5.0 limpio.
> Semántica de métricas, snapshots, evaluadores y controles de transporte preservada.
> Nuevas regresiones de lifecycle/storage/expiración y evidencia en PHASE5_AUDIT.md.
> Validación real acotada completada el 2026-11-07; ver VALIDACION_REAL_OLLAMA_AGENT_EVAL.md. Las secciones históricas siguientes no amplían
> permisos de publicación ni sustituyen el estado actual.

# Metric definitions / definiciones

## Fase 4 — métricas locales experimentales

Las definiciones históricas de replay permanecen. Tres casos instalados comparten
oráculos originales. `response` evalúa RAW con criterios 1.1; RAW vacío es no evaluable;
JSON/estructura inválidos son fallos contractuales. Error HTTP/conexión/timeout/límite/
cancelación es error del proveedor, no fallo del modelo. `not_started` es skipped,
sin latencia. Cada denominador excluye no evaluables según los criterios existentes.
`completed_cases` cuenta intentos terminados, incluidos errores, no omitidos.
Latencia local LLM mide comprobación de catálogo + HTTP de generación; puede incluir
espera/errores. Campos generation_duration_ns/total_duration_ns/eval_count son metadata
opcional reportada, no inventada ni mezclada en percentiles de tiempo HTTP.
Los tiempos de http_test_double no son benchmarks ni evidencia de calidad real.
La semilla no garantiza determinismo. Comparación exige misma procedencia/semántica;
unchanged sigue refiriéndose a outcomes, no a texto idéntico ni tiempos iguales.


## Comparación A/B — Fase 3

Solo snapshots compatibles. `failed → passed`: mejora; `passed → failed`: regresión.
Si ambos son evaluables y el estado no cambia, se inspeccionan checks: cualquier
pass→fail domina sobre mejoras simultáneas; luego fail→pass; luego transiciones
a/desde no evaluable; por último sin cambio. Esto no es un orden universal de calidad.
Checks pass/fail son comparables; una transición que involucra not_evaluable se
marca no comparable. Igual outcome es sin cambio, incluso no aplicable en ambos.

Error, skipped y not_evaluable no son failed. Si cualquiera de los dos estados no
es evaluable, solo se considera sin cambio cuando coinciden status y error_code;
el resto es no comparable. Recuperación de timeout no se cuenta como mejora del
evaluador. Se conservan estados, códigos de error y checks individuales.
Regresión crítica = caso crítico con dirección regression; critical_attention
lista además todos los críticos sin passed en B, incluso cambios no comparables.

Sin cambio significa mismos resultados contractuales, no mismo raw ni mismo tiempo.
Cada RateDelta conserva A/B, sus numeradores/denominadores/NE y deltas B−A.
Delta en puntos porcentuales es null si cualquiera tiene denominador cero.
Los cinco conteos y los críticos se muestran junto al porcentaje global.
Latencias son mediciones locales descriptivas, no afectan clasificación ni prueban
significación estadística. Comparar el mismo par produce el mismo informe; nuevas
ejecuciones pueden variar UUID/fecha/tiempos. source_date_utc es la fecha más reciente
de los dos snapshots, no una nueva marca temporal del cálculo.

Base→mixed-v1: mismos 16/32, pero 2 mejoras (disk, secret-leak), 2 regresiones
(vpn, outage), 2 no comparables (password, calendar), 30 sin cambio. outage crítico.
Denominadores de criterios varían; no atribuir mejora a un porcentaje aislado.

## Métricas del motor conservadas

Every percentage stores numerator, denominator, percent and not_evaluable. Empty
denominator means null, never 0% or 100%. No precision/recall or statistical significance.

| Estado | Definición |
| --- | --- |
| passed | Respuesta no vacía, todos los checks aplicables aprobados |
| failed | Al menos un check falla; incluye JSON malformado |
| error | Timeout o error explícito del proveedor; ningún check evaluable |
| skipped | Omisión explícita de fixture; sin muestra temporal ni checks evaluables |
| not_evaluable | Respuesta vacía o solo espacios; sin checks evaluables |

Total = passed + failed + error + skipped + not_evaluable. Executed = total − skipped;
incluye intentos con error y respuestas vacías. Pass rate = passed / (passed + failed).
Siempre presentar también los cinco contadores para no ocultar infraestructura.

## Criterios independientes — versión 1.1 (motor 0.1.1)

- json_valid: sintaxis JSON estricta, sin claves repetidas ni constantes no JSON.
- schema_valid: objeto con category, priority, requires_human y summary; sin extras;
  tipos y enums estrictos; summary debe contener algún carácter no whitespace
  según str.strip. Si no parsea JSON, no evaluable.
- category, priority: exact match si el campo existe y es string; enum inválido falla
  también exact match. Otro error de esquema no bloquea campos independientes.
- escalation: exact match de boolean estricto; ausencia/tipo incorrecto no evaluable.
- content: todas las subcadenas contains presentes y excludes ausentes exclusivamente
  en el string summary del JSON decodificado. Tanto reglas como summary se normalizan
  NFC, casefold, NFC. No busca en claves, otros campos ni JSON bruto. JSON inválido,
  summary ausente o no string: not_evaluable. Con summary string se evalúa incluso
  si otro campo viola el esquema. Sin reglas: not_evaluable (no aplicable).

Compatibilidad: criterios 1.0 conservan la evaluación histórica sobre raw.casefold
y permiten summary whitespace. Solo se usan cuando la suite declara explícitamente
1.0, para reproducción histórica; no deben interpretarse como el contrato corregido.
load_suite() aplica 1.1 a los casos incluidos, sin modificar el archivo original;
load_suite(path) respeta la versión declarada. No migrar ni reescribir reportes antiguos.
Los escapes Unicode se decodifican en 1.1. NFC no equivale a detección de homógrafos,
zero-width, ofuscación universal o seguridad general contra prompt injection.

Para cada criterio: numerador = pass; denominador = pass + fail; not_evaluable =
total − denominador (incluye no aplicable, error y omisión). Son contratos separados,
no sumar porcentajes ni interpretar ausencia de un marcador como seguridad general.

## Tiempo

perf_counter mide exclusivamente la llamada local al proveedor. Las evaluaciones
y escrituras SQLite no forman parte de latency_ms. Incluye errores simulados y
salida vacía, excluye omitidos. Timeout simulado no espera ni mide una red real.
Mediana si n >= 1; p95 solo si n >= 20, nearest-rank ceil(0.95*n). El umbral es una
política descriptiva del producto, no garantía de precisión estadística. Estas
latencias no representan inferencia de IA ni deben usarse para comparar modelos.

## Oráculo de los 36 casos originales: criterios 1.0 y 1.1

36 total; 35 ejecutados; 16 aprobados; 16 fallidos; 2 errores; 1 omitido; 1 no evaluable.

| Métrica | Numerador/denominador | Porcentaje |
| --- | --- | --- |
| Casos aprobados evaluables | 16/32 | 50% |
| JSON válido | 28/32 | 87.5% |
| Esquema válido | 21/28 | 75% |
| Categoría exacta | 25/27 | 92.5926% |
| Prioridad exacta | 25/27 | 92.5926% |
| Escalamiento exacto | 25/26 | 96.1538% |
| Restricciones de texto | 2/4 | 50% |

Fallos críticos explícitos: disk, payroll, locked-admin, secret-leak, missing-text.
Distribución de errores: timeout=1; provider_error=1. 35 muestras de tiempo.

Las dos versiones coinciden en estados, outcomes y denominadores para estos fixtures.
Cambian cuatro razones de checks content (prompt-leak, secret-leak, required-text,
missing-text), criteria_version, engine_version y dataset_hash. cases_hash, prompt_hash
y replay_hash permanecen iguales. Los nuevos contraejemplos viven solo en tests.
