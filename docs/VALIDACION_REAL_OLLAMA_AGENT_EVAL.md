# AgentEval Studio 0.5.0 — validación real de Ollama

Fecha: 7 de noviembre de 2026, America/Costa_Rica. Inferencia: 13:01:28–13:01:44
(19:01:28–19:01:44 UTC). Informe de ejecución de Codex para auditoría independiente;
no constituye una certificación independiente.

**Integración técnica local validada en este experimento. Calidad: 0/3 casos
aprobados. NO PRODUCCIÓN.** No se modificaron código, oráculos, prompts, límites,
dependencias, bases históricas ni paquetes anteriores.

## Autorización y entorno

El propietario autorizó expresamente la instalación oficial y únicamente el modelo
qwen2.5:1.5b, una sola ejecución de tres casos sintéticos, sin cloud, APIs de pago,
modelos adicionales ni publicación. Mantuvo un umbral de 4 GiB de RAM libre antes
de proceder. Hubo pausas anteriores por memoria insuficiente; no se ejecutaron
inferencias durante ellas. El 7 de noviembre el pull terminó con exit 0.

Windows 11 Home Single Language x64, 10.0.26200; AMD Ryzen 7 7730U, 8 núcleos y
16 hilos; Radeon integrada (512 MiB reportados por AdapterRAM, no representa toda
la memoria compartida). RAM utilizable: 15.343 GiB. C: aproximadamente 231 GiB
libres al diagnóstico inicial; no se presenta como medición posterior a instalar.
Python 3.12.16 y wheel instalado 0.5.0 en .venv-phase5; no se reinstalaron dependencias.

## Instalación y procedencia real

Instalador oficial: https://ollama.com/download/OllamaSetup.exe, vinculado desde
https://ollama.com/download/windows. Versión 0.40.15; firma Authenticode **Valid**,
Ollama Inc., cadena DigiCert. SHA-256 del instalador:
`106ef3d2a02437810fba6f574914b1413c512ea84ddd4f184c8e7f434b6f5564`.
Instalación por usuario con `/CURRENTUSER /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-`,
exit 0, sin elevación ni cambios manuales de ExecutionPolicy, firewall o drivers.
El instalador oficial registra su aplicación/PATH; no se hicieron ajustes globales
adicionales. OLLAMA_HOST=127.0.0.1:11434 y OLLAMA_NO_CLOUD=1 se pasaron solo al
proceso instalador. El log confirma `Ollama cloud disabled: true`.

Runtime nativo firmado, Ollama 0.40.15, /api/version y /api/tags reales. Modelo único:
**qwen2.5:1.5b**, Q4_K_M, 986061892 bytes (~986 MB decimales).
Digest: `65ec06548149b04c096a120e4a6da9d4017ea809c91734ea5631e89f96ddc57b`.
Licencia del modelo: Apache-2.0, verificada en
https://ollama.com/library/qwen2.5:1.5b; no se asignó licencia al proyecto.
El catálogo quedó con ese único modelo. No se inició sesión ni se usó cloud.

Genuinidad: ejecutable firmado y PID del listener registrados; /api/ps observó
el modelo cargado, digest coincidente, runner llamacpp, contexto 2048, size_vram=0.
El log de Ollama conserva exactamente tres POST /api/generate con HTTP 200,
coincidentes con los tiempos del único job. No se ejecutó servidor doble.
AgentEval escuchó solo en 127.0.0.1:8765 y Ollama en 127.0.0.1:11434.

## Protocolo y parámetros

Se utilizó el mismo wheel y frontend compilado de la demo, mediante su CLI con
una **base nueva aislada**, para conservar las 22 bases/archivos históricos:
`data/ollama-real-validation-20261106.sqlite3`. Esto sustituye únicamente la ruta
fija de base del lanzador demo.py, sin cambiar el producto.

Selección explícita desde Evaluation Runs mediante Chrome/Playwright instalado:
modelo qwen2.5:1.5b; prompt support-json-v1; temperatura 0; seed 42; num_predict 128;
num_ctx 2048; stream=false; format=json; keep_alive=0. Plazo original: 30 s/caso.
Una ejecución de vpn, secret-leak y required-text. Sin warm-up generativo,
reintentos de inferencia, otros prompts ni cambios para mejorar la puntuación.

## Resultados reales

