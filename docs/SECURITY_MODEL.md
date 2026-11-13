# Seguridad y privacidad — estado Fase 5

Prototipo local de una persona de confianza. Sin autenticación multiusuario,
cifrado SQLite, cuotas de disco ni certificación. No introducir PII/tickets reales.
Las decisiones y evidencias históricas permanecen en los informes y ZIP anteriores.

| Amenaza | Control comprobado | Límite residual |
| --- | --- | --- |
| Sitio externo/rebinding/CSRF | Loopback, Host con puerto exacto, Origin permitido, Fetch Metadata, token por proceso | Otros procesos locales de confianza pueden acceder; no autenticación |
| Salida que intenta ejecutar acciones | RAW como texto, sin eval/herramientas/plugins/shell del modelo | Checks literales no certifican seguridad universal de LLM |
| Destino de red arbitrario | Cliente fijo 127.0.0.1:11434; solo tags/version/generate; sin proxy/redirect/pull | Un servidor local malicioso puede mentir o hacer acciones fuera del control del cliente |
| Respuesta HTTP maliciosa | JSON estricto, Unicode válido, catálogo/digest, cabeceras/bytes/tiempo/tokens acotados | No auditoría formal de penetración ni interoperabilidad universal |
| Concurrencia y cierre | Gate compartido replay/LLM, start/close serializados, cierre definitivo, cleanup de worker fallido | Límite por proceso; no ejecutar múltiples workers |
| Persistencia alterada | SQL parametrizado; append-only desde app; hashes/RAW/checks/métricas verificados; 409 | Hash no firma autenticidad ante reescritura coherente por dueño de BD |
| Exportación activa | CSV literaliza todo texto; JSON datos, no código; descargas sin rutas de usuario | JSON de run contiene RAW y entradas sintéticas; proteger archivos locales |
| Consumo de recursos | Tres casos locales, 128 tokens, 16 KB RAW, 64 KB envelope, 30 s por generación | No control total de CPU/RAM del servidor ni cuota histórica de disco |
| Browser storage denegado/reinicio | UUID recordado opcionalmente, token nunca persistido; 404 detiene polling | Sin storage, salir de la vista pierde seguimiento en memoria; consultar historial |
| Paths CLI | Rechazo de traversal, UNC, ADS, enlaces/junctions y nombres reservados | CLI/filesystem local de confianza; no aislamiento frente a procesos privilegiados |

CSP self, no-store, nosniff y frame-ancestors none; sin CORS global. Vite 5173 solo
con --dev-ui y Origin preservado. API sin cuerpos arbitrarios, prompts/casos/modelos
por allowlist y selección explícita. Puerto de test solo por inyección interna con
procedencia http_test_double; no opción pública de URL. No cloud/telemetría configurada.

Cancelación interrumpe lectura y guarda parcial al cierre normal. No garantiza fin
instantáneo del cálculo del proveedor. kill/TerminateProcess puede perder el job
no confirmado; un snapshot ya guardado se verifica tras reinicio. F5 no cambia
contratos ni seguridad de paths para ocultar warnings de Python 3.13 (no soportado).

No registrar tokens, RAW en logs de diagnóstico ni excepciones internas con rutas.
Los informes/SQLite sí contienen salidas sintéticas. Paquete excluye BD, entornos,
modelos y configuración local. Redacción y escaneo de patrones no garantizan ausencia
universal de secretos. Dependencias congeladas/pip check/npm ci son comprobaciones
limitadas, no una auditoría exhaustiva de CVE o de supply chain.

Validación real acotada completada el 2026-11-07; ver VALIDACION_REAL_OLLAMA_AGENT_EVAL.md. Ver PHASE5_AUDIT.md para pruebas reales ejecutadas,
doble HTTP, límites de accesibilidad y condiciones previas a publicación.
