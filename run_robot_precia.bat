@echo off
REM ===================================================================
REM  run_robot_precia.bat  -  MAQUINA PRIMARIA (corre 04:00)
REM  Elige automaticamente el Python que TENGA el robot instalado
REM  (sirve tanto si quedo en un entorno "motor2" como en Anaconda base).
REM ===================================================================
cd /d "%~dp0"

if not exist "logs" mkdir "logs"
set "LOG=logs\robot_precia_primaria.log"
echo. >> "%LOG%"
echo ===== %date% %time% (primaria) ===== >> "%LOG%"

REM Probar candidatos y quedarnos con el primero que pueda importar el robot.
set "PYEXE="
for %%P in (
  "%USERPROFILE%\.conda\envs\motor2\python.exe"
  "%USERPROFILE%\anaconda3\envs\motor2\python.exe"
  "%USERPROFILE%\AppData\Local\anaconda3\envs\motor2\python.exe"
  "C:\ProgramData\anaconda3\envs\motor2\python.exe"
  "C:\ProgramData\anaconda3\python.exe"
  "%USERPROFILE%\anaconda3\python.exe"
  "%USERPROFILE%\AppData\Local\anaconda3\python.exe"
) do (
  if not defined PYEXE (
    if exist "%%~P" (
      "%%~P" -c "import procesos.robot_precia.process" 1>nul 2>nul && set "PYEXE=%%~P"
    )
  )
)

if not defined PYEXE (
  echo [ERROR] No se encontro un Python con el robot instalado. >> "%LOG%"
  echo         Revisa que hiciste 'pip install -e .' en la carpeta del proyecto. >> "%LOG%"
  exit /b 9
)

echo Usando Python: %PYEXE% >> "%LOG%"
"%PYEXE%" -m procesos.robot_precia.process >> "%LOG%" 2>&1
set EXITCODE=%ERRORLEVEL%
echo Robot Precia (primaria) finalizado con codigo %EXITCODE% >> "%LOG%"
exit /b %EXITCODE%
