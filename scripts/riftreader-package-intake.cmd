@echo off
setlocal
cd /d "%~dp0.."
python "%~dp0..\tools\riftreader_workflow\apply_package.py" %*
exit /b %ERRORLEVEL%
