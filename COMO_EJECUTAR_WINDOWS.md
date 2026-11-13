# Ejecutar AgentEval Studio 0.5.0 en Windows

1. Descomprime el ZIP en una carpeta local nueva y abre PowerShell en ella.
2. Instala Python 3.12 y, para compilar o desarrollar, Node.js 24 (>=24.15,<25).
3. Crea el entorno e instala dependencias verificadas:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps dist/agenteval_studio-0.5.0-py3-none-any.whl
```

4. El ZIP incluye frontend compilado. Para reconstruirlo desde el código:

```powershell
cd frontend
npm ci
npm run build
cd ..
```

Para reconstruir también el wheel, instala requirements-dev.lock con --require-hashes y ejecuta `python -m build --wheel --no-isolation` con el Python del entorno.

5. Inicia la aplicación:

```powershell
.\.venv\Scripts\python.exe -m agenteval.cli serve --db data/demo.sqlite3 --ui-dir frontend/dist
```

6. Abre http://127.0.0.1:8765. Mantén la terminal abierta. Ctrl+C detiene el servidor.
7. En Evaluation Runs ejecuta Base histórica y Variante mixta. En Regression Lab compara A/B: 2 mejoras, 2 regresiones, 2 no comparables, 30 sin cambio. Overview, Test Suites y Case Explorer permiten inspeccionar los 36 casos y sus checks. Descarga JSON/CSV desde los controles de exportación. El historial persiste al reiniciar con la misma base.
8. Replay no requiere Ollama, modelos ni APIs pagadas. No ejecutar nuevas inferencias para reproducir el experimento histórico; usa docs/evidence-ollama-real/audit_offline.py.

Si 8765 está ocupado, elige un puerto libre mediante --port y abre esa dirección. Para E2E original se requieren 8765 y 5173 libres; no cierres aplicaciones ajenas. Prototipo local de un usuario de confianza; no introducir datos personales ni secretos. No producción.
