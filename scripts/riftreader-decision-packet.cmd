@echo off
setlocal
cd /d "%~dp0.."
python "%~dp0..\tools\riftreader_workflow\decision_packet.py" %*
exit /b %ERRORLEVEL%
