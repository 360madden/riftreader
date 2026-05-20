@echo off
setlocal
cd /d "%~dp0\.."
python .\scripts\character_select_automation_plan.py %*
exit /b %ERRORLEVEL%
