# RiftReader Desktop ChatGPT Harness

- Version: riftreader-desktop-chatgpt-harness-doc-v0.1.0
- Total-Character-Count: 2565
- Purpose: Define the phase 1 local harness that lets ChatGPT Desktop drive RiftReader work through deterministic repo and Google Drive artifacts.

## Scope

This harness keeps ChatGPT Desktop at the reasoning layer while local repo-owned scripts handle deterministic status, prompt, and package artifact creation.

## Authority model

| Location | Role |
|---|---|
| `C:\RIFT MODDING\RiftReader` | Local execution repo and validation environment |
| GitHub `360madden/riftreader` | Durable source of truth |
| `G:\My Drive\RiftReader` | Artifact transport, archive, status, handoff, and package inbox |
| ChatGPT Desktop | Reasoning console and review surface |

## Phase 1 commands

Run status and write Drive status artifacts:

```powershell
& "C:\RIFT MODDING\RiftReader\scripts\riftreader-desktop-harness.ps1" -Action status -WriteStatus
```

Emit clean JSON:

```powershell
& "C:\RIFT MODDING\RiftReader\scripts\riftreader-desktop-harness.ps1" -Action status -Json -WriteStatus
```

Generate a prompt artifact for ChatGPT Desktop:

```powershell
& "C:\RIFT MODDING\RiftReader\scripts\riftreader-desktop-harness.ps1" -Action prompt -Task "Continue Drive integration" -WriteStatus
```

Create a status package ZIP in the Drive inbox:

```powershell
& "C:\RIFT MODDING\RiftReader\scripts\riftreader-desktop-harness.ps1" -Action package -WriteStatus
```

## Safety rules

1. The harness does not run ProofOnly, Stage 1 promotion, visual gates, movement, or live RIFT input.
2. The harness treats stale PID/HWND/proof-anchor data as out of scope while Drive integration is selected.
3. The harness may write Drive artifacts but does not stage, commit, push, delete, or reset repo files.
4. Installer/commit scripts must use explicit git allowlists.
5. Known proof-anchor residue may be documented and excluded but must not be touched during Drive integration.

## Phase 1 actions

| Action | Writes repo? | Writes Drive? | Purpose |
|---|---:|---:|---|
| `status` | No | Optional | Summarize repo, remote, dirty-file classification, and Drive inbox status |
| `prompt` | No | Yes | Create a compact prompt file for ChatGPT Desktop |
| `package` | No | Yes | Create a ZIP containing status and selected docs/status artifacts |

## Next phase

Phase 2 can add patch-package intake around this harness, but it should reuse the existing Drive inbox helper and keep repo mutation behind explicit allowlisted validation.

# END_OF_SCRIPT_MARKER
