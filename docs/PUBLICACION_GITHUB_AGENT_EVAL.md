# Publicación GitHub — AgentEval Studio 0.5.0

**PUBLICADO Y VERIFICADO.** Prototipo local de portafolio, NO PRODUCCIÓN.

- Repositorio público: https://github.com/yerlangomezhernandez24-afk/agenteval-studio
- Rama principal: main.
- Commit de la aplicación y etiqueta v0.5.0: e0d9aebc3f56393c9c1560bc70d0642314a58ff9.
- Release: https://github.com/yerlangomezhernandez24-afk/agenteval-studio/releases/tag/v0.5.0
- ZIP: https://github.com/yerlangomezhernandez24-afk/agenteval-studio/releases/download/v0.5.0/AgentEval-Studio-v0.5.0-Windows.zip
- SHA-256: `901077f778140075aaaf938a94e0fbedff8b43acf7ad8fe0247ffe1b56484cac`.
- CI aprobada en el mismo commit, intento 2: https://github.com/yerlangomezhernandez24-afk/agenteval-studio/actions/runs/43357057935

## Contenido y licencia

156 archivos originales preparados en Git: backend/frontend, pruebas, configuraciones y locks, README ES/EN, arquitectura, guía COMO_EJECUTAR_WINDOWS.md, fixtures sintéticos y tres capturas auténticas. Se publica este informe como actualización documental posterior a la etiqueta.
LICENSE contiene MIT completo para código original, copyright 2026 Yerlan Daniel Gómez Hernández. Metadatos Python/frontend reflejan MIT. THIRD_PARTY_NOTICES.md y third_party/ conservan avisos de dependencias. No se distribuyen Ollama ni sus modelos.

La copia pública se preparó en reports/publication/source, con Git separado para preservar originales y evidencia privada del proyecto. No se publicó el árbol local sin filtrar. No se alteró trabajo remoto previo: el repositorio no existía según la consulta autenticada; se creó público, se publicó main sin force push y la Release adjunta ZIP y SHA-256. Topics y descripción configurados.

## Distribución y ejecución limpia

ZIP público: 161 entradas, 837315 bytes. Incluye fuentes, wheel recompilado con MIT, UI compilada, guía Windows y manifiesto por archivo. CRC, SHA-256, rutas y contenido comprobados. Se descargó sin autenticación desde la URL pública y su hash coincidió. Repositorio confirmado público, rama main y licencia MIT reconocida por GitHub.

Instalación en entorno Python 3.12 nuevo: requirements.lock con --require-hashes, wheel sin reinstalar dependencias, pip check aprobado. Frontend: npm ci instaló 228 paquetes y reportó cero vulnerabilidades; build aprobado. No equivale a auditoría universal de dependencias.

Copia pública limpia: 37/37 Vitest, 10/10 Playwright con Chrome y doble HTTP explícito, más smoke HTTP con replay de 36 casos, A/B, exportaciones JSON/CSV y recuperación exacta tras reinicio. Se extrajo el ZIP en carpeta nueva, se instaló su wheel y se repitió el smoke con exit 0. Las cinco vistas y sus flujos se comprobaron en los E2E de la copia publicable; los archivos extraídos coinciden por manifiesto.

Incidente del harness extraído: primer smoke falló por crear data/ con una ruta relativa equivocada del harness; se corrigió la ubicación, conservó el log y el segundo intento pasó. No fue un defecto del producto ni requirió alterar criterios.

## Resultado real de GitHub Actions

Workflow Windows, Python 3.12 y Node 24. Instalación hash-locked, build/instalación del wheel, pip check, Ruff, mypy, pytest, npm ci, npm ls, Vitest, ESLint, Prettier, build y Playwright con Chrome. Sin modelo real.

Primer intento de main: 9 E2E aprobadas y fallo de Chrome al capturar la primera pantalla (`Unable to capture screenshot`). Ejecución de la etiqueta: 9 E2E aprobadas y fallo al observar el estado vacío inicial. Logs conservados; no se borran esos resultados.

Se reintentó el job fallido de main para comprobar la variabilidad del runner, sin modificar código, timeouts, aserciones ni activar retries en Playwright. Intento 2 completado en success: **218 Python (42.77 s), 37 Vitest, 10 E2E (31.7 s)**; cero pruebas omitidas en estas suites. Las etapas de calidad también pasaron. Los primeros fallos indican variabilidad observada de CI; no se afirma estabilidad universal a partir de un reintento. La ejecución histórica de etiqueta conserva su fallo; el mismo SHA de aplicación está verificado por la ejecución aprobada de main.

## Privacidad, conservación y limitaciones

Revisión del índice Git antes de publicar: sin bases SQLite, entornos, cachés, modelos, instaladores, ZIP históricos privados, tokens de sesión ni rutas personales. Los fixtures y RAW son sintéticos y se conservaron íntegros. Escaneo de patrones acotado, no garantía universal. Los avisos de licencia de terceros se incluyen sin relicenciar sus bibliotecas.

Históricos locales y otros proyectos permanecen intactos. No se cerraron procesos ajenos. No se ejecutaron nuevas inferencias ni descargas de modelos. Experimento qwen2.5:1.5b preservado: tres HTTP 200 y 0/3 aprobados, sin fallos de transporte; no mide precisión o seguridad universales. No se ejecutaron acciones ni se preparó material nuevo de LinkedIn.

Prototipo local de un usuario de confianza; sin autenticación multiusuario ni cifrado SQLite. No certificado para producción. Publicación y MIT autorizadas por el propietario. La auditoría independiente sigue siendo una revisión distinta de esta implementación/autoverificación.

## Continuidad local

ZIP y sidecar también disponibles bajo reports/AgentEval-Studio-v0.5.0-Windows.zip. Evidencia privada de esta publicación: reports/publication/evidence/. El checkout público para próximos cambios está en reports/publication/source; no subir automáticamente el árbol original, que conserva evidencia privada.

Este informe se publica después de v0.5.0 como documentación; la etiqueta y ZIP verificables conservan su commit y hash. No se reescribe la etiqueta ni se sustituye el activo publicado.
