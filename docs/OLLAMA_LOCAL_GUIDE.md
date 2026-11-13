# Ollama local experimental — Fase 5

Estado al 2026-11-07: **INTEGRACIÓN REAL VALIDADA EN UN EXPERIMENTO ACOTADO**.
Ollama 0.40.15 + qwen2.5:1.5b produjo tres respuestas reales: 0/3 casos aprobados,
sin errores de transporte. Ver [informe](VALIDACION_REAL_OLLAMA_AGENT_EVAL.md).
Su dictamen independiente está pendiente. `http_test_double` sigue identificando
exclusivamente evidencia sintética; no mezclarla con `local_ollama`.

## Uso opcional

1. Iniciar AgentEval con el wheel 0.5.0 siguiendo WINDOWS_QUICKSTART.md.
2. Abrir Evaluation Runs y seleccionar «Ollama local (experimental)».
3. Pulsar «Comprobar disponibilidad». Solo se consulta 127.0.0.1:11434.
4. Si no responde o no hay modelos, continuar con ReplayProvider. No es necesario
   instalar nada para usar o verificar la aplicación.
5. Si ya existe Ollama local con un modelo autorizado, seleccionarlo explícitamente,
   revisar metadatos y elegir uno de los dos prompts versionados. No hay entrada libre.
6. Elegir temperatura 0..1, semilla 0..2147483647 y máximo 16..128 tokens.
   Contexto fijado en 2048; stream=false, format=json, keep_alive=0.
7. «Ejecutar 3 casos con Ollama» autoriza esa ejecución sintética. Revisar progreso,
   cancelar si procede y abrir el snapshot. Nunca se inicia por seleccionar el proveedor.

Ollama y qwen2.5:1.5b ya se instalaron en el equipo del propietario con autorización.
En otro equipo, instalar modelos requiere su propia decisión informada. Consultar la documentación oficial del proveedor,
comprobar licencia/tamaño del modelo y mantener el servidor ligado a loopback.
No configurar host público ni Ollama Cloud. Este proyecto no incorpora instaladores,
comandos pull, credenciales de terceros ni selección automática de modelos.

Se aceptan nombres locales de hasta 128 caracteres alfanuméricos y `_.:-`;
nombres con `/` y entradas marcadas remotas/cloud se rechazan conservadoramente.
Un digest del catálogo distinto antes de cada caso impide generar con ese modelo.
La versión de Ollama y sus tiempos se registran solo cuando el proveedor los entrega.
No son medidas verificadas de rendimiento ni firmas de identidad.

## Recursos, cancelación y datos

Solo tres casos incorporados: vpn, secret-leak, required-text, con sus oráculos
originales. El doble HTTP no conoce ni utiliza esos oráculos para responder.
No PII ni archivos libres. RAW se almacena en SQLite sin cifrado, como texto no
confiable. JSON exporta el snapshot completo, incluidas entradas y RAW; CSV exporta
checks, errores, tiempos y procedencia sin RAW. Texto CSV lleva apóstrofo protector.

Un job a la vez, compartiendo bloqueo con replay. Catálogo/versiones: hasta 3 s
por petición; conexión hasta 2 s; generación hasta 30 s por caso. Tres casos acotan
el trabajo a aproximadamente 100 s, más preparación y persistencia local. Salida
16 KB y envelope HTTP 64 KB. No se garantiza uso máximo de RAM/CPU del proceso
Ollama: depende del modelo ya instalado. Semilla y temperatura no garantizan determinismo.

Cancelar interrumpe la lectura y cierra la conexión. No garantiza que un servidor
externo mal comportado detenga inmediatamente su cálculo. Se guarda un snapshot
parcial: error cancelled para la petición interrumpida y skipped para casos no
iniciados. No se inventan respuestas. Los intentos terminados no incluyen omitidos.
Un corte abrupto puede perder el job en curso; snapshots guardados permanecen.
Fase 5 serializa start/close y rechaza trabajo después del cierre. Un error al
crear el worker devuelve 503 sin dejar un job fantasma. Un 404 de job expirado
detiene polling y permite consultar el historial antes de una nueva ejecución.

El navegador intenta conservar únicamente el UUID del último job en sessionStorage para
recuperar su estado al volver (si storage está bloqueado, el job activo sigue
visible en memoria hasta salir de la vista); el token CSRF no se persiste. El servidor conserva
como máximo 20 jobs en memoria. Tras reiniciar, abrir los snapshots del historial.

Errores de transporte no son fallos de clasificación del modelo. Tiempo HTTP
incluye comprobación del catálogo y petición; generación en ns es metadata opcional
del proveedor, mostrada por separado. El suplemento real registra 4.314 GiB
libres antes de inferir y un mínimo muestreado de 3.203 GiB durante la prueba;
son observaciones de ese equipo, no requisitos universales ni un benchmark.

## Comparación y revisión

Replay y LLM quedan incompatibles. Un LLM solo se compara con otro completo de la
misma procedencia, suite/casos, criterios y motor compatible. Prompts/modelos pueden
variar y quedan trazados; no se afirma causalidad ni significación estadística.
`unchanged` describe outcomes contractuales, no igualdad de respuestas o tiempos.
Al leer históricos LLM se recalculan checks desde RAW; jamás se repite inferencia.

Fuentes oficiales consultadas para el protocolo:
[List local models](https://docs.ollama.com/api/tags),
[Generate a response](https://docs.ollama.com/api/generate).
La autorización para el experimento original ya se consumó. Consultar el snapshot
guardado no requiere inferir. Nuevos experimentos deben tener alcance explícito;
no repetir el job original ni descargar otros modelos para buscar aprobaciones.
