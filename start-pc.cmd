@echo off
rem Starts Brento in this window. The settings file in your home folder names the vault, so no path is needed here.
start "" http://127.0.0.1:8770
set "PY=python"
if defined BRENTO_PYTHON set "PY=%BRENTO_PYTHON%"
"%PY%" "%~dp0server.py"
if errorlevel 1 pause
