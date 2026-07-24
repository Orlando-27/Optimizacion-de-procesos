@echo off
REM ===================================================================
REM  run_impugnacion.bat - entrypoint para el Programador de Tareas
REM  Proceso 001: impugnacion_rfl
REM ===================================================================
REM  El Programador de Tareas arranca en C:\Windows\System32; por eso
REM  fijamos el directorio de trabajo a la carpeta del .bat.
cd /d "%~dp0"

REM --- Activar el entorno virtual (ajustar la ruta si difiere) ---
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else (
    echo [ADVERTENCIA] No se encontro .venv. Usando Python del PATH.
)

REM --- Carpeta de logs y timestamp para el nombre del log ---
if not exist "logs" mkdir "logs"
for /f "tokens=1-3 delims=/-. " %%a in ("%date%") do set HOY=%%c%%b%%a

REM --- Ejecutar el proceso (entorno se toma de config.yaml) ---
REM  Redirige stdout y stderr al log diario.
python -m procesos.impugnacion_rfl.process >> "logs\impugnacion_%HOY%.log" 2>&1
set EXITCODE=%ERRORLEVEL%

echo Proceso finalizado con codigo %EXITCODE% >> "logs\impugnacion_%HOY%.log"

REM --- Devolver el exit code al Programador de Tareas ---
exit /b %EXITCODE%
