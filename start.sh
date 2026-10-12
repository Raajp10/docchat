#!/usr/bin/env bash
# Mac / Linux: first run installs everything, then opens the app in your browser.
cd "$(dirname "$0")"
if [ ! -x .venv/bin/streamlit ]; then
  # Python 3.14 is too new for the search model library, so prefer 3.13 -> 3.10.
  PY=""
  for v in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$v" >/dev/null 2>&1; then PY="$v"; break; fi
  done
  [ -z "$PY" ] && { echo "Please install Python 3.12 from https://www.python.org/downloads/"; exit 1; }
  echo "First run: installing with $PY (a few minutes)..."
  rm -rf .venv
  "$PY" -m venv .venv && ./.venv/bin/pip install -q -r requirements.txt || {
    echo "Install failed. Install Python 3.12 from https://www.python.org/downloads/ and run this again."
    rm -rf .venv; exit 1; }
fi
# Open the browser once the app is ready (headless mode skips Streamlit's first-run email prompt).
URL=http://localhost:8501
( until curl -s "$URL/_stcore/health" >/dev/null 2>&1; do sleep 1; done
  open "$URL" 2>/dev/null || xdg-open "$URL" 2>/dev/null ) &
./.venv/bin/streamlit run app.py
