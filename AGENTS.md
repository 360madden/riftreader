# RiftReader Agent Instructions

## Repo-scoped reasoning policy

This repository uses a **quality-first reasoning policy** for Codex and similar coding agents.

- Default to **extra high reasoning** for work in this repo.
- You may lower reasoning to **low** only for very basic, clearly safe tasks.
- If there is any uncertainty about task risk, ambiguity, or required depth, stay at **extra high reasoning**.

Low reasoning is allowed only for tasks like:

- read-only inspection
- listing files, symbols, references, or command outputs
- simple summaries of already-read material
- mechanical doc/comment/copy edits with no design choice
- explicit-value low-risk config updates
- trivial, local, obvious fixes with easy verification

Do **not** lower reasoning for:

- debugging or root-cause analysis
- architecture or design changes
- behavior changes with non-obvious impact
- multi-file code edits unless they are purely mechanical and trivial
- risky, hard-to-revert, or high-blast-radius changes
- ambiguous requirements
- security-sensitive logic
- reverse-engineering decisions or workflow changes that affect live proof quality

When a task mixes simple and non-simple work, use the higher reasoning level for the full task.

## Policy file

See `C:\RIFT MODDING\RiftReader\.codex\reasoning-policy.md` for the same policy in a dedicated repo-local reference file.
