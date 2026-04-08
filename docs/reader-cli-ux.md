# Reader CLI UX Requirements

## Purpose

This document captures the desired command-line experience for `RiftReader.Reader`.

## Requirement Summary

The reader should support:

- **extensive and robust command-line switches** as the project grows
- **intuitive help output** that clearly explains each switch
- **colorized menus and prompts** where the terminal supports them
- **syntax highlighting or highlighted examples** in help text and guided output

This is a reasonable requirement for a tool that is expected to be used repeatedly during reverse-engineering and validation work.

## Intended UX Characteristics

### Switch design

- switches should be discoverable and predictable
- related operations should be grouped logically
- optional flags should be documented in help output
- new functionality should be added as switches rather than requiring code changes in the caller workflow

### Help behavior

- `--help` should print a useful overview, not just a usage line
- help should include examples for common workflows
- help should note when options are mutually exclusive or depend on each other
- help should surface the PTS-only constraint clearly

### Color and highlighting

- color should improve readability, not become a hard dependency
- menus, section headers, warnings, and examples should be visually distinct
- syntax-highlighted or color-emphasized examples should make command shapes easier to copy correctly
- the tool should degrade gracefully to plain text if ANSI color is unavailable

## Non-Goals

- no heavy graphical UI is required for the reader
- no dependency on a specific color library is mandated by this document
- no terminal-only behavior should block basic operation

## Early Examples of Good Switch Coverage

Future switches may reasonably cover:

- process targeting
- PTS validation profile selection
- memory read modes
- dump formatting
- logging verbosity
- snapshot output format
- validation correlation output

## Relationship to the Addon

The addon remains the in-game validation surface. The reader CLI should make it easy to:

- attach to the right PTS process
- choose the right inspection mode
- capture comparable output
- inspect results quickly during iteration

The CLI should reduce friction during reverse-engineering, not add ceremony.
