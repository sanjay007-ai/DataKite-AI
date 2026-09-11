@echo off
title DataKite AI - Final
color 0B
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "backend\app.py" (
  echo ERROR: backend\app.py not found.
  pause
  exit /b 1
)

set "PYTHON=python"
if exist ".venv\Scripts\python.exe" set "PYTHON=%~dp0.venv\Scripts\python.exe"
if exist "backend\.venv\Scripts\python.exe" set "PYTHON=%~dp0backend\.venv\Scripts\python.exe"

cd /d "%~dp0backend"

echo ============================================
echo   DataKite AI - FINAL
 echo ============================================
echo.
"%PYTHON%" --version
if errorlevel 1 (
  echo ERROR: Python unavailable.
  pause
  exit /b 1
)

if not exist "%~dp0.venv\deps.ok" if not exist "%~dp0backend\.venv\deps.ok" (
  echo Installing required packages...
  "%PYTHON%" -m pip install -r requirements.txt > install_log.txt 2>&1
  if errorlevel 1 (
    echo ERROR: Package installation failed. See backend\install_log.txt
    pause
    exit /b 1
  )
  if exist "%~dp0.venv" (echo ok>"%~dp0.venv\deps.ok") else (echo ok>"%~dp0backend\.venv\deps.ok")
)

echo.
echo Starting DataKite AI...
echo Open http://127.0.0.1:5000
echo.
start "" "http://127.0.0.1:5000"
"%PYTHON%" app.py
pause
