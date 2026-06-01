@echo off
setlocal
cd /d "%~dp0.."
python tools\riftreader_workflow\ghidra_static_evidence.py %*
exit /b %ERRORLEVEL%
