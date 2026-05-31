@echo off
setlocal
cd /d "%~dp0.."
python tools\riftreader_workflow\validation_ledger.py %*
