@echo off
REM Detiene el backend matando el proceso que escucha en 127.0.0.1:8000.
REM No ejecutar directamente; se invoca desde detener.vbs.
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "127.0.0.1:8000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
