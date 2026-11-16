@echo off
setlocal
cd /d "%~dp0"
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
set /p NAME=Name to print on the report cover: 
%PY% report\build_report.py "%NAME%"
echo Report written to report\CRICQ_Methodology_Report.pdf
pause
