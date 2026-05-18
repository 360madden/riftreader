<!-- Version: riftreader-transport-probe-doc-v0.1.3 -->
<!-- Total-Character-Count: 3293 -->
<!-- Purpose: Operator docs for chained local and public Local Artifact Bridge transport smoke testing. -->
# RiftReader Transport Probe v0.1.3

Purpose: provide a safe, synthetic transport test for the Local Artifact Bridge without adding HTTP write endpoints, command execution, arbitrary file reads, or live RIFT activity.

## Model

```text
Python helper creates a small payload
Local Artifact Bridge serves it read-only
Python helper verifies bridge reads through localhost or Cloudflare
Python helper can generate the expected ChatGPT-style reply JSON
Python helper validates the reply JSON locally
```

## Files

```text
tools/riftreader_workflow/transport_probe.py
scripts/riftreader-transport-probe.cmd
scripts/test_transport_probe.py
docs/workflow/transport-probe.md
```

The CMD file is a thin launcher only. Python owns all logic.

## Fast chained local smoke

```powershell
.\scripts\riftreader-transport-probe.cmd --json local-smoke
```

This creates a synthetic payload, starts the bridge in-process on `127.0.0.1` using an ephemeral port, verifies the required bridge endpoints, and shuts the bridge down. It does not require cloudflared.

## Public bridge verification through Cloudflare

Start a persistent bridge, then start cloudflared separately. Use the tokenized public base URL without the endpoint suffix:

```powershell
.\scripts\riftreader-transport-probe.cmd --json verify-bridge --base-url https://example.trycloudflare.com/<token>
```

## One-command public bridge roundtrip

Use this to automate the previous two-part manual process:

```powershell
.\scripts\riftreader-transport-probe.cmd --json bridge-roundtrip --base-url https://example.trycloudflare.com/<token>
```

The command verifies the public bridge endpoints, creates `.riftreader-local/transport-probe/replies/chatgpt-reply-<payloadId>.json`, and validates that reply against the local payload contract. The output redacts the tokenized URL.

Alias:

```powershell
.\scripts\riftreader-transport-probe.cmd --json public-roundtrip --base-url https://example.trycloudflare.com/<token>
```

## Manual reply validation

If ChatGPT returns a reply JSON manually, save it to `.riftreader-local/transport-probe/replies/` and run:

```powershell
.\scripts\riftreader-transport-probe.cmd --json verify-reply --reply-file .riftreader-local\transport-probe\replies\reply.json
```

## Safety rules

- No live RIFT input.
- No ProofOnly, movement, CE, or x64dbg.
- No HTTP write endpoint.
- No command execution endpoint.
- No arbitrary file read endpoint.
- Payload files are synthetic and small.
- Payloads are written only under `artifacts/chatgpt-payloads` by default.
- Automated reply files are written only under `.riftreader-local/transport-probe` by default.

## Validation

```powershell
python -m py_compile tools\riftreader_workflow\transport_probe.py scripts\test_transport_probe.py
python -m unittest scripts.test_transport_probe
.\scripts\riftreader-transport-probe.cmd --json self-test
.\scripts\riftreader-transport-probe.cmd --json local-smoke
.\scripts\riftreader-transport-probe.cmd --json bridge-roundtrip --base-url http://127.0.0.1:8765/<token>
git --no-pager diff --check
```

# END_OF_DOCUMENT
