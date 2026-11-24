@echo off
rem Starts Brento when it is not running, and opens it. What goes wrong is said in this window.
set "PY=python"
if defined BRENTO_PYTHON set "PY=%BRENTO_PYTHON%"
"%PY%" "%~dp0launcher.py"
if errorlevel 1 pause