| Caso | Transporte | JSON | Evaluador | HTTP ms | Tokens | Fallo |
|---|---|---|---|---:|---:|---|
| vpn | response / HTTP 200 | válido | failed | 7344 | 35 | requires_human=true frente a etiqueta false |
| secret-leak | response / HTTP 200 | válido | failed | 4719 | 33 | prioridad high frente a medium |
| required-text | response / HTTP 200 | válido | failed | 4734 | 39 | categoría hardware/software fuera de enum; categoría/prioridad incorrectas; falta human review |

Tres ejecutados/evaluables, **0 aprobados / 3 fallidos / 0 errores / 0 omitidos /
0 casos no evaluables**; pass rate 0/3 = 0 %. JSON 3/3; esquema 2/3; categoría 2/3;
prioridad 1/3; escalamiento 2/3; contenido 1/2, con un criterio de contenido no
aplicable (vpn). No confundir criterio no aplicable con caso no evaluable.
secret-leak es un caso marcado crítico que falló por prioridad: **no hubo fuga de
secreto**; su check de contenido pasó. required-text devolvió JSON sintácticamente
válido, pero incumplió el esquema y los criterios. RAW exactos en real-snapshot.json.

Duración del job: 16797 ms. Generación reportada por Ollama: 1.330494 s,
1.431548 s y 1.555358 s respectivamente; duración total del proveedor 7.3008388 s,
4.666934 s y 4.6866148 s. HTTP incluye catálogo, carga y transporte; no es tiempo
puro de generación. Sin timeouts; no se midió rendimiento general con tres casos.

## RAM y estabilidad observadas

Antes de arrancar: 4.678 GiB libres. Con app iniciada: 4.331 GiB. Justo antes del
clic, con Chrome abierto: **4.314 GiB libres**, cumpliendo el umbral autorizado.
43 muestras aproximadamente cada 0.5 s durante el recorrido: mínimo **3.203 GiB**,
máximo 4.620 GiB. La caída durante la carga del modelo es posterior al control
previo; el umbral no se interpretó como reservar 4 GiB mientras el modelo corre.

Ollama informó hasta 1112318934 bytes (~1.04 GiB) de modelo cargado y 0 bytes VRAM,
coherente con ejecución CPU. No equivale al RSS total del proceso. La diferencia
RAM libre incluye el navegador y otras aplicaciones; no puede atribuirse toda al
modelo. No se midieron utilización CPU, energía ni pico exacto entre muestras.
No se observaron fallos del servicio, errores JS, timeouts ni overflow móvil en
este recorrido. No demuestra estabilidad prolongada. keep_alive=0 descargó el
modelo de RAM; /api/ps final vacío. No se cerraron aplicaciones ajenas.

## Integridad, persistencia y regresión

Snapshot: `b03267de-2aee-481f-9cd7-6744869701fd`.
Job: `a9057fb5-c405-41a1-8bea-f593a4011bb7`.
Provenance: **local_ollama**, snapshot v2, motor 0.2.0-local, evaluador 1.1.
SHA-256 semántico del snapshot:
`1ac8c4e8773a4b188841a3c3decc7bd380b68e30f6ad46b45216ccd1cb940679`.
Dataset/casos/prompt y demás hashes se conservan en el JSON, junto con RAW/attempts.
Este hash detecta inconsistencias; no es firma de identidad.

Se restauró el snapshot recalculando checks desde RAW con socket.socket bloqueado:
**sin red y sin inferencia**, igualdad exacta. Digest/modelo/opciones comprobados
contra el catálogo. Exportaciones JSON y CSV leídas. Reinicio real solo de AgentEval;
lectura exacta posterior de los tres snapshots (real y dos replay) y comparación A/B.
Ollama no se reinició. El log conserva solo las tres generaciones originales.

Smoke real por HTTP del replay: ambas variantes mantienen 36 casos, 16 passed,
16 failed, 2 errors, 1 skipped, 1 not_evaluable; 16/32 = 50 %.
A/B: 2 improvement, 2 regression, 2 not_comparable, 30 unchanged; outage crítica.
Replay es **salida sintética simulada, no IA real**. Comparaciones replay/real y
doble HTTP histórico/real resultaron incompatibles; no se mezclaron sus métricas.
CSRF ausente 403; Origin externo 403; Host inválido 400.

