@echo off
setlocal
cd /d "%~dp0.."
python "%~dp0..\tools\riftreader_workflow\opencode_bridge.py" --lane live-observer --run %*
exit /b %ERRORLEVEL%
