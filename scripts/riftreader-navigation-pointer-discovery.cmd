@echo off
setlocal
cd /d "%~dp0.."
python "%~dp0..\tools\riftreader_workflow\navigation_pointer_discovery.py" %*
exit /b %ERRORLEVEL%
