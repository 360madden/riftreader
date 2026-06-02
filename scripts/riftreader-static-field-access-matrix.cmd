@echo off
setlocal
cd /d "%~dp0\.."
python -m tools.riftreader_workflow.static_field_access_matrix %*
