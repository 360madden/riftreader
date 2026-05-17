@echo off
setlocal
cd /d "%~dp0.."
python "%~dp0..\tools\riftreader_workflow\status_packet.py" %*
exit /b %ERRORLEVEL%
