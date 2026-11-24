@echo off
rem Opens Brento, and starts it first when it is not running. The Start menu shortcut from install.ps1 points here.
rem launcher.py also lets the browser in: Brento opens only for the person it belongs to.
set "PY=pythonw"
if defined BRENTO_PYTHON set "PY=%BRENTO_PYTHON:python.exe=pythonw.exe%"
if defined BRENTO_PYTHON if not exist "%PY%" set "PY=%BRENTO_PYTHON%"
start "" "%PY%" "%~dp0launcher.py" %*
