# 🟢 RiftReader / RiftScan Movement-Backed Actor Coordinate Truth Handoff

Created: 2026-04-30 10:49 America/New_York  
Primary repo: `C:\RIFT MODDING\RiftReader`  
Coordination repo: `C:\RIFT MODDING\Riftscan`  
Primary objective: **discovery first** — promote already-found coordinate truth, then chase durable recovery.

---

## 🚨 TL;DR

🟢 **Actor/player coordinate truth is found and now movement-backed.**  
Do **not** treat coordinates as still unresolved.

📌 Canonical proof coordinate source for current live process:

```text
source object:   0x216F2F26020
coord triplet:   0x216F2F26068
offset:          +0x48
formula:         0x216F2F26020 + 0x48 = 0x216F2F26068
```

🟢 Movement-backed synchronized live coordinate mirrors:

```text
+0x48 -> 0x216F2F26068
+0x88 -> 0x216F2F260A8
+0xD8 -> 0x216F2F260F8
```

🔴 Not-current/static secondary triplet:

```text
+0xE4 -> 0x216F2F26104
```

🟡 Best durable recovery lead:

```text
bridge/source-chain table: 0x216BE6A0000
0x216BE6A00B0 -> 0x216F2F26020
```

🔴 Still unresolved:

- durable owner/selector recovery after restart
- actor-facing/yaw truth
- which of `+0x48/+0x88/+0xD8` is engine-primary vs mirror/cache

---

## 🎯 Live target used

Verified current live RIFT target:

```text
Process: rift_x64
PID:     41220
HWND:    0xBD0D94
Title:   RIFT
Start:   2026-04-28T14:06:20.402266-04:00
```

⚠️ These PID/HWND/address values are session-local. Refresh after RIFT restart.

---

## 🟢 Proof coord anchor revalidated

Artifact:

```text
C:\RIFT MODDING\RiftReader\scripts\captures\codex-discovery-proof-anchor-20260430-102628.json
```

Revalidated values:

```text
ObjectBaseAddress:           0x216F2F26020
CoordRegionAddress:          0x216F2F26068
SourceObjectAddress:         0x216F2F26020
SourceCoordRelativeOffset:   72 / 0x48
CanonicalCoordSourceKind:    coord-trace-source-object
MatchSource:                 readerbridge-live
CoordMatchesWithinTolerance: true
```

Memory sample:

```text
X = 7259.063
Y = 875.5653
Z = 3052.8816
```

ReaderBridge expected:

```text
X = 7259.0600585938
Y = 875.57000732422
Z = 3052.8798828125
```

Deltas:

```text
DeltaX = 0.0029296875
DeltaY = -0.004699707
DeltaZ = 0.0017089844
```

✅ Conclusion: `0x216F2F26020 + 0x48` is proof-grade coordinate truth for this live process.

---

## 🧪 Source object neighborhood evidence

Artifact folder:

```text
C:\RIFT MODDING\RiftReader\scripts\captures\codex-coord-neighborhood-20260430-102652
```

Important files:

```text
source-object-0x216F2F26020-len768.json
coord-region-0x216F2F26068-len256.json
bridge-0x216BE6A0000-len512.json
```

Decoded source-object triplets before movement:

| Offset | Address | X | Y | Z | Status |
|---|---:|---:|---:|---:|---|
| `+0x48` | `0x216F2F26068` | `7259.06` | `875.57` | `3052.88` | 🟢 live coord mirror |
| `+0x88` | `0x216F2F260A8` | `7259.06` | `875.57` | `3052.88` | 🟢 live coord mirror |
| `+0xD8` | `0x216F2F260F8` | `7259.06` | `875.57` | `3052.88` | 🟢 live coord mirror |
| `+0xE4` | `0x216F2F26104` | `7222.65` | `873.14` | `3026.55` | 🔴 not current/live movement coord |

---

## 🧍 Movement-labeled coordinate proof

### ❌ Attempt 1 — SendInput 300ms `W`

Artifact:

```text
C:\RIFT MODDING\RiftReader\scripts\captures\codex-movement-labeled-coord-20260430-104518
```

