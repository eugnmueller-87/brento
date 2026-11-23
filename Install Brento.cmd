@echo off
rem Double-click to install Brento for yourself. No admin rights needed.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
echo.
echo You can close this window.
pause >nul
