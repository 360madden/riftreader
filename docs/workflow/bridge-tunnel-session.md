# RiftReader Bridge Tunnel Session

Version: `riftreader-bridge-tunnel-session-docs-v0.2.1`

## Status

Deprecated for ChatGPT Web/Desktop MCP communication. Prefer the OpenAI Secure
MCP Tunnel path documented in `docs/workflow/riftreader-chatgpt-mcp.md`.
This helper remains only as historical fallback/dev-only Cloudflare bridge
support until the Cloudflare method is fully removed.

## Purpose

Legacy fallback helper that starts the existing RiftReader Local Artifact Bridge and a Cloudflare quick tunnel, then prints the exact URL to paste into ChatGPT.

## Files

```text
tools/riftreader_workflow/bridge_tunnel_session.py
scripts/riftreader-bridge-tunnel-session.cmd
scripts/test_bridge_tunnel_session.py
docs/workflow/bridge-tunnel-session.md
```

## Important fix

This helper does **not** call `scripts\riftreader-local-artifact-bridge.cmd` from inside Python. That path is fragile when the repo path contains spaces, such as:

```text
C:\RIFT MODDING\RiftReader
```

Instead, it directly launches:

```text
tools\riftreader_workflow\local_artifact_bridge.py
```

using `sys.executable` and an argument list.

## Run

```cmd
cd /d "C:\RIFT MODDING\RiftReader"
.\scripts\riftreader-bridge-tunnel-session.cmd
```

## Validation

```cmd
python -m py_compile tools\riftreader_workflow\bridge_tunnel_session.py scripts\test_bridge_tunnel_session.py
python tools\riftreader_workflow\bridge_tunnel_session.py --self-test
python -m unittest scripts.test_bridge_tunnel_session
```

## Safety

No Git mutation, no live RIFT input, no debugger attach, no Cheat Engine, and no command-execution endpoint.

# END_OF_SCRIPT_MARKER
