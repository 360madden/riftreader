@echo off
setlocal
cd /d "%~dp0.."
python "%~dp0rift_emergency_key_release.py" %*
exit /b %ERRORLEVEL%
