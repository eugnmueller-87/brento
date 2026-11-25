@echo off
rem Starts Daytag when it is not running, and opens it. What goes wrong is said in this window.
set "PY=python"
if defined DAYTAG_PYTHON set "PY=%DAYTAG_PYTHON%"
"%PY%" "%~dp0launcher.py"
if errorlevel 1 pause
