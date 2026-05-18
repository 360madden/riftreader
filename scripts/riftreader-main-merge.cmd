@echo off
REM Version: riftreader-main-merge-wrapper-v0.1.0
REM Total-Character-Count: 293
REM Purpose: Thin CMD launcher for Python-owned RiftReader main merge workflow helper.
cd /d "%~dp0\.."
python "tools\riftreader_workflow\main_merge.py" %*
exit /b %ERRORLEVEL%
REM END_OF_SCRIPT_MARKER
