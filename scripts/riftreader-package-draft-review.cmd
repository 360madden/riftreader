@echo off
REM Version: riftreader-package-draft-review-wrapper-v0.1.0
REM Purpose: Thin CMD wrapper for reviewing Local Artifact Bridge package drafts and optional dry-run.
setlocal
cd /d "%~dp0\.."
python "tools\riftreader_workflow\package_draft_review.py" %*
set "EXITCODE=%ERRORLEVEL%"
REM END_OF_SCRIPT_MARKER
exit /b %EXITCODE%
