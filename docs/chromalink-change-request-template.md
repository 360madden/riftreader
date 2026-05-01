# ChromaLink Change Request Template

Use this when a RiftReader task needs new or changed ChromaLink data. This keeps
RiftReader sessions from silently editing the ChromaLink provider repo without a
handoff.

```markdown
# ChromaLink Change Request

Date:
Requested by:
RiftReader branch/session:

## Need

- RiftReader use case:
- Existing ChromaLink endpoint/client checked:
- Missing field/behavior:
- Why current ChromaLink data is insufficient:

## Proposed provider contract

- Endpoint or client API:
- Proposed JSON/client field names:
- Expected freshness/latency:
- Read-only vs control:
- Backward compatibility concerns:

## Consumer plan

- RiftReader adapter area:
- Validation command/proof needed in RiftReader:
- Blocked until ChromaLink handoff/commit:

## Boundaries

- Does this request involve heading/facing/yaw/control? If yes, explain the
  proven ChromaLink source before implementation.
- Is raw diagnostic snapshot data being promoted to a stable contract? If yes,
  require ChromaLink schema/docs/tests.
```
