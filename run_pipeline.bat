@echo off
setlocal
cd /d "%~dp0"
title CRICQ pipeline
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
echo Rebuilding every CRICQ output from the Data Pack (about 70 seconds)...
%PY% pipeline.py
if errorlevel 1 goto end
%PY% tools\make_submission.py
%PY% tools\make_photo_placeholders.py
:end
pause
