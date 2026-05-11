# RiftReader Pre-Update Glyph Patch Handoff - 2026-05-11

## Status

PRE-UPDATE BASELINE PRESERVED. GLYPH PATCH PENDING.

The logged-in RIFT client was still running while Glyph reported a pending update. The pre-update process identity and ReaderBridge snapshot were captured and pushed before allowing the patch.

## Baseline commit

- Repository: 360madden/riftreader
- Branch: main
- Baseline commit: a3369171bf771c3d263121edb94e39ab7f23e9f2
- Local HEAD before this handoff: a3369171bf771c3d263121edb94e39ab7f23e9f2
- Baseline artifact folder: handoffs/current/pre-update-baseline/20260511T205115Z-process-sweep-v030

## Captured RIFT executable identity

- ProcessName: rift_x64
- ProcessId: 35728
- MainWindowTitle: RIFT
- MainWindowHandle: 0x60E42
- Path: C:\Program Files (x86)\Glyph\Games\RIFT\Live\rift_x64.exe
- FileLastWriteUtc: 05/05/2026 11:59:05
- FileLengthBytes: 60044224
- SHA256: E3F5BAD4285C02BD873915A4F01A729E3013881E9AE82FF4438741D8B903C1BC

## Captured ReaderBridge truth

- Character: Atank
- Level: 45
- Calling: warrior
- Role: tank
- LocationName: Tavril Plaza
- Zone: z487C9102D2EA79BE
- CoordX: 7406.330078125
- CoordY: 871.76995849609
- CoordZ: 3029.7700195312
- SourceMode: DirectAPI
- ExportCount: 1932
- TelemetrySequence: 21688

## Known caveats

- tasklist matching did not produce useful evidence; process identity was captured from Get-Process/CIM instead.
- One browser process matched because the Edge title contained RiftReader; ignore the msedge candidate.
- process-candidates.json is valid JSON but contains a nested array shape from the capture script. Future parsers should flatten arrays defensively.
- API-facing/yaw values were not available from this ReaderBridge snapshot. Position truth was available through DirectAPI.
- Do not assume existing memory offsets remain valid after the Glyph patch.

## Next action after this handoff is pushed

1. Allow Glyph to update RIFT.
2. Launch/log back into RIFT.
3. Confirm character Atank is in-world.
4. Run the post-update baseline.
5. Compare:
   - rift_x64.exe SHA256
   - executable timestamp and file length
   - PID/HWND/window title
   - ReaderBridge status
   - character/zone/position truth
   - current-truth/proof-anchor status
6. Do not trust old offsets until proof-anchor validation succeeds.

## Do not do yet

- Do not edit current-truth.md as if offsets survived.
- Do not overwrite the pre-update baseline artifact folder.
- Do not mix pre-update and post-update artifacts in the same folder.
- Do not treat the public event post as sufficient technical patch evidence; the local Glyph update prompt is the stronger signal.

## Resume prompt

Resume RiftReader after Glyph patch using:

PRE_UPDATE_GLYPH_PATCH_PENDING_HANDOFF_2026-05-11.md

Start with post-update baseline capture and compare against baseline commit a3369171bf771c3d263121edb94e39ab7f23e9f2.

## Generated

- GeneratedUtc: 2026-05-11T21:05:16.5017617Z
- Script: riftreader-create-preupdate-handoff-v0.1.1

