@echo off
cd /d "%~dp0"
py -3.11 bootstrap.py
set "INSTALL_RESULT=%errorlevel%"
pause
exit /b %INSTALL_RESULT%
