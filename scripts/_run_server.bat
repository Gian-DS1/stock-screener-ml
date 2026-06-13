@echo off
REM Motor del lanzador: arranca el backend que sirve API + dashboard.
REM Escucha SOLO en 127.0.0.1 (loopback) -> ningun puerto expuesto a la red.
REM No ejecutar directamente; se invoca desde iniciar.vbs.
cd /d "%~dp0..\backend"
uv run uvicorn screener.api.main:app --host 127.0.0.1 --port 8000
