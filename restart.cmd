@echo off
rem Restarts the Brento without a window. The scheduled task "Brento" runs this through start-hidden.vbs
rem at logon and every morning at 05:00, so a reboot or new server code never leaves an old page running.
rem start-pc.cmd stays the manual way in.
rem A listening socket has no remote end (0.0.0.0:0). Matching that instead of the word LISTENING works in any
rem Windows language: a German netstat says ABHOEREN.
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /c:"127.0.0.1:8770 " ^| findstr /c:"0.0.0.0:0 "') do taskkill /pid %%p /f >nul 2>&1
rem The old process needs a moment to let go of the port.
ping -n 3 127.0.0.1 >nul
rem The settings file names the vault. The log goes next to it: ~/.leitstand for an install from before the setup.
set "BRENTO_DIR=%USERPROFILE%\.brento"
if exist "%USERPROFILE%\.leitstand" set "BRENTO_DIR=%USERPROFILE%\.leitstand"
if not exist "%BRENTO_DIR%" mkdir "%BRENTO_DIR%"
rem The installer names the exact Python in BRENTO_PYTHON. Without it, the one on the PATH.
set "PY=python"
if defined BRENTO_PYTHON set "PY=%BRENTO_PYTHON%"
"%PY%" "%~dp0server.py" > "%BRENTO_DIR%\server.log" 2>&1
