# ChatGPT MCP package-template callable handoff

## Verdict

The first package-loop proof blocker has cleared in actual ChatGPT Web/Desktop:
`get_package_proposal_template` is callable through the `rift-mcp` tool facade.

Final proof is still blocked until the remaining package-loop tools are called
from ChatGPT and their outputs are checked by the local proof recorder.

| Field | Current value |
|---|---|
| Public MCP URL | `https://mcp.360madden.com/mcp` |
| Connection mode | Cloudflare named Tunnel |
| ChatGPT app | `rift-mcp`, Developer Mode, No Authentication |
| Local backend | `127.0.0.1:8770`, PID `48828` |
| Tool count | 12 |
| First package-loop tool | `get_package_proposal_template` passed in ChatGPT at `2026-06-08T03:35:46Z` |

## New actual-client evidence

The operator pasted the ChatGPT result for `get_package_proposal_template`:

| Fact | Value |
|---|---|
| Tool called | `get_package_proposal_template` |
| `ok` | `true` |
| Status | `passed` |
| Template kind | `package-proposal` |
| Storage root | `.riftreader-local/artifact-bridge-inbox` |
| Safety | draft-only, requires human review, no repo target writes, no command execution, no Git mutation, no RIFT input, no CE/x64dbg |

Ignored evidence was updated locally:

| Artifact | Path |
|---|---|
| Operator observation | `.riftreader-local\riftreader-chatgpt-mcp\operator-observations\20260608-033546Z-get-package-proposal-template\observation.json` |
| Updated proof input | `.riftreader-local\riftreader-chatgpt-mcp\proof-input-templates\20260607-232355Z\proof-input.json` |

## Refreshed local validation

| Command | Result |
|---|---|
| `python tools\riftreader_workflow\chatgpt_trial_recorder.py --check-latest-template --json` | Blocked as expected, but `template-fetch-not-confirmed` and `chatgpt-tool-facade-unavailable:*` are no longer current blockers. |
| `scripts\riftreader-mcp-domain-diagnostics.cmd --public-mcp-host mcp.360madden.com --json` | Passed at `2026-06-08T03:39:57Z`; public smoke HTTP 200, backend PID `48828`, Caddy remains deprecated and is not the active route. |
| `python tools\riftreader_workflow\riftreader_chatgpt_mcp.py --proposal-transport-smoke --json` | Passed locally; package-loop transport works on loopback and unapproved apply blocks with `APPLY_APPROVAL_MISSING`. |

Remaining proof-input blockers after ingesting the first ChatGPT output:

```text
submit-package-proposal-not-confirmed
create-package-draft-not-confirmed
review-latest-package-draft-not-confirmed
review-latest-package-draft-read-only-not-confirmed
dry-run-not-confirmed
dry-run-diff-preview-not-confirmed
dry-run-diff-preview-package-intake-not-confirmed
dry-run-diff-preview-bounded-bytes-not-confirmed
dry-run-diff-preview-text-length-invalid:0
draft-id-missing
apply-latest-package-draft-without-approval-not-blocked
apply-latest-package-draft-without-approval-missing-approval-blocker
```

## Next actual ChatGPT action

In the same `rift-mcp` ChatGPT chat, call `submit_package_proposal` with this
minimal proposal:

```json
{
  "proposal": {
    "schemaVersion": 1,
    "kind": "package-proposal",
    "title": "ChatGPT MCP proof smoke package",
    "body": "Harmless draft-only proof package to verify ChatGPT can submit package proposals through rift-mcp.",
    "payload": {
      "packageName": "ChatGPT MCP proof smoke package",
      "files": [
        {
          "target": "docs/workflow/riftreader-chatgpt-mcp-desktop-proof-smoke.md",
          "content": "# ChatGPT MCP proof smoke\n\nThis file is proposed by ChatGPT only for dry-run proof of the RiftReader MCP package workflow.\n",
          "encoding": "utf-8"
        }
      ],
      "checks": []
    },
    "source": {
      "tool": "Desktop ChatGPT",
      "context": "operator-approved MCP package-loop proof"
    },
    "metadata": {
      "requiresHumanReview": true,
      "draftOnly": true
    }
  }
}
```

Then paste the `submit_package_proposal` output back into Codex. The key field
needed for the next step is `inboxId`.

## Boundary

No repo target files were applied, no Git push occurred, no RIFT input was sent,
and no CE/x64dbg/provider write/proof promotion boundary was crossed.
