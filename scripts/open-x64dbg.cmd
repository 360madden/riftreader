@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
python "%~dp0x64dbg_launcher.py" %*
exit /b %errorlevel%
