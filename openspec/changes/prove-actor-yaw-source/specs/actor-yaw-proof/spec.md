## ADDED Requirements

### Requirement: Actor-yaw proof workflow emits a run summary
The system SHALL persist a single summary artifact for each actor-yaw proof run that records preflight state, player/coord baseline, selected candidate, proof artifact paths, and final workflow status.

#### Scenario: Successful proof run records the selected candidate
- **WHEN** the actor-yaw workflow finds at least one usable candidate and completes its configured steps
- **THEN** it SHALL write a summary artifact that identifies the selected candidate and the artifact files used during that run

#### Scenario: Candidate-missing run still records the failure
- **WHEN** the actor-yaw workflow does not find a usable candidate
- **THEN** it SHALL still write a summary artifact with a non-success status and a reason that explains why no candidate qualified

### Requirement: Actor-yaw proof uses turn-based evidence gating
The system SHALL classify a candidate as promotion-eligible only when the candidate responds to turn stimulus, player coordinate drift stays within the configured limit, and the workflow records the proof measurements used for that decision.

#### Scenario: Truth-like candidate passes the proof gate
- **WHEN** a candidate yaw changes beyond the configured threshold during turn stimulus while player coordinate drift stays within the configured limit
- **THEN** the workflow SHALL mark that candidate as truth-like and include the measured proof data in the summary artifact

#### Scenario: Non-responsive or drift-heavy candidate fails the proof gate
- **WHEN** a candidate does not respond to turn stimulus or coordinate drift exceeds the configured limit
- **THEN** the workflow SHALL not mark that candidate as truth-like

### Requirement: Degraded proof states are explicit and blocking
The system SHALL record whether candidate selection or proof relied on cached fallback, stale inputs, skipped stimulus, or skipped debug confirmation, and SHALL block truth promotion when any blocking degraded state is present.

#### Scenario: Cached fallback blocks truth promotion
- **WHEN** any selector-owner, source-chain, or related proof stage falls back to cached or stale artifacts
- **THEN** the summary artifact SHALL record the degraded source and SHALL mark truth promotion as blocked

#### Scenario: Debug-blocked confirmation is visible
- **WHEN** the live client is already under a debugger and bounded debug confirmation is skipped
- **THEN** the summary artifact SHALL record the debug-blocked state and SHALL not treat the run as fully confirmed

### Requirement: Repo truth promotion is gated by promotion-ready evidence
The system SHALL promote an actor-yaw source to repo truth only from a promotion-ready run and SHALL update repo truth documentation with the authoritative source description, freshness date, and supporting artifact references.

#### Scenario: Promotion-ready run updates repo truth
- **WHEN** a run ends with a selected truth-like candidate, no blocking degraded states, and the required supporting artifacts
- **THEN** the repo truth documentation SHALL identify that source as the current authoritative actor-yaw source and reference the proof artifacts that justified the promotion

#### Scenario: Non-promotable run preserves stale or provisional truth
- **WHEN** a run does not produce a promotion-ready result
- **THEN** the repo truth documentation SHALL continue to mark actor orientation as stale or provisional instead of promoting the source
