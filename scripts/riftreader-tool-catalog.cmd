@echo off
setlocal
cd /d "%~dp0.."
python "%~dp0..\tools\riftreader_workflow\tool_catalog.py" %*
exit /b %ERRORLEVEL%
