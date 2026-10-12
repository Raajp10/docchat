@echo off
setlocal enabledelayedexpansion
REM Windows: first run installs everything, then opens the app in your browser.
cd /d "%~dp0"
if not exist .venv\Scripts\streamlit.exe (
  REM Python 3.14 is too new for the search model library, so prefer 3.13 -> 3.10.
  set PY=python
  for %%v in (3.10 3.11 3.12 3.13) do py -%%v -c "" >nul 2>&1 && set PY=py -%%v
  echo First run: installing, this takes a few minutes...
  if exist .venv rmdir /s /q .venv
  !PY! -m venv .venv
  .venv\Scripts\pip install -q -r requirements.txt
  if errorlevel 1 (
    echo Install failed. Install Python 3.12 from https://www.python.org/downloads/ and run this again.
    rmdir /s /q .venv
    pause
    exit /b 1
  )
)
REM Open the browser once the app is ready (headless mode skips Streamlit's first-run email prompt).
start "" /b powershell -NoProfile -Command "while(-not(Test-NetConnection localhost -Port 8501 -InformationLevel Quiet -WarningAction SilentlyContinue)){Start-Sleep 1}; Start-Process http://localhost:8501"
.venv\Scripts\streamlit run app.py
