@echo off
REM ===================================================================
REM  run_robot_precia.bat  -  MAQUINA PRIMARIA (corre 04:00)
REM  Proceso 002: robot_precia (descarga diaria de insumos de Precia)
REM ===================================================================
REM  El Programador de Tareas arranca en C:\Windows\System32; fijamos
REM  el directorio de trabajo a la carpeta del .bat.
cd /d "%~dp0"

REM --- Interprete de Python (entorno "motor2") -----------------------
REM  Se prueban las rutas mas comunes de Anaconda/Miniconda. La tarea NO
REM  activa conda, por eso hay que apuntar al python.exe del entorno por
REM  ruta directa (no vale "python" a secas).
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
set "LOG=logs\robot_precia_primaria.log"

echo. >> "%LOG%"
echo ===== %date% %time% (primaria) ===== >> "%LOG%"
if not exist "%PYEXE%" (
    echo [ERROR] No se encontro python.exe del entorno motor2. Edita PYEXE en este .bat. >> "%LOG%"
    exit /b 9
)

"%PYEXE%" -m procesos.robot_precia.process >> "%LOG%" 2>&1
set EXITCODE=%ERRORLEVEL%
echo Robot Precia (primaria) finalizado con codigo %EXITCODE% >> "%LOG%"
exit /b %EXITCODE%
