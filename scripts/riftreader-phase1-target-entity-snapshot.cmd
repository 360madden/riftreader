@echo off
setlocal
cd /d "%~dp0\.."
python scripts\phase1_target_entity_snapshot.py %*
exit /b %ERRORLEVEL%
