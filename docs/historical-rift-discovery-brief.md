# Historical Rift discovery brief

This note captures **old public Rift reverse-engineering clues** that may still
help current discovery work in `RiftReader`.

These sources are primarily from **2011-era 32-bit Rift clients**. Treat the
numeric offsets as **historical only** unless revalidated in the current
`rift_x64.exe` client. The useful part is usually the **field role**, **root
name**, or **structure hint**.

## Working rules

- Do **not** trust old offsets as current.
- Do use old names to generate modern search hypotheses.
- Prefer **module-local patterns**, **owner/source graph capture**, and
  **live addon comparison** over literal address reuse.
- If a historical clue implies a state exists (for example "is moving" or UI
  error text), treat that as a modern discovery target even if the old path is
  obsolete.

## Highest-value historical leads

### 1. Player-global / entity-manager roots

Source:

- <https://www.taultunleashed.com/rift-bots-hacks/1-5-hotfix-11-1-offsets-released-t81174.html>
  - title: `1.5 Hotfix # 11.1 Offsets Released`
  - post date: 2011-11-05

Historical names listed there:

- `PlayerGlobal`
- `PGlobalXorKy`
- `oEntityMgr`
- `oEntityXor`
- `No_Collision`

Usefulness today:

- suggests an older **player-global root** concept
- suggests an older **entity manager root** concept
- suggests some important globals may have been **xor-masked / decoded before
  use**

Current hypotheses:

- a modern equivalent of `PlayerGlobal` may still exist as a root object that
  leads into owner / source / state structures
- a modern equivalent of `EntityMgr` may still exist as a root used for target,
  nearby-actor, or unit iteration paths
- code paths may decode or transform a global before dereferencing it

Confidence:

- **medium** for structure / naming value
- **low** for literal offsets

### 2. Movement state separate from coordinates

Source:

- <https://www.taultunleashed.com/rift-bots-hacks/rift-offsets-for-version-movement-agro-with-example-codes-t80748.html>
  - title: `Rift Offsets For Version, Movement, Agro WIth Example Codes`
  - post date: 2011-05-03

Historical constants shown:

- `Playerbase = 0x0F48C20`
- movement chain:
  - `RunBase1 = 0x17C`
  - `RunBase2 = 0x270`
  - `RunBase3 = 0x004`
  - `RunBase4 = 0x024`
  - `IsPlayerRunningOffset = 0x175`

Why this matters:

- the post did **not** derive movement from coord deltas alone
- it read a **separate moving/running flag** from a dereferenced subtree below
  player base

Current hypotheses:

- modern Rift may still have a separate **movement-state / controller / animation**
  subtree
- the selected-source / coord object may not be sufficient to explain moving vs
  idle
- movement-state discovery should explicitly test:
  - walk start / stop
  - strafe
  - autorun
  - jump
  - turn in place

Confidence:

- **medium-high** for the structural idea that movement state was separate
- **low** for the old offsets

### 3. Aggro as a coarse player-side flag

Source:

- same TaultUnleashed movement/agro post above

Historical constant shown:

- `IsAgroStatic = 0x0E30A25`

Why this matters:

- the post treated aggro as a simple byte-like state
- this suggests public reversers were using a **coarse player-side combat
  pressure flag**, not a full per-unit threat table

Current hypotheses:

- start modern threat discovery with:
  - in-combat
  - currently under attack
  - hostile pressure / danger state
- only after that, branch into true threat ranking or target-side tables

Confidence:

- **medium** for the idea that a coarse aggro flag may exist
- **low** for the literal static offset

### 4. UI error-message chain for skill-mechanic testing

Source:

- same TaultUnleashed movement/agro post above

Historical UI/error clues:

- `ErrorMsgBase = 0x0E25380`
- separate length chain from `base + 0x0E20CDC`
- example messages:
  - `You are too far away`
  - `You must be facing your target!`

Why this matters:

- these are **mechanic-gating messages**
- they provide a good side channel for:
  - range checks
  - facing checks
  - skill legality
  - target interaction constraints

Current hypotheses:

