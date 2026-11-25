@echo off
rem Opens Daytag, and starts it first when it is not running. The Start menu shortcut from install.ps1 points here.
rem launcher.py also lets the browser in: Daytag opens only for the person it belongs to.
set "PY=pythonw"
if defined DAYTAG_PYTHON set "PY=%DAYTAG_PYTHON:python.exe=pythonw.exe%"
if defined DAYTAG_PYTHON if not exist "%PY%" set "PY=%DAYTAG_PYTHON%"
start "" "%PY%" "%~dp0launcher.py" %*
