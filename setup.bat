@echo off
setlocal
cd /d "%~dp0"
title CRICQ setup
echo ============================================================
echo  CRICQ setup - installs the Python libraries (one time)
echo ============================================================
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (
  echo.
  echo  Python was not found. Install Python 3.10 or newer from https://www.python.org/downloads/
  echo  and tick "Add Python to PATH", then run setup.bat again.
  echo.
  pause
  exit /b 1
)
%PY% --version
%PY% -m pip install --upgrade pip
%PY% -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo  SETUP FAILED - see the messages above.
  pause
  exit /b 1
)
echo.
echo  SETUP COMPLETE. Now double-click run_dashboard.bat
echo.
pause
