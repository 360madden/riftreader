# RiftReader Drive Inbox Workflow

## Purpose

This workflow makes `G:\My Drive\RiftReader` the standard landing zone for packaged helper apps, patch bundles, prompts, and handoff artifacts produced through ChatGPT Desktop or Codex-assisted work.

The goal is to stop treating `Downloads` as the project archive. Downloads can still be the browser's temporary landing folder, but project artifacts should be imported into the RiftReader Drive inbox with SHA-256 verification and a manifest.

## Authority model

| Location | Role | Rule |
|---|---|---|
| `C:\RIFT MODDING\RiftReader` | Local execution repo | Work here. Validate here. Do not replace with Drive. |
| GitHub `360madden/riftreader` | Durable source of truth | Commit/push only after explicit validation. |
| `G:\My Drive\RiftReader` | Transport/archive/status | Store packages, manifests, handoffs, status, and run summaries. |
| `Downloads` | Temporary browser landing zone | Import from here, then stop using it as project storage. |

## Drive directory contract

```text
G:\My Drive\RiftReader\
  inbox\
    packages\
    scripts\
    prompts\
    handoffs\
    manifests\
  package-archive\
  status\
    imports\
  handoffs\
    current\
  logs\
```

## Commands after install

Bootstrap or repair Drive folder structure:

```powershell
& "C:\RIFT MODDING\RiftReader\scriptsiftreader-drive-inbox.ps1" -Action bootstrap -WriteStatus
```

Check Drive inbox status:

```powershell
& "C:\RIFT MODDING\RiftReader\scriptsiftreader-drive-inbox.ps1" -Action status -WriteStatus
```

Import a package from Downloads into the Drive inbox:

```powershell
& "C:\RIFT MODDING\RiftReader\scriptsiftreader-drive-inbox.ps1" -Action import -Source "$env:USERPROFILE\Downloads\SomePackage.zip" -Lane packages -WriteStatus
```

Import and remove the source only after SHA-256 verification:

```powershell
& "C:\RIFT MODDING\RiftReader\scriptsiftreader-drive-inbox.ps1" -Action import -Source "$env:USERPROFILE\Downloads\SomePackage.zip" -Lane packages -WriteStatus -RemoveSourceAfterVerify
```

Clean JSON output for Codex/automation:

```powershell
& "C:\RIFT MODDING\RiftReader\scriptsiftreader-drive-inbox.ps1" -Action status -Json
```

## Safety rules

1. The helper does not perform Git commits or pushes.
2. The helper does not delete source files unless `-RemoveSourceAfterVerify` is explicitly used.
3. Source deletion occurs only after destination SHA-256 equals source SHA-256.
4. The Drive inbox is not an execution authority. Imported packages still need repo-side validation before use.
5. Future package installers should write summaries to `G:\My Drive\RiftReader\status` and use explicit git allowlists.

## ChatGPT Desktop workflow

1. ChatGPT produces a ZIP/helper package.
2. Browser downloads it wherever Windows places downloads.
3. Run the import command to place it into `G:\My Drive\RiftReader\inbox\packages`.
4. Use a repo-owned installer/importer to apply it into `C:\RIFT MODDING\RiftReader`.
5. Validate, stage explicit files only, commit, push, and verify remote SHA.

## Codex CLI workflow

Codex should consume the same artifacts and status files instead of rediscovering basic local state repeatedly. Preferred pattern:

```text
helper status/import/validate -> JSON/MD artifact -> Codex reads artifact -> Codex edits/tests -> helper validates
```

This keeps Codex in the higher-value closed-loop coding role and keeps low-level file/package/status operations deterministic and fast.
