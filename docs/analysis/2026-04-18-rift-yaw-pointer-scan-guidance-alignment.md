# Rift yaw pointer-scan guidance: alignment with current repo strategy

## Verdict

The external Rift-specific yaw guidance is useful, but it should be treated as a
**heuristic overlay**, not a replacement for the repo's current best
orientation path.

The biggest useful takeaways are:

1. **Start from position/coord truth first.**
2. **Bias toward nearby orientation data in the same actor/source family.**
3. **Prefer turn-only stimuli over movement when proving yaw changes.**
4. **If pointer-chain proof is needed, keep pointer depth shallow and filter by
   observed end offsets.**
5. **Use restart/session-stability checks as a proof gate, not as the first
   discovery tool.**

## What already aligns with the repo

The repo already has several orientation-specific findings that match the
guidance well:

| External guidance | Current repo alignment |
|---|---|
| Position is the best starting point | `--read-player-current`, `--scan-readerbridge-player-coords`, and current-player anchor work all start from live coord truth. |
| Yaw is usually near position or in the same actor struct | The selected source object used by `--read-player-orientation` exposes coord blocks at `+0x48` / `+0x88` and duplicated basis/orientation blocks at `+0x60/+0x6C/+0x78` and `+0x94/+0xA0/+0xAC`. |
| Yaw often lives near other transform data | Current orientation recovery derives yaw/pitch from the forward row of those basis blocks rather than from an isolated scalar. |
| Turn-only stimuli are cleaner than movement-heavy proof | Existing orientation evidence already shows left/right turn stimuli changing yaw without requiring coord drift. |
| Session stability matters | The repo already uses ledgers, candidate screens, and recovery artifacts to downrank unstable candidates. |

## What should change in future testing

### 1. Use the guidance to tighten candidate prioritization

When evaluating new yaw or rotation candidates, prefer this order:

1. **Selected source / owner-source basis path**
2. **Near-coord triplets in the same family**
3. **Nearby rotation-like scalars or basis rows within roughly `0x40–0xC0` of
   live coord blocks**
4. **Only then** broader scalar/pointer-chain hunts

This means the current best live yaw path should still be the existing source
basis path, not a fresh broad scalar search.

### 2. Prefer turn-only stimulus when validating yaw

For yaw-specific tests:

- prefer **left/right turn stimuli**
- avoid treating forward/back movement as the main yaw proof
- treat wall-adjacent movement results as collision-ambiguous

This is especially important because the recent live movement work showed how
easy it is to misread forward-motion tests near obstacles.

### 3. If pointer-chain proof is revisited, keep it shallow

If we ever need a stable pointer-chain proof for yaw:

- start with **max level 4**, not a deep search
- only increase toward **5–6** if evidence forces it
- keep max offsets conservative
- filter hard using known end-offset neighborhoods near current coord / basis
  data

For this repo, the most relevant end-offset neighborhoods are not arbitrary
yaw-scalar guesses; they are the already observed source-family offsets:

- coord blocks around `+0x48` / `+0x88`
- basis blocks around `+0x60/+0x6C/+0x78`
- duplicate basis around `+0x94/+0xA0/+0xAC`

### 4. Use restart stability as a later gate

The guidance's pointer-map idea is still valuable, but in this repo it should be
used **after** candidate discovery, not before.

The right order here is:

1. prove the live orientation family/source
2. narrow to the correct local block/offset
3. only then do restart/session survivability checks

## What does **not** change

The guidance does **not** overturn the repo's current best orientation finding:

> The selected source basis remains the best current actor-orientation anchor.

Direct standalone yaw-scalar proof is still secondary to the basis-derived path
until contradictory live evidence appears.

## Practical rule going forward

For Rift yaw/orientation work in this repo:

1. **Coord truth first**
2. **Source-family local neighborhood second**
3. **Turn stimulus third**
4. **Pointer-chain proof last**

## Most relevant files

- `C:\RIFT MODDING\RiftReader\scripts\capture-actor-orientation.ps1`
- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Program.cs`
- `C:\RIFT MODDING\RiftReader\reader\RiftReader.Reader\Cli\ReaderOptionsParser.cs`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-10-orientation-evidence-report.md`
- `C:\RIFT MODDING\RiftReader\docs\analysis\2026-04-10-basis-integrity-report.md`
