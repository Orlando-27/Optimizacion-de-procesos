@echo off
REM ===================================================================
REM  run_robot_precia.bat - entrypoint para el Programador de Tareas
REM  Proceso 002: robot_precia  (descarga diaria de insumos, 04:00)
REM ===================================================================
REM  El Programador de Tareas arranca en C:\Windows\System32; fijamos
REM  el directorio de trabajo a la carpeta del .bat.
cd /d "%~dp0"

REM --- Activar el entorno virtual/conda (ajustar segun instalacion) ---
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else (
    echo [ADVERTENCIA] No se encontro .venv. Usando Python del PATH.
)

REM --- Carpeta de logs y timestamp ---
if not exist "logs" mkdir "logs"
for /f "tokens=1-3 delims=/-. " %%a in ("%date%") do set HOY=%%c%%b%%a

REM --- Ejecutar el robot (entorno se toma de config.yaml) ---
python -m procesos.robot_precia.process >> "logs\robot_precia_%HOY%.log" 2>&1
set EXITCODE=%ERRORLEVEL%

echo Robot Precia finalizado con codigo %EXITCODE% >> "logs\robot_precia_%HOY%.log"
exit /b %EXITCODE%
