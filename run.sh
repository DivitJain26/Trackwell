#!/usr/bin/env bash
# TrackWell - local start script (macOS / Linux)
set -e
cd "$(dirname "$0")"
echo "=============================================="
echo " TrackWell - local start script"
echo "=============================================="

if ! command -v python3 >/dev/null 2>&1; then
  echo "[ERROR] python3 was not found. Install Python 3.10+ and try again."; exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "[1/4] Creating virtual environment..."; python3 -m venv .venv
else
  echo "[1/4] Virtual environment found."
fi
PY=.venv/bin/python

if ! $PY -c "import flask, sklearn, pandas, flask_wtf" >/dev/null 2>&1; then
  echo "[2/4] Installing dependencies (first run only, needs internet)..."
  $PY -m pip install --upgrade pip >/dev/null
  $PY -m pip install -r requirements.txt
else
  echo "[2/4] Dependencies already installed."
fi

echo "[3/4] Initialising database..."
$PY scripts/init_db.py

echo "[4/4] Starting TrackWell at http://127.0.0.1:5000  (Ctrl+C to stop)"
echo "      First time? Open the page and use 'Create the first administrator account'."
echo "      Train the model from the Model page or run: $PY scripts/train_model.py"
exec $PY app.py
