@echo off
setlocal
cd /d "%~dp0.."
python "%~dp0current_pid_family_neighborhood_analysis.py" %*
exit /b %ERRORLEVEL%