Result:

```text
send exit: 0
movement:  none detected
```

### ❌ Attempt 2 — SendInput 1200ms `W`

Artifact:

```text
C:\RIFT MODDING\RiftReader\scripts\captures\codex-movement-labeled-coord-20260430-104610-longw
```

Result:

```text
send exit: 0
warning: foreground stayed on Codex, expected RIFT
movement: none detected
```

Interpretation: SendInput did not reliably reach the game window.

### ✅ Attempt 3 — AutoHotkey 1200ms `W`

Artifact:

```text
C:\RIFT MODDING\RiftReader\scripts\captures\codex-movement-labeled-coord-20260430-104716-ahk
```

Files:

```text
coord-offset-before-after-w-ahk.jsonl
send-w-ahk-1200ms.stdout.txt
send-w-ahk-1200ms.stderr.txt
```

AutoHotkey helper succeeded:

```text
[RiftAhkKey] Target PID : 41220
[RiftAhkKey] Target HWND: 0xBD0D94
[RiftAhkKey] Key        : w
[RiftAhkKey] Hold ms    : 1200
[RiftAhkKey] SUCCESS
```

Movement result:

| Offset | Before X | After X | ΔX | ΔY | ΔZ | Planar Δ | Meaning |
|---|---:|---:|---:|---:|---:|---:|---|
| `+0x48` | `7259.06` | `7260.59` | `+1.52` | `+0.11` | `+0.04` | `1.52` | 🟢 movement-backed live coord |
| `+0x88` | `7259.06` | `7260.59` | `+1.52` | `+0.11` | `+0.04` | `1.52` | 🟢 movement-backed mirror |
| `+0xD8` | `7259.06` | `7260.59` | `+1.52` | `+0.11` | `+0.04` | `1.52` | 🟢 movement-backed mirror |
| `+0xE4` | `7222.65` | `7222.65` | `0.00` | `0.00` | `0.00` | `0.00` | 🔴 not current movement coord |

✅ Conclusion: `+0x48`, `+0x88`, and `+0xD8` are synchronized live player-coordinate mirrors during real movement.  
📌 Keep `+0x48` as canonical because it is the validated proof anchor and ReaderBridge-matched coord region.

---

## 🔗 Bridge/source-chain candidate

Bridge candidate:

```text
0x216BE6A0000
```

Pre/post movement stable edges:

```text
0x216BE6A00A8 -> 0x21693FB9E48   # rejected trace/control object
0x216BE6A00B0 -> 0x216F2F26020   # validated coord source object
0x216BE6A00F8 -> 0x7FF7879B117E  # coord access instruction
```

Post-move bridge artifact:

```text
C:\RIFT MODDING\RiftReader\scripts\captures\codex-post-move-bridge-20260430-104814\bridge-0x216BE6A0000-postmove-len512.json
```

🟡 Status: high-confidence bridge/source-chain table, but not yet durable owner truth.

---

## 🧩 RiftScan coordination status

RiftScan has a packet verifier for the RiftReader actor-coordinate scan packet.

Verified packet:

```text
C:\RIFT MODDING\Riftscan\reports\generated\riftreader-delegate-actor-coordinate-scan-20260430-094639.json
```

Verifier command:

```powershell
cd 'C:\RIFT MODDING\Riftscan'
dotnet run --project .\src\RiftScan.Cli\RiftScan.Cli.csproj --configuration Release --no-restore -- verify riftreader-actor-coordinate-scan 'reports\generated\riftreader-delegate-actor-coordinate-scan-20260430-094639.json'
```

Expected verified fields:

```text
success:                         true
source_object_address_hex:        0x216F2F26020
coord_region_address_hex:         0x216F2F26068
source_coord_relative_offset_hex: 0x48
bridge_region_base_hex:           0x216BE6A0000
trace_object_address_hex:         0x21693FB9E48
```

🟢 RiftScan can now consume the RiftReader coordinate truth packet.  
🟡 Next useful RiftScan step is targeted replay capture/analysis around source object + bridge table.

---

## 🔴 Important correction / workflow rule

