@echo off
REM ===================================================================
REM  run_robot_precia_respaldo.bat  -  MAQUINA DE RESPALDO (corre 05:00)
REM  Igual que la primaria pero en MODO RESPALDO (--respaldo):
REM   - Revisa la ruta de destino.
REM   - Si la maquina primaria (04:00) ya bajo TODO -> se salta (SKIPPED),
REM     sin abrir el navegador, y avisa por correo "[RESPALDO] nada que hacer".
REM   - Si falta algo (la primaria se apago/reinicio/fallo) -> descarga
REM     SOLO lo que falta.
REM  La ruta de destino DEBE ser la MISMA en las dos maquinas (carpeta de
REM  red compartida), para que el respaldo "vea" lo que bajo la primaria.
REM ===================================================================
cd /d "%~dp0"

set "PYEXE=%USERPROFILE%\anaconda3\envs\motor2\python.exe"
if not exist "%PYEXE%" set "PYEXE=python"

if not exist "logs" mkdir "logs"
for /f "tokens=1-3 delims=/-. " %%a in ("%date%") do set HOY=%%c%%b%%a

"%PYEXE%" -m procesos.robot_precia.process --respaldo >> "logs\robot_precia_respaldo_%HOY%.log" 2>&1
set EXITCODE=%ERRORLEVEL%

echo Robot Precia (respaldo) finalizado con codigo %EXITCODE% >> "logs\robot_precia_respaldo_%HOY%.log"
exit /b %EXITCODE%
