@echo off
REM ===================================================================
REM  run_robot_precia_respaldo.bat  -  MAQUINA DE RESPALDO (corre 05:00)
REM  Igual que la primaria pero en MODO RESPALDO (--respaldo): si la
REM  primaria ya bajo todo, se salta; si falta algo, baja solo lo que falta.
REM  La ruta de destino DEBE ser la MISMA en las dos maquinas.
REM ===================================================================
cd /d "%~dp0"

REM Entornos con python propio (lo mas comun):
set "PYEXE=%USERPROFILE%\.conda\envs\motor2\python.exe"
if not exist "%PYEXE%" set "PYEXE=%USERPROFILE%\anaconda3\envs\motor2\python.exe"
if not exist "%PYEXE%" set "PYEXE=%USERPROFILE%\AppData\Local\anaconda3\envs\motor2\python.exe"
if not exist "%PYEXE%" set "PYEXE=C:\ProgramData\anaconda3\envs\motor2\python.exe"
REM Anaconda base (caso de la 2a maquina: el robot quedo instalado en base):
if not exist "%PYEXE%" set "PYEXE=C:\ProgramData\anaconda3\python.exe"
if not exist "%PYEXE%" set "PYEXE=%USERPROFILE%\anaconda3\python.exe"
if not exist "%PYEXE%" set "PYEXE=%USERPROFILE%\AppData\Local\anaconda3\python.exe"

if not exist "logs" mkdir "logs"
set "LOG=logs\robot_precia_respaldo.log"

echo. >> "%LOG%"
echo ===== %date% %time% (respaldo) ===== >> "%LOG%"
if not exist "%PYEXE%" (
    echo [ERROR] No se encontro python.exe del entorno motor2. Edita PYEXE en este .bat. >> "%LOG%"
    exit /b 9
)

"%PYEXE%" -m procesos.robot_precia.process --respaldo >> "%LOG%" 2>&1
set EXITCODE=%ERRORLEVEL%
echo Robot Precia (respaldo) finalizado con codigo %EXITCODE% >> "%LOG%"
exit /b %EXITCODE%
