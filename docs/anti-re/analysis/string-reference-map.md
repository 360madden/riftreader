# String Reference Map

Created: 2026-07-11
Status: **needs execution**
Tool: Ghidra headless + manual analysis

## Purpose

Map unique strings near the coordinate code paths in `rift_x64.exe`. Strings
provide stable anchors for finding coordinate-related functions via xref
tracing.

## Approach

1. Extract all strings from `.rdata` section
2. Filter for player/position/coordinate-related strings
3. For each candidate string, find xrefs in Ghidra
4. For each xref, identify the containing function
5. Classify functions by their role (reader, writer, updater, validator)

## Candidate String Categories

| Category | Examples | Value |
|---|---|---|
| Error messages | "Invalid position", "Coordinate out of range" | High — unique to coordinate code |
| Debug output | Format strings with float coordinates | High — near coordinate handling |
| Log messages | "Player moved to", "Position updated" | High — direct coordinate reference |
| UI labels | "X:", "Y:", "Z:", "Position" | Low — too generic |
| Network messages | Coordinate sync packets | Medium — may be obfuscated |

## Analysis

_Pending execution._
