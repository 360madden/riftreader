# Helper App Standards

## Purpose

High-value helper apps and scripts that are expected to be reused should live in the repository instead of being recreated repeatedly in chat. This reduces workflow drift, preserves tested behavior, and saves operator time.

## Rules

1. Reuse existing repo helpers before creating new helpers.
2. Patch or extend an existing helper when the workflow is the same or adjacent.
3. Create a new helper only when there is no suitable existing repo-owned helper.
4. Every helper script must include:
   - `Version`
   - `Total-Character-Count`
   - `Purpose`
   - `END_OF_SCRIPT_MARKER`
5. Helper behavior should be configurable with command-line switches where practical.
6. Machine-readable mode must keep JSON output clean and parseable.
7. Human-readable mode may use progress/status text, but must not corrupt JSON output.
8. Movement, input, `/reloadui`, screenshot key, Cheat Engine use, Git mutation, and proof promotion must be explicit in script output and safety metadata.
9. Larger scripts should include meaningful error checking and artifact/log output.
10. After writing code, do a bug-check and fix pass before delivering the code or patch.

## Preferred helper parameters

Reusable helpers should usually support relevant switches such as:

- `-Json`
- `-OutputRoot`
- `-ProcessName`
- `-ProcessId`
- `-TargetWindowHandle`
- `-NoMovement`
- `-DryRun`
- timeout/retry/scan tuning switches when applicable

## Time management

Avoid repeated local one-off testing unless it proves something new, gates a risky change, or diagnoses a real failure. Prefer committed reusable helpers plus fast fix cycles when real execution reveals a bug.
