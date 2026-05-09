@echo off
setlocal
cd /d "%~dp0\.."
python ".\scripts\check_rift_target_control.py" %*
exit /b %ERRORLEVEL%
