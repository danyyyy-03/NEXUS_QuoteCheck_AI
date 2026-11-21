@echo off
setlocal
cd /d "%~dp0"
title NEXUS QuoteCheck AI - Build Windows EXE
if not exist ".venv\Scripts\python.exe" (
  echo Run setup.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install "pyinstaller>=6,<7"
if errorlevel 1 goto failed
echo Building an experimental Windows executable...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name "NEXUS_QuoteCheck_AI" --add-data "samples;samples" --collect-all pymupdf --collect-all openpyxl app.py
if errorlevel 1 goto failed
echo.
echo SUCCESS: dist\NEXUS_QuoteCheck_AI.exe
echo IMPORTANT: Test on another Windows PC before publishing.
echo Ollama and its model must be installed separately for AI features.
pause
exit /b 0
:failed
echo BUILD FAILED. Please screenshot the error.
pause
exit /b 1