Do **not** say “coordinates are still unresolved.”

Correct state:

```text
coordinates:       🟢 found / validated / movement-backed
coord source:      🟢 0x216F2F26020
canonical coord:   🟢 +0x48 / 0x216F2F26068
live mirrors:      🟢 +0x88, +0xD8
not-current coord: 🔴 +0xE4
bridge candidate:  🟡 0x216BE6A0000
actor-facing:      🔴 unresolved
durable recovery:  🔴 unresolved
```

Discovery priority means: use this truth immediately. Do not waste cycles re-proving that actor coordinates exist unless the live process restarted or validation contradicts it.

---

## 🧭 Best next action

🚀 Chase durable recovery from the bridge table:

```text
0x216BE6A0000 + 0xB0 -> 0x216F2F26020
```

Recommended immediate read-only path:

1. 🔎 Scan pointers to `0x216BE6A0000`.
2. 🔎 Read parent/owner neighborhoods that point to the bridge table.
3. 🧪 Confirm whether the parent remains stable across movement/refresh.
4. 🧭 Use the durable parent to recover the source object after restart.
5. 🎯 Separately inspect nearby source object basis/orientation fields for actor-facing.

---

## 🛠️ Resume commands

Refresh target:

```powershell
Get-Process -Name rift_x64 | Where-Object { $_.MainWindowHandle -ne 0 } |
  Select-Object Id,ProcessName,@{n='MainWindowHandleHex';e={'0x{0:X}' -f $_.MainWindowHandle.ToInt64()}},MainWindowTitle,StartTime,Responding
```

Revalidate proof coord anchor read-only:

```powershell
cd 'C:\RIFT MODDING\RiftReader'
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\resolve-proof-coord-anchor.ps1 `
  -ProcessId 41220 `
  -TargetWindowHandle 0xBD0D94 `
  -SkipRefresh `
  -RefreshAttempts 0 `
  -Json
```

Read source object:

```powershell
.\scripts\run-reader.cmd --pid 41220 --address 0x216F2F26020 --length 768 --json
```

Read bridge table:

```powershell
.\scripts\run-reader.cmd --pid 41220 --address 0x216BE6A0000 --length 512 --json
```

Movement input helper that actually worked:

```powershell
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass -File .\scripts\send-rift-key-ahk.ps1 `
  -Key w `
  -HoldMilliseconds 1200 `
  -TargetProcessId 41220 `
  -TargetWindowHandle 0xBD0D94 `
  -NoRefocus
```

⚠️ Only send live input after explicit user approval.

---

## 🧾 Validation / evidence summary

🟢 Current process/window verified.  
🟢 Proof coord anchor revalidated against ReaderBridge.  
🟢 Source object neighborhood dumped.  
🟢 Movement-labeled proof succeeded with AutoHotkey input.  
🟢 `+0x48/+0x88/+0xD8` moved in sync.  
🟢 `+0xE4` did not move.  
🟢 Bridge table stayed stable after movement.  
🟢 RiftReader git tree was clean after artifact creation because captures are ignored.

---

## ⚠️ Remaining risks

🔴 PID/address values are live-session-specific. Refresh after restart.  
🔴 Actor-facing/yaw truth remains unresolved.  
🟡 Bridge table is strong but not durable owner truth yet.  
🟡 `+0x48/+0x88/+0xD8` are synchronized; primary-vs-cache role still needs finer temporal sampling or engine write-path evidence.  
🟡 SendInput did not reliably focus/send to RIFT; AutoHotkey did.

---

## 🌟 Optional top 5 next recommended actions

1. 🔗 Pointer-scan for parents of `0x216BE6A0000` to chase durable recovery.
2. 🧪 Capture another movement pulse while polling bridge + source object together.
3. 🎯 Inspect source object nearby basis/orientation fields now that coordinate source is proven.
4. 📦 Feed this movement-backed truth into RiftScan targeted replay capture.
5. 📝 Promote a compact `current-actor-coordinate-truth.json` artifact so future agents cannot miss the truth again.

---

END_OF_HANDOFF
