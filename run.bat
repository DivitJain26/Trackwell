@echo off
setlocal
cd /d "%~dp0"
echo ==============================================
echo  TrackWell - local start script (Windows)
echo ==============================================

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python was not found on PATH.
  echo         Install Python 3.10+ from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/4] Creating virtual environment...
  python -m venv .venv
  if errorlevel 1 ( echo [ERROR] Could not create the virtual environment. & pause & exit /b 1 )
) else (
  echo [1/4] Virtual environment found.
)

set PY=.venv\Scripts\python.exe

%PY% -c "import flask, sklearn, pandas, flask_wtf" >nul 2>nul
if errorlevel 1 (
  echo [2/4] Installing dependencies ^(first run only, needs internet^)...
  %PY% -m pip install --upgrade pip >nul
  %PY% -m pip install -r requirements.txt
  if errorlevel 1 ( echo [ERROR] Dependency installation failed. Check your internet connection. & pause & exit /b 1 )
) else (
  echo [2/4] Dependencies already installed.
)

echo [3/4] Initialising database...
%PY% scripts\init_db.py
if errorlevel 1 ( echo [ERROR] Database initialisation failed. & pause & exit /b 1 )

echo [4/4] Starting TrackWell at http://127.0.0.1:5000  (Ctrl+C to stop)
echo       First time? Open the page and use "Create the first administrator account".
echo       Train the model from the Model page or run: %PY% scripts\train_model.py
start "" http://127.0.0.1:5000
%PY% app.py
pause
