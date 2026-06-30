@echo off
setlocal
cd /d "%~dp0.."
python "%~dp0..\tools\riftreader_workflow\postpatch_profile.py" %*
exit /b %ERRORLEVEL%
