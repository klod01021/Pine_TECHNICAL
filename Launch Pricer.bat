@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo   Option Pricer
echo   Installing anything missing, then opening your browser ...
echo.

if exist "%~dp0.venv\Scripts\python.exe" (
  set "PY=%~dp0.venv\Scripts\python.exe"
  goto :run
)

where py >nul 2>nul
if %ERRORLEVEL%==0 (
  set "PY=py -3"
  goto :run
)

where python >nul 2>nul
if %ERRORLEVEL%==0 (
  set "PY=python"
  goto :run
)

where python3 >nul 2>nul
if %ERRORLEVEL%==0 (
  set "PY=python3"
  goto :run
)

echo Python 3 was not found.
echo Install it from https://www.python.org/downloads/ then double-click this file again.
start "" "https://www.python.org/downloads/"
echo.
pause
exit /b 1

:run
%PY% "%~dp0launch.py"
if errorlevel 1 (
  echo.
  echo The pricer exited with an error.
  pause
  exit /b 1
)
endlocal
