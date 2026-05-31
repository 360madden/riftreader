@echo off
setlocal
cd /d "%~dp0\.."
python scripts\static_owner_camera_yaw_classification.py %*