- modern Rift likely still has a UI/system error buffer or message manager
- forcing known failures may reveal:
  - Unicode strings
  - message-owner objects
  - related state bits for range/facing/ability gating

Recommended test cases:

- too far away
- not facing target
- invalid target
- ability unavailable
- insufficient resource

Confidence:

- **high** that this was historically useful
- **medium** that a similar modern side channel still exists

## Secondary historical evidence

### 5. Old HP / resource clustering

Sources:

- <https://www.elitepvpers.com/forum/rift-hacks-bots-cheats-exploits/1124039-possible-rift-base-address.html>
  - title: `Possible Rift Base Address`
  - post date: 2011-04-15
- <https://www.elitepvpers.com/forum/rift-hacks-bots-cheats-exploits/1068900-thereallifes-rift-bot.html>
  - title: `TheRealLife's Rift Bot`
  - post date: 2011-03-14

Historical clues:

- HP discussed through `rift.exe+E2FA7C`
- offsets mentioned in discussion:
  - `0x130`
  - `0x1A4`
  - `0x1A8`
  - `0x4`
- one commenter said that once health was found, repeated `+0x4` reads exposed
  related values like max health / power / max power

Why this matters:

- supports the idea that resource values historically lived in **local sibling
  groups**
- aligns with the current repo's stat-hub / grouped-resource model

Confidence:

- **medium** as a grouping hint
- **low** for any exact numeric reuse

### 6. Pointer chains alone were probably not enough

Source:

- <https://www.elitepvpers.com/forum/rift-hacks-bots-cheats-exploits/1068900-thereallifes-rift-bot.html>

Historical clue:

- poster discussion suggested Rift botting required more than a simple stable
  pointer; they referenced needing data structures / entity manager style
  understanding

Why this matters:

- supports current `RiftReader` design bias:
  - owner graph
  - selected source component
  - state records
  - stat-hub graph

Confidence:

- **medium**

## Datamining / naming resources

### 7. Telara.db and asset/datamining references

Sources:

- <https://thegharstation.com/gharwiki/index.php/Main_Page>
- <https://thegharstation.com/gharwiki/index.php/Telara.db>

Why these matter:

- they do **not** give memory offsets
- they help label modern discoveries with game-domain names

Useful data categories listed on the Telara.db page include:

- abilities
- effects
- zones
- teleport / spawn locations
- console commands
- Lua documentation

Recommended use:

- when an unknown memory structure appears to hold ability/effect/location data,
  use these resources to generate better labels and test scenarios

Confidence:

- **high** for naming support

### 8. Archive starting point for lost Rift information

Source:

- <https://www.reddit.com/r/Rift/comments/1pzwbd0/links-to-lost-info-for-rift/>

Why it matters:

- useful as a map to archived resources, especially the official forums

Linked archival starting point:

- <https://web.archive.org/web/20220122162308/http://forums.riftgame.com/>

Confidence:

- **high** as an archive pointer

## Current discovery implications for RiftReader

### Most promising modern search targets

1. **UI/system error message manager**
   - can unlock range / facing / ability gating discovery

2. **movement-state subtree**
   - separate from coord and basis matrix
   - likely controller / locomotion / animation related

3. **coarse aggro/combat flag**
   - likely easier to find than a full threat table

4. **entity-manager-like root**
   - useful for target, nearby actor, unit registry, and possibly buff/debuff
     exploration

5. **decoded global roots**
   - watch disassembly for xor or transform steps before dereference

### Suggested experimental ordering

1. trigger UI error messages and diff memory / strings
2. test moving vs idle vs strafe vs jump for byte/enum movement states
3. test coarse aggro/combat transitions
4. branch into target/unit registry work
5. only then attempt deeper threat/pathfinding hypotheses

## Non-goals / cautions

- Do not copy old offsets into current code.
- Do not assume 2011 `rift.exe` layouts apply to 2026 `rift_x64.exe`.
- Treat all old public offsets as **research hints only**.
- Prefer live validation through:
  - `ReaderBridge` export comparison
  - module-local pattern checks
  - session capture artifacts
  - CE trace / disassembly evidence
