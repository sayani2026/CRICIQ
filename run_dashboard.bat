@echo off
setlocal
cd /d "%~dp0"
title CRICQ dashboard - close this window to stop
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (
  echo Python was not found. Run setup.bat first.
  pause
  exit /b 1
)
echo Starting CRICQ at http://localhost:8501  (your browser will open)
echo Close this window to stop the dashboard.
%PY% -m streamlit run dashboard\app.py --server.headless false --server.port 8501
pause
