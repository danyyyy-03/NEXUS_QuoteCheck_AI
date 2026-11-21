@echo off
setlocal
cd /d "%~dp0"
title NEXUS QuoteCheck AI - Setup
echo.
echo =================================================
echo  NEXUS QuoteCheck AI v0.1.0 - Windows Setup
 echo =================================================
echo.
py -3.12 --version
if errorlevel 1 goto no_python
if not exist ".venv\Scripts\python.exe" (
  echo Creating isolated Python 3.12 environment...
  py -3.12 -m venv .venv
  if errorlevel 1 goto failed
)
echo Installing PDF and Excel packages...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo.
echo SETUP COMPLETE. Now double-click run.bat.
pause
exit /b 0
:no_python
echo ERROR: Python 3.12 was not found.
echo Install Python 3.12 64-bit from https://www.python.org/downloads/
pause
exit /b 1
:failed
echo INSTALLATION FAILED. Screenshot this error message.
pause
exit /b 1
