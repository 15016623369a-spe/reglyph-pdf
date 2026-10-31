@echo off
cd /d "%~dp0"
if not exist ".venv-editor\Scripts\python.exe" (
  echo Run install.bat with Python 3.11 first.
  pause
  exit /b 1
)
".venv-editor\Scripts\python.exe" launcher.py %*
if errorlevel 1 pause
