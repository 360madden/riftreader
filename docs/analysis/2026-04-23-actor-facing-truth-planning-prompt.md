# 2026-04-23 actor-facing truth planning prompt

> planning / delegation packet only. For the living current-session truth and
> rebuild order, see:
>
> - `C:\RIFT MODDING\RiftReader\docs\recovery\current-truth.md`
> - `C:\RIFT MODDING\RiftReader\docs\recovery\rebuild-runbook.md`

## Verdict

Use a **hybrid two-lane plan**:

- **Lane A = behavior-backed same-session live truth**
- **Lane B = provenance / source-chain strengthening**

That gives the highest chance of success on the current session while keeping
false-promotion risk low.

## Strategy options

| Rank | Strategy | Success probability | Speed | Stability | False-promotion risk | Recommendation |
|---:|---|---|---|---|---|---|
| 1 | hybrid two-lane approach | highest | high | highest | lowest | **best default** |
| 2 | behavior-backed live truth lane only | high | highest | high | low | good when speed matters more than deeper lineage |
| 3 | provenance / source-chain-first lane | medium | lowest | medium | highest | use only for deeper reverse-engineering, not as the default truth path |

Why this ranking:

- the current live lead is already working at `0x12CC0FA0F70 @ +0xD4`
- same-session reversible validation is already working through the current
  discovery conductor
- provenance is currently restored and confirmed, but it should strengthen
  truth rather than block it
- movement coord truth must remain separate from actor-facing truth unless
  separately re-proven

## Best prompt

```text
You are working in C:\RIFT MODDING\RiftReader.

Goal:
Produce the best execution plan for elevating actor-facing to durable current-session truth with the highest chance of success and the lowest chance of false promotion.

Current known state:
- Current live actor-facing truth is the behavior-backed lead at 0x12CC0FA0F70 @ +0xD4.
- Live truth is currently working through:
  - scripts\refresh-actor-facing-discovery.ps1
  - scripts\capture-actor-orientation.ps1
  - --read-player-orientation
- The actor-facing provenance lane is currently restored and confirmed.
- Source-chain refresh now prefers a fresh rebuild path:
  - Recovery.Mode = rebuild-from-suggested-source-chain-pattern
- Same-session reuse of a previous source-chain artifact is still allowed only as a last-resort fallback if the fresh pattern-scan rebuild path fails.
- Movement coord truth and actor-facing truth must remain separate unless separately re-proven.

Task:
Organize the best plan for elevating facing to truth. Compare the available strategies, decide priorities, and choose the best course of action for maximum chance of success.

Required output:
1. Start with a clear verdict on the best strategy.
2. List the realistic strategy options, including:
   - behavior-backed live truth lane
   - provenance/source-chain-first lane
   - hybrid two-lane approach
3. Rank the options by probability of success, speed, stability, and risk of false truth promotion.
4. Choose one recommended approach and explain why it is best.
5. Produce a decision-complete implementation plan that covers:
   - goal and success criteria
   - what counts as “facing truth”
   - promotion gates
   - provenance requirements
   - stale-artifact rejection rules
   - fallback and failure behavior
   - validation steps
   - acceptance criteria
6. Keep movement coord truth explicitly out of scope unless separately required.
7. Do not automatically treat historical source-chain results as current truth.
8. Prefer the smallest set of changes that improves truth quality without regressing the current working live lead.

Planning constraints:
- Optimize for success on the current live session first.
- Prefer same-session validation over historical evidence.
- Preserve the current working behavior-backed lead unless a stronger same-session truth path clearly beats it.
- Treat provenance failures as non-blocking if live facing truth remains confirmed.
- Distinguish clearly between:
  - live truth
  - provenance
  - historical evidence
  - movement coord truth

Deliverable style:
- Use tables for options, priorities, tradeoffs, and recommended sequence.
- Be explicit about priorities.
- Be opinionated: choose the best path instead of only listing possibilities.
- Make the plan handoff-ready so another engineer or agent can implement it without making product decisions.
```

## Short prompt

```text
Plan the best path for elevating actor-facing to durable current-session truth in C:\RIFT MODDING\RiftReader.

Current state:
- Current live truth is the behavior-backed lead at 0x12CC0FA0F70 @ +0xD4.
- Live truth works through refresh-actor-facing-discovery.ps1, capture-actor-orientation.ps1, and --read-player-orientation.
- Provenance is currently confirmed.
- Source-chain refresh now prefers fresh rebuild-from-suggested-source-chain-pattern before falling back to reuse-previous-source-chain.

Your task:
- compare the realistic strategies for making facing “truth”
- rank them by success probability, speed, stability, and false-promotion risk
- choose the best strategy
- produce a decision-complete implementation plan

Requirements:
- separate live truth from provenance and historical evidence
- do not promote historical source-chain truth automatically
- preserve the current live lead unless a stronger same-session truth path beats it
- treat provenance failures as non-blocking if live truth stays confirmed
- keep movement coord truth out of scope

Output:
- verdict first
- options table
- chosen strategy with reasons
- implementation plan
- test/validation plan
- assumptions/defaults
```

## Default recommendation to preserve

| Decision | Best default |
|---|---|
| Primary truth source | behavior-backed lead |
| Promotion basis | same-session reversible validation |
| Provenance role | secondary / confirmatory |
| Historical evidence | reference only |
| Failure default | retain current confirmed lead instead of forcing promotion |
| Success definition | capture + reader + current lead all agree on the same current-session source/basis |

## Why this prompt is safer

| Improvement | Why it matters |
|---|---|
| Anchored to current repo truth | prevents drift back to stale `0x12CAF6F7080` or older April 22 source-chain truth |
| Forces option comparison | produces an actual strategy choice instead of a vague brainstorm |
| Separates truth vs provenance | avoids blocking a working lead on deeper reverse-engineering work |
| Includes promotion gates and stale rejection | reduces false truth promotion |
| Excludes movement coord truth | prevents mixing facing planning with coord-proof work |
| Requires a recommendation | maximizes handoff usefulness |
