@echo off
setlocal
cd /d "%~dp0.."
python "%~dp0..\tools\riftreader_workflow\apply_package.py" --self-test --compact-json %*
exit /b %ERRORLEVEL%
