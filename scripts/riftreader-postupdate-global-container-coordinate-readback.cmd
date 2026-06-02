@echo off
setlocal
cd /d "%~dp0.."
python ".\scripts\postupdate_global_container_coordinate_readback.py" %*
