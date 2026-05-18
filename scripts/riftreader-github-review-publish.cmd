@echo off
REM Version: riftreader-github-review-publish-wrapper-v0.1.0
REM Total-Character-Count: 319
REM Purpose: Thin CMD launcher for Python-owned RiftReader GitHub review publish workflow.
cd /d "%~dp0\.."
python "tools\riftreader_workflow\github_review_publish.py" %*
exit /b %ERRORLEVEL%
REM END_OF_SCRIPT_MARKER
