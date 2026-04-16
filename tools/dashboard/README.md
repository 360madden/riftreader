# RiftReader Dashboard

Local dashboard for summarizing branch/worktree state in this repo, with an
optional file-based live overlay for current worktree + player/target details.

## What it does

- reads a generated snapshot from `dashboard-data.js`
- shows a branch-aware overview in the browser
- optionally overlays live current-worktree + player/target details from `dashboard-live-data.js`
- does **not** edit git state, switch branches, or poll a backend

## Regenerate the dashboard data

```powershell
C:\RIFT MODDING\RiftReader\scripts\build-dashboard-summary.ps1
```

That rewrites:

- `C:\RIFT MODDING\RiftReader\tools\dashboard\dashboard-data.js`

Regenerate the live dashboard payload:

```powershell
C:\RIFT MODDING\RiftReader\scripts\build-dashboard-live-data.ps1
```

That rewrites:

- `C:\RIFT MODDING\RiftReader\tools\dashboard\dashboard-live-data.js`

## Open the dashboard

Preferred:

```powershell
C:\RIFT MODDING\RiftReader\scripts\open-dashboard.ps1
```

Live mode:

```powershell
C:\RIFT MODDING\RiftReader\scripts\open-dashboard.ps1 -Live
```

Smoke check:

```powershell
C:\RIFT MODDING\RiftReader\scripts\test-dashboard-prototype.ps1
```

Cmd wrapper:

```cmd
C:\RIFT MODDING\RiftReader\scripts\open-dashboard.cmd
```

Manual fallback:

- open `C:\RIFT MODDING\RiftReader\tools\dashboard\index.html` in a browser

## Key files

- `C:\RIFT MODDING\RiftReader\tools\dashboard\index.html`
- `C:\RIFT MODDING\RiftReader\tools\dashboard\app.js`
- `C:\RIFT MODDING\RiftReader\tools\dashboard\styles.css`
- `C:\RIFT MODDING\RiftReader\scripts\build-dashboard-summary.ps1`

## Current limits

- data is only as fresh as the latest generator run
- live mode depends on a running Rift client plus the latest available ReaderBridge saved-variable snapshot
- rich branch-local coverage is intentionally selective
- no backend or localhost service
- live refresh is file-based and local-only
- no write actions beyond regenerating the dashboard payload files
