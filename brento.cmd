@echo off
rem Opens Brento. Starts the server first, without a window, when it is not running yet.
rem The Start menu shortcut from install.ps1 points here.
netstat -ano | findstr /c:"127.0.0.1:8770 " | findstr /c:"0.0.0.0:0 " >nul
if errorlevel 1 (
  wscript.exe "%~dp0start-hidden.vbs"
  rem Give the server a moment to open its port.
  ping -n 5 127.0.0.1 >nul
)
rem An app window without an address bar. Chrome first, because it keeps the sign-ins of the tools in the dock.
set "PF86=%ProgramFiles(x86)%"
set "APPWIN="
if exist "%PF86%\Microsoft\Edge\Application\msedge.exe" set "APPWIN=%PF86%\Microsoft\Edge\Application\msedge.exe"
if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" set "APPWIN=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
if exist "%PF86%\Google\Chrome\Application\chrome.exe" set "APPWIN=%PF86%\Google\Chrome\Application\chrome.exe"
if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set "APPWIN=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "APPWIN=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if defined APPWIN (
  start "" "%APPWIN%" --app=http://127.0.0.1:8770/
) else (
  start "" http://127.0.0.1:8770/
)
