@echo off
setlocal
cd /d "%~dp0\.."
python tools\riftreader_workflow\current_truth_refresh_apply.py %*
