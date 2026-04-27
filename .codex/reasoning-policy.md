# RiftReader reasoning policy

## Default

Use **extra high reasoning** by default for work in `C:\RIFT MODDING\RiftReader`.

## Allowed low-reasoning cases

Low reasoning is allowed only for very basic, clearly safe tasks:

- read-only inspection
- listing files, symbols, or references
- simple summaries
- mechanical documentation or comment edits
- explicit-value low-risk config changes
- trivial local fixes with obvious cause and easy verification

## Do not lower reasoning for

- debugging
- root-cause analysis
- architecture or design choices
- multi-file or non-local edits
- risky or hard-to-revert changes
- ambiguous tasks
- security-sensitive logic
- reverse-engineering decisions or live workflow changes

## Fallback

When in doubt, use **extra high reasoning**.
