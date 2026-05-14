@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
python "%~dp0capture_rift_window.py" %*
exit /b %errorlevel%
