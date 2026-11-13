# Arquitectura vigente — Fase 5

Monolito modular local: React/TypeScript → FastAPI loopback → motor/proveedor →
evaluadores → snapshot SQLite. Aplicación 0.5.0; sin reescritura ni migración de datos.
El historial de decisiones se conserva en PHASE1..5_AUDIT y paquetes inmutables.

| Capa | Responsabilidad |
| --- | --- |
| models, engine, providers | Run histórico y ReplayProvider determinista 0.1.1 |
| evaluators, metrics | Seis criterios y denominadores explícitos, semánticas 1.0/1.1 |
| local_models, local_snapshot | LocalRun v2 y verificación pura desde RAW, sin red |
| ollama | HTTP directo fijo 127.0.0.1:11434, tags/version/generate y límites |
| local_jobs | Un worker comparte gate con replay; lifecycle serializa start/close |
| storage, integrity, io | Append-only desde la app, JSON canónico, verificación al leer |
| comparison, reports | Compatibilidad semántica y exportaciones JSON/CSV |
| api, security | UUID/query permitidos, Host/Origin/CSRF/Fetch Metadata; no cuerpos |
| React | Cinco pantallas, Zod, hash URLs, polling real, RAW como texto |

## Dos contratos conservados

Run replay conserva su formato original; integrity.verify reproduce solo los fixtures.
LocalRun v2 usa motor 0.2.0-local/evaluadores 1.1, modelo/digest/opciones/procedencia,
intentos y hash integral. Verificar un LLM recalcula checks desde RAW almacenado.
La tabla runs mantiene id, created_utc y snapshot; no hay migración ni update/delete
públicos. Dataset hash incluye la suite completa; cases_hash identifica los casos.
SHA-256 detecta inconsistencias, no firma autenticidad frente al propietario de la BD.

## Ciclo de vida y recursos

start/close serializados; close es definitivo. Preparación del catálogo y publicación
del worker terminan antes de que close cancele y espere. Worker nunca toma el lock
lifecycle, evitando join circular. Fallo de Thread.start elimina estado parcial y
libera gate, devuelve 503. Un segundo job o replay simultáneo se rechaza con 409.
Cancelación guarda parcial con error cancelled y skipped no iniciados. Job máximo
20 estados en memoria; snapshots guardados sobreviven reinicios. Un kill puede perder
el job sin snapshot. Límites de conexión, tiempo, salida y tokens en OLLAMA_LOCAL_GUIDE.

Handlers síncronos y worker propio no ejecutan inferencia en el event loop. Al
cerrar normalmente se espera al worker antes de disponer Store. SQLite error: 503;
snapshot inconsistente: 409 sin contenido privado. CLI conserva validate/run/export/serve.

## API e interfaz

/api/runs crea replay con variante permitida; /runs/{uuid} verifica el snapshot.
/variants, /comparisons y /comparisons/export conservan el contrato A/B.
/ollama/status consulta disponibilidad; POST /ollama/jobs inicia; GET por UUID
consulta; POST /cancel solicita parada. /runs/{uuid}/export sirve JSON/CSV verificados.
Alias sin /api preservados. JSON de run contiene RAW; CSV exporta checks sin RAW.

UI compilada same-origin; Vite 5173 solo con --dev-ui. History/Case Explorer/A-B
usan UUID/selección en hash de URL. La sesión intenta recordar únicamente UUID de
job: storage bloqueado no rompe ejecución; 404 detiene polling de job expirado.
El token CSRF vive solo en cada llamada, nunca en storage. No reintentos de POST.
Replay/LLM y doble/real se bloquean por incompatibilidad; no reetiquetar históricos.