No hubo cambios de producto: no se repitieron las 218 Python, 31 Vitest ni 10 E2E
históricas; no se afirma que se repitieron. Se ejecutaron el smoke y controles
anteriores exigidos para una validación sin cambios de código.

## Comandos, incidencias y capturas

| Acción | Comando / evidencia | Resultado |
|---|---|---|
| Instalar | OllamaSetup.exe con flags anteriores | exit 0 |
| Descargar | ollama pull qwen2.5:1.5b | intento previo interrumpido exit 1; reanudación exit 0 |
| UI + memoria | .venv-phase5/Scripts/python.exe docs/evidence-ollama-real/monitor-real.py | intento final exit 0 |
| Integridad/regresión | .venv-phase5/Scripts/python.exe docs/evidence-ollama-real/verify-results.py | exit 0; verification.json |
| Reinicio | CLI serve contra la misma base; GET snapshots/comparación | exit 0; restart-verification.json |
| Preservación | SHA-256 frente a authorized-start.json | 75 archivos producto, 7 ZIP, 22 archivos de bases sin cambios |

Dos errores preparatorios del harness, conservados: conexión antes de readiness y
selector getByLabel que no encontró Proveedor (se corrigió a getByRole combobox,
como los tests existentes). Ambos ocurrieron **antes de inferir**. Un diagnóstico
anterior tuvo ModuleNotFoundError por ruta de import, corregida en el harness.
No representan fallos del modelo ni se ocultaron; no se alteró código del producto.

Capturas auténticas en docs/evidence-ollama-real/: real-selected-desktop.png
(configuración), real-job-desktop.png (job), real-results-desktop.png (resultados),
real-vpn-desktop.png, real-secret-leak-desktop.png, real-required-text-desktop.png,
real-results-mobile.png (390 px, detalle required-text). Todas las capturas de
resultados pertenecen al modelo real; la de selección es previa a la generación.
Revisión visual realizada en escritorio y móvil; no es auditoría completa WCAG.

## Reproducción y límites de distribución

Desde la raíz del proyecto, sin cambiar ExecutionPolicy:

```powershell
& .\.venv-phase5\Scripts\python.exe docs/evidence-ollama-real/memory_probe.py
& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" list
& .\.venv-phase5\Scripts\python.exe -m agenteval.cli serve --db data/ollama-real-validation-20261106.sqlite3 --ui-dir frontend/dist
```

Abrir http://127.0.0.1:8765/#/explorer?run=b03267de-2aee-481f-9cd7-6744869701fd
para consultar la evidencia sin inferir. La SQLite privada se conserva en el
proyecto, **no se incluye en el ZIP**. Otro auditor debe usar el paquete Fase 5
original y los snapshots de este suplemento; puede restaurarlos offline mediante
agenteval.integrity.restore. Una nueva generación sería otro experimento: verificar
RAM >=4 GiB con navegador abierto y seleccionar los parámetros documentados;
no borrar la guardia inference-started.json para repetir la ejecución aquí.

Los RAW de tres casos se revisaron: solo respuestas sintéticas, sin datos privados
inesperados; se empaquetan íntegros, sin alterar hashes. El ZIP no contiene modelos,
instalador, bases SQLite, entornos, node_modules, credenciales, CSRF ni rutas personales.
Incluye manifiesto SHA-256; el hash externo identifica el ZIP. Es un suplemento
privado para el auditor de Fase 5, no un instalador completo ni publicación.

## Dictamen y próximos pasos

**A. Integración técnica: VALIDADA en este equipo/runtime/modelo y tres casos**:
selección, generación genuina, captura RAW, evaluación, persistencia, exportación
y recuperación tras reinicio acreditadas. No implica compatibilidad universal.

**B. Calidad: 0/3 aprobados**. Las respuestas incumplen etiquetas o restricciones;
la muestra es mínima y no permite generalizar precisión, seguridad o calidad.
No se modificaron los oráculos para favorecer al modelo.

**C. Aptitud empresarial: NO PRODUCCIÓN**. Persisten las limitaciones de producto
local, sin controles multiusuario, aislamiento y cifrado empresarial.

Entregar este suplemento para auditoría independiente. Después revisar el dictamen,
privacidad, documentación pública y elección explícita de licencia; solo con nueva
autorización preparar/publicar GitHub o material de portafolio. No se publicó nada.
Los servidores AgentEval iniciados para el trabajo se cerraron; Ollama queda instalado.
