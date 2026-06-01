@echo off
setlocal
cd /d "%~dp0\.."
python scripts\facing_target_promotion_apply.py %*
