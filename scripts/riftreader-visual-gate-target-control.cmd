@echo off
setlocal
cd /d "%~dp0\.."
python ".\scripts\check_live_visual_gate_target_control.py" %*
exit /b %ERRORLEVEL%
