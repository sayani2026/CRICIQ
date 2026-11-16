@echo off
cd /d "%~dp0"
where code >nul 2>nul
if errorlevel 1 (
  echo VS Code was not found. Install it from https://code.visualstudio.com/ and tick "Add to PATH".
  pause
  exit /b 1
)
start "" code "%~dp0"
