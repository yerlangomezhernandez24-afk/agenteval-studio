# Demo privada de tres minutos

Objetivo: mostrar ingeniería de evaluación, trazabilidad y detección de regresiones.
No presentar precisión de IA real, certificación de seguridad o preparación empresarial.

Preparar el wheel 0.5.0 y abrir una base separada de la del usuario:

```powershell
& .\.venv-phase5\Scripts\python.exe -m agenteval.cli serve --db data/recruiter-demo.sqlite3 --ui-dir frontend/dist
```

Abrir http://127.0.0.1:8765. No borrar una base existente para repetir la demo;
elegir otro nombre de archivo si se necesita un historial vacío. Ctrl+C termina el
servidor. No hacen falta Node, Ollama ni conexión externa para el replay compilado.

| Tiempo | Acción | Qué explicar |
| --- | --- | --- |
| 0:00–0:30 | Test Suites: inspeccionar vpn y secret-leak | 36 casos ficticios, seis criterios y oráculos versionados. No son tickets reales. |
| 0:30–1:10 | Evaluation Runs: Base histórica, ejecutar; abrir secret-leak | El motor comprueba RAW real del fixture. 16/32 evaluables; errores y omisiones están separados. Los fallos deliberados prueban el evaluador, no degradación de un modelo. |
| 1:10–2:00 | Ejecutar Variante mixta y comparar A→B en Regression Lab | Mismo 50 % global, pero dos regresiones, incluida outage crítica; dos mejoras y dos no comparables. unchanged no significa texto o tiempo idéntico. |
| 2:00–2:30 | Abrir caso, volver y descargar comparación CSV/JSON | URL reproducible, snapshot inmutable desde la app, checks/hashes verificados. CSV literaliza texto; JSON de run contiene RAW sintético. |
| 2:30–3:00 | Seleccionar Ollama en Runs y comprobar disponibilidad, sin generar | Adaptador local experimental, selección explícita y límites. Integración real documentada con qwen2.5:1.5b: 0/3 aprobados. Mostrar el informe o una captura real guardada, sin nueva inferencia; distinguirla del doble HTTP. |

Cerrar mostrando PHASE5_AUDIT.md, logs y SHA-256 del paquete. Un hash detecta
inconsistencias, no autentica una base frente a reescritura coherente. La demo es
local para una persona de confianza; no hay cifrado SQLite ni usuarios aislados.

No ejecutar un modelo durante una entrevista sin autorización explícita. Si un
modelo responde, eso por sí solo tampoco establece calidad general o seguridad.
Las capturas entregadas que muestran HTTP TEST DOUBLE están identificadas como
integración sintética; no presentarlas como una ejecución de Ollama real.

## Revisar el experimento real ya guardado (equipo del propietario)

Cerrar primero el servidor de demo anterior con Ctrl+C. Desde la raíz:

```powershell
& .\.venv-phase5\Scripts\python.exe -m agenteval.cli serve --db data/ollama-real-validation-20261106.sqlite3 --ui-dir frontend/dist
```

Abrir http://127.0.0.1:8765/#/explorer?run=b03267de-2aee-481f-9cd7-6744869701fd.
La lectura usa RAW persistido: no necesita cargar el modelo ni volver a generar.
Esta base privada existe en el equipo del propietario y no está en el ZIP.
En otro equipo, consultar el informe/capturas o ejecutar audit_offline.py del
suplemento con el wheel 0.5.0 instalado. No prometer una base prellenada en el paquete.

Mensaje de presentación: «Construí un laboratorio que detecta incumplimientos de
contratos y regresiones por caso. Separé replay, doble HTTP e inferencia real.
El modelo real falló los tres casos; la plataforma permitió explicar cada fallo,
conservar la evidencia y comprobarla después sin volver a llamar al modelo».
