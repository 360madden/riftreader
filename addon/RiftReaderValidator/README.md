# RiftReaderValidator

Minimal helper addon for validating the external reader.

## Current Purpose

- capture on-demand snapshots of API-visible player data
- keep a small rolling history in saved variables
- mark a few important state transitions for later comparison
- show a basic in-game status window with indicator lights so validation activity is visible

## Commands

- `/rrv snapshot` - capture a validation snapshot
- `/rrv status` - print current addon status
- `/rrv clear` - clear saved snapshot history
- `/rrv ui` - toggle the status window
- `/rrv show` - show the status window
- `/rrv hide` - hide the status window
- `/rrv help` - print command help

## GUI

The addon now includes a small status window with:

- indicator lights for addon state, player visibility, snapshot freshness, and secure/combat mode
- current snapshot summary
- recent activity lines
- buttons for snapshot, refresh, clear, and hide

## Notes

- This addon is intentionally small and should remain reader-supporting only.
- If the client reports the addon as outdated, verify the `Environment` value in `RiftAddon.toc` against the current addon API level.
