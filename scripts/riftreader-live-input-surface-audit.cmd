@echo off
setlocal
cd /d "%~dp0.."
python "%~dp0live_input_surface_audit.py" %*
exit /b %ERRORLEVEL%
