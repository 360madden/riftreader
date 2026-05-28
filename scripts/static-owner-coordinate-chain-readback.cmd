@echo off
setlocal
cd /d "%~dp0\.."
python scripts\static_owner_coordinate_chain_readback.py %*
exit /b %ERRORLEVEL%
