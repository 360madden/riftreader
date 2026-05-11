# PRE_UPDATE_PROCESS_SWEEP

- CapturedUtc: 20260511T205115Z
- RepoRoot: C:\RIFT MODDING\RiftReader
- SearchPattern: (?i)(rift|glyph|gamigo)
- CandidateCount: 4
- TaskListMatchCount: 0
- GitStatusAfterProcessSweep: ?? handoffs/

Artifacts:
- process-candidates.json
- tasklist-verbose.csv
- tasklist-matches.txt
- git-status-after-process-sweep.txt

Interpretation:
- If CandidateCount is greater than 0, inspect process-candidates.json for the RIFT executable path and SHA256.
- If CandidateCount is 0 but TaskListMatchCount is greater than 0, inspect tasklist-matches.txt for window-title evidence.
- If both counts are 0, this shell cannot discover RIFT/Glyph/gamigo by process name, path, command line, or verbose tasklist output.
