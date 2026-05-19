#!/usr/bin/env bash
# Env Extractor launcher (macOS).
# Double-click this file. It will:
#   1. Check for Python 3.10+
#   2. Create a local .venv if missing
#   3. Install requirements (first run only)
#   4. Launch Streamlit and open your browser

set -e

# cd to the streamlit-app directory regardless of where this was invoked from.
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
APP_DIR="$( dirname "$SCRIPT_DIR" )"
cd "$APP_DIR"

echo "------------------------------------------------------------"
echo " Env Extractor"
echo " app dir: $APP_DIR"
echo "------------------------------------------------------------"

# --- 1. Find Python ---------------------------------------------------------
PYTHON_BIN=""
for candidate in python3.12 python3.11 python3.10 python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    version=$("$candidate" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || true)
    major=$(echo "$version" | cut -d. -f1)
    minor=$(echo "$version" | cut -d. -f2)
    if [ "$major" = "3" ] && [ "$minor" -ge 10 ] 2>/dev/null; then
      PYTHON_BIN="$candidate"
      break
    fi
  fi
done

if [ -z "$PYTHON_BIN" ]; then
  echo ""
  echo "ERROR: Python 3.10 or newer is required and we couldn't find it."
  echo ""
  echo "Install Python from https://www.python.org/downloads/ (grab the latest 3.x),"
  echo "then double-click this file again."
  echo ""
  read -n 1 -s -r -p "Press any key to close this window..."
  exit 1
fi

echo "Using $PYTHON_BIN ($("$PYTHON_BIN" --version))"

# --- 2. Create venv if missing ---------------------------------------------
if [ ! -d ".venv" ]; then
  echo "First run: creating local virtual environment in .venv ..."
  "$PYTHON_BIN" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

# --- 3. Install requirements ------------------------------------------------
NEEDS_INSTALL=0
if [ ! -f ".venv/.installed" ]; then
  NEEDS_INSTALL=1
elif [ requirements.txt -nt .venv/.installed ]; then
  NEEDS_INSTALL=1
fi

if [ "$NEEDS_INSTALL" = "1" ]; then
  echo "Installing dependencies (one-time, ~30 seconds)..."
  pip install --upgrade pip >/dev/null
  pip install -r requirements.txt
  touch .venv/.installed
fi

# --- 4. Launch --------------------------------------------------------------
echo ""
echo "Starting Env Extractor at http://localhost:8501"
echo "(Close this window to stop the app.)"
echo ""

# Give Streamlit a moment, then open the browser.
( sleep 2 && open "http://localhost:8501" ) &

streamlit run app.py --server.headless true --browser.gatherUsageStats false
