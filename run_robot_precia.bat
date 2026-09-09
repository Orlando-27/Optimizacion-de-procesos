@echo off
REM ===================================================================
REM  run_robot_precia.bat  -  MAQUINA PRIMARIA (corre 04:00)
REM  Proceso 002: robot_precia (descarga diaria de insumos de Precia)
REM ===================================================================
REM  El Programador de Tareas arranca en C:\Windows\System32; fijamos
REM  el directorio de trabajo a la carpeta del .bat.
cd /d "%~dp0"

REM --- Interprete de Python -------------------------------------------
REM  Ajusta PYEXE a tu instalacion de Anaconda/entorno "motor2".
REM  (Ruta directa al python.exe del entorno; es lo mas robusto para el
REM   Programador de Tareas, no depende de "activar" el entorno.)
set "PYEXE=%USERPROFILE%\anaconda3\envs\motor2\python.exe"
if not exist "%PYEXE%" set "PYEXE=python"

REM --- Carpeta de logs y timestamp (YYYYMMDD) ------------------------
if not exist "logs" mkdir "logs"
for /f "tokens=1-3 delims=/-. " %%a in ("%date%") do set HOY=%%c%%b%%a

REM --- Ejecutar el robot (el entorno se toma de config.yaml) ----------
"%PYEXE%" -m procesos.robot_precia.process >> "logs\robot_precia_%HOY%.log" 2>&1
set EXITCODE=%ERRORLEVEL%

echo Robot Precia (primaria) finalizado con codigo %EXITCODE% >> "logs\robot_precia_%HOY%.log"
exit /b %EXITCODE%
