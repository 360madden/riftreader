#!/usr/bin/env python3
"""Localhost-only status dashboard for RiftReader ChatGPT Web/Desktop MCP."""

from __future__ import annotations

import argparse
import html
import json
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

try:
    from .chatgpt_trial_recorder import (
        ACTUAL_CLIENT_PROOF_ROOT,
        PROOF_INPUT_TEMPLATE_ROOT,
        EXPECTED_CHATGPT_MCP_TOOL_NAMES,
        EXPECTED_DOMAIN_READ_ONLY_TOOL_NAMES,
    )
    from .common import find_repo_root, repo_rel as rel, safety_flags, utc_iso
    from .mcp_domain_diagnostics import (
        DEFAULT_PUBLIC_HOST,
        check_dns,
        check_windows_port_owner,
        public_mcp_url,
        smoke_public_initialize,
        _socket_connect,
    )
    from .riftreader_chatgpt_mcp import DEFAULT_HOST, DEFAULT_PORT, PUBLIC_READ_ONLY_TOOL_ORDER, SERVER_NAME
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from riftreader_workflow.chatgpt_trial_recorder import (
        ACTUAL_CLIENT_PROOF_ROOT,
        PROOF_INPUT_TEMPLATE_ROOT,
        EXPECTED_CHATGPT_MCP_TOOL_NAMES,
        EXPECTED_DOMAIN_READ_ONLY_TOOL_NAMES,
    )
    from riftreader_workflow.common import find_repo_root, repo_rel as rel, safety_flags, utc_iso
    from riftreader_workflow.mcp_domain_diagnostics import (
        DEFAULT_PUBLIC_HOST,
        check_dns,
        check_windows_port_owner,
        public_mcp_url,
        smoke_public_initialize,
        _socket_connect,
    )
    from riftreader_workflow.riftreader_chatgpt_mcp import DEFAULT_HOST, DEFAULT_PORT, PUBLIC_READ_ONLY_TOOL_ORDER, SERVER_NAME


SCHEMA_VERSION = 1
DEFAULT_DASHBOARD_HOST = "127.0.0.1"
DEFAULT_DASHBOARD_PORT = 8788
STATUS_TTL_SECONDS = 20.0


def redact_repo_root(value: Any, repo_root: Path) -> Any:
    root = str(repo_root.resolve())
    if isinstance(value, str):
        return value.replace(root, ".").replace(root.replace("\\", "/"), ".")
    if isinstance(value, list):
        return [redact_repo_root(item, repo_root) for item in value]
    if isinstance(value, dict):
        return {str(key): redact_repo_root(item, repo_root) for key, item in value.items()}
    return value


def latest_file(root: Path, pattern: str) -> Path | None:
    if not root.is_dir():
        return None
    candidates = [path for path in root.glob(pattern) if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, str(path)))


def load_json_file(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except Exception:  # noqa: BLE001 - dashboard should stay up.
        return None


def command_json(repo_root: Path, args: list[str], timeout_seconds: float = 8.0) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            args,
            cwd=repo_root,
            check=False,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
            timeout=timeout_seconds,
        )
        payload: dict[str, Any]
        try:
            parsed = json.loads(completed.stdout)
            payload = parsed if isinstance(parsed, dict) else {"value": parsed}
        except json.JSONDecodeError:
            payload = {"stdoutPreview": completed.stdout[-2000:]}
        payload["_command"] = {"args": args, "exitCode": completed.returncode, "ok": completed.returncode == 0}
        return payload
    except Exception as exc:  # noqa: BLE001
        return {"status": "failed", "ok": False, "_command": {"args": args, "error": f"{type(exc).__name__}:{exc}"}}


def recent_audit_events(repo_root: Path, limit: int = 12) -> list[dict[str, Any]]:
    audit_root = repo_root / ".riftreader-local" / "riftreader-chatgpt-mcp" / "audit"
    if not audit_root.is_dir():
        return []
    events: list[dict[str, Any]] = []
    for path in sorted(audit_root.rglob("*.json"), key=lambda p: p.stat().st_mtime_ns, reverse=True)[:limit]:
        payload = load_json_file(path) or {}
        events.append(
            {
                "path": rel(repo_root, path),
                "mtimeUtc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(path.stat().st_mtime)),
                "toolName": payload.get("toolName") or payload.get("tool") or payload.get("name"),
                "status": payload.get("status"),
                "ok": payload.get("ok"),
            }
        )
    return events


def collect_status(repo_root: Path, public_host: str, *, include_public_smoke: bool = True) -> dict[str, Any]:
    public_url = public_mcp_url(public_host)
    backend_connect = _socket_connect(DEFAULT_HOST, DEFAULT_PORT, 1.0)
    dns = check_dns(public_host)
    tcp443 = _socket_connect(public_host, 443, 2.0)
    tcp443_owner = check_windows_port_owner(443)
    backend_owner = check_windows_port_owner(DEFAULT_PORT)
    public_smoke = smoke_public_initialize(public_url, timeout_seconds=4.0) if include_public_smoke else {
        "status": "skipped",
        "ok": None,
        "blockers": [],
    }
    final_status = command_json(repo_root, ["cmd", "/c", "scripts\\riftreader-mcp-final.cmd", "--status", "--compact-json"], 10.0)
    mission = command_json(repo_root, ["cmd", "/c", "scripts\\riftreader-mcp-mission-control.cmd", "--json"], 12.0)
    latest_template_path = latest_file(repo_root / PROOF_INPUT_TEMPLATE_ROOT, "*/proof-input.json")
    latest_proof_path = latest_file(repo_root / ACTUAL_CLIENT_PROOF_ROOT, "*/proof.json")
    latest_template = load_json_file(latest_template_path)
    latest_proof = load_json_file(latest_proof_path)
    status = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-dashboard-status",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if backend_connect.get("ok") and dns.get("ok") and tcp443.get("ok") and public_smoke.get("ok") else "blocked",
        "ok": bool(backend_connect.get("ok") and dns.get("ok") and tcp443.get("ok") and public_smoke.get("ok")),
        "appName": "rift-mcp",
        "chatGptSetup": {
            "surface": "ChatGPT Web/Desktop Developer Mode",
            "notCodex": True,
            "serverUrl": public_url,
            "authentication": "No Authentication",
        },
        "backend": {"service": SERVER_NAME, "host": DEFAULT_HOST, "port": DEFAULT_PORT, "connect": backend_connect, "owner": backend_owner},
        "domain": {"publicHost": public_host, "publicMcpUrl": public_url, "dns": dns, "tcp443": tcp443, "tcp443Owner": tcp443_owner, "publicSmoke": public_smoke},
        "toolSurface": {
            "phase0ReadOnlyTools": list(PUBLIC_READ_ONLY_TOOL_ORDER),
            "phase0ExpectedProofTools": list(EXPECTED_DOMAIN_READ_ONLY_TOOL_NAMES),
            "fullFinalProofTools": list(EXPECTED_CHATGPT_MCP_TOOL_NAMES),
            "fullFinalProofToolCount": len(EXPECTED_CHATGPT_MCP_TOOL_NAMES),
        },
        "missionControl": {
            "status": mission.get("status"),
            "ok": mission.get("ok"),
            "recommendedNextAction": mission.get("recommendedNextAction") or mission.get("operatorNextAction"),
            "blockers": (mission.get("blockers") or [])[:10],
        },
        "finalReadiness": {
            "status": final_status.get("status"),
            "ok": final_status.get("ok"),
            "recommendedNextAction": final_status.get("recommendedNextAction"),
            "blockers": (final_status.get("blockers") or [])[:10],
        },
        "proof": {
            "latestTemplatePath": rel(repo_root, latest_template_path),
            "latestTemplateKind": latest_template.get("kind") if latest_template else None,
            "latestTemplateProofMode": latest_template.get("proofMode") if latest_template else None,
            "latestProofPath": rel(repo_root, latest_proof_path),
            "latestProofStatus": latest_proof.get("status") if latest_proof else None,
            "latestProofMode": ((latest_proof.get("proof") or {}).get("proofMode") if latest_proof else None),
            "latestProofGeneratedAtUtc": latest_proof.get("generatedAtUtc") if latest_proof else None,
        },
        "safety": {
            **safety_flags(),
            "dashboardHost": DEFAULT_DASHBOARD_HOST,
            "localhostOnly": True,
            "statusOnly": True,
            "startStopControls": False,
            "shellEndpoint": False,
            "arbitraryFilesystemEndpoint": False,
            "gitMutationEndpoint": False,
            "riftInputEndpoint": False,
            "cheatEngineEndpoint": False,
            "x64dbgEndpoint": False,
        },
        "recentAuditEvents": recent_audit_events(repo_root),
    }
    return redact_repo_root(status, repo_root)


def render_html() -> bytes:
    return HTML.encode("utf-8")


HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>RiftReader MCP Dashboard</title>
  <style>
    :root { color-scheme: dark; font-family: Segoe UI, system-ui, sans-serif; background:#0c1117; color:#e6edf3; }
    body { margin: 0; padding: 24px; }
    h1 { margin: 0 0 4px; }
    .muted { color:#9aa7b5; }
    .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(310px, 1fr)); gap:16px; margin-top:18px; }
    .card { background:#151b23; border:1px solid #30363d; border-radius:12px; padding:16px; box-shadow: 0 2px 12px #0008; }
    .status { display:inline-block; padding:3px 9px; border-radius:999px; font-weight:700; }
    .green { background:#1f6f43; color:#d2ffe3; }
    .yellow { background:#8a6d1d; color:#fff4c2; }
    .red { background:#842029; color:#ffd6dc; }
    .gray { background:#3b424b; color:#d4dbe3; }
    code { background:#0d1117; padding:2px 5px; border-radius:5px; }
    ul { padding-left: 20px; }
    pre { white-space:pre-wrap; overflow:auto; max-height:240px; background:#0d1117; padding:10px; border-radius:8px; }
  </style>
</head>
<body>
  <h1>RiftReader ChatGPT Web/Desktop MCP</h1>
  <div class="muted">Local status dashboard only. No start/stop, shell, Git, RIFT input, CE, or x64dbg controls.</div>
  <div id="updated" class="muted"></div>
  <div id="cards" class="grid"></div>
<script>
function cls(ok, status) {
  if (ok === true || status === "passed" || status === "ready") return "green";
  if (status === "skipped" || status === "disabled") return "gray";
  if (status === "blocked" || status === "failed") return "red";
  return "yellow";
}
function pill(label, ok, status) { return `<span class="status ${cls(ok, status)}">${label}: ${status ?? ok}</span>`; }
function esc(v) { return String(v ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;"}[c])); }
function list(items) { return `<ul>${(items||[]).map(x=>`<li><code>${esc(x)}</code></li>`).join("") || "<li class='muted'>none</li>"}</ul>`; }
function card(title, body) { return `<section class="card"><h2>${esc(title)}</h2>${body}</section>`; }
async function refresh() {
  const r = await fetch("/status.json", {cache:"no-store"});
  const s = await r.json();
  document.getElementById("updated").textContent = `Updated ${s.generatedAtUtc}`;
  const cards = [];
  cards.push(card("MCP backend", `${pill("backend", s.backend.connect.ok, s.backend.connect.ok ? "running" : "stopped")}<p><code>${s.backend.host}:${s.backend.port}</code></p><pre>${esc(JSON.stringify(s.backend.owner.processes || [], null, 2))}</pre>`));
  cards.push(card("Public domain", `${pill("DNS", s.domain.dns.ok, s.domain.dns.status)} ${pill("TCP 443", s.domain.tcp443.ok, s.domain.tcp443.ok ? "passed" : "blocked")} ${pill("/mcp smoke", s.domain.publicSmoke.ok, s.domain.publicSmoke.status)}<p><code>${esc(s.domain.publicMcpUrl)}</code></p>${list(s.domain.publicSmoke.blockers)}`));
  cards.push(card("ChatGPT setup", `<p>App: <code>${esc(s.appName)}</code></p><p>Server URL: <code>${esc(s.chatGptSetup.serverUrl)}</code></p><p>Auth: <code>${esc(s.chatGptSetup.authentication)}</code></p><p class="muted">Surface: ${esc(s.chatGptSetup.surface)}; not Codex.</p>`));
  cards.push(card("Tool surface", `<h3>Phase 0 read-only</h3>${list(s.toolSurface.phase0ReadOnlyTools)}<h3>Full 12-tool final proof</h3><p>${s.toolSurface.fullFinalProofToolCount} tools retained.</p>`));
  cards.push(card("Mission Control", `${pill("mission", s.missionControl.ok, s.missionControl.status)}<p>Next: <code>${esc(JSON.stringify(s.missionControl.recommendedNextAction || {}))}</code></p>${list(s.missionControl.blockers)}`));
  cards.push(card("Proof", `<p>Latest template: <code>${esc(s.proof.latestTemplatePath)}</code></p><p>Template mode: <code>${esc(s.proof.latestTemplateProofMode)}</code></p><p>Latest proof: <code>${esc(s.proof.latestProofPath)}</code></p><p>Proof status: <code>${esc(s.proof.latestProofStatus)}</code></p>`));
  cards.push(card("Safety", `${pill("dashboard", true, "status-only")} ${pill("controls", null, "disabled")}<ul><li>No shell endpoint</li><li>No arbitrary filesystem endpoint</li><li>No Git mutation endpoint</li><li>No RIFT input</li><li>No CE/x64dbg</li></ul>`));
  cards.push(card("Recent audit/events", `<pre>${esc(JSON.stringify(s.recentAuditEvents, null, 2))}</pre>`));
  document.getElementById("cards").innerHTML = cards.join("");
}
refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>
"""


class DashboardServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler: type[BaseHTTPRequestHandler], repo_root: Path, public_host: str, include_public_smoke: bool) -> None:
        super().__init__(server_address, handler)
        self.repo_root = repo_root
        self.public_host = public_host
        self.include_public_smoke = include_public_smoke
        self._cache_lock = threading.Lock()
        self._cache_at = 0.0
        self._cache: dict[str, Any] | None = None

    def status(self) -> dict[str, Any]:
        with self._cache_lock:
            now = time.monotonic()
            if self._cache is None or now - self._cache_at > STATUS_TTL_SECONDS:
                self._cache = collect_status(self.repo_root, self.public_host, include_public_smoke=self.include_public_smoke)
                self._cache_at = now
            return self._cache


class Handler(BaseHTTPRequestHandler):
    server: DashboardServer

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/index.html"):
            body = render_html()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/status.json":
            body = json.dumps(self.server.status(), indent=2, sort_keys=True).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)


def self_test(repo_root: Path, public_host: str) -> dict[str, Any]:
    status = collect_status(repo_root, public_host, include_public_smoke=False)
    text = json.dumps(status, sort_keys=True)
    blockers: list[str] = []
    root_text = str(repo_root.resolve())
    if root_text in text or root_text.replace("\\", "\\\\") in text or root_text.replace("\\", "/") in text:
        blockers.append("absolute-repo-root-exposed")
    if "sk-" in text or "Bearer " in text:
        blockers.append("secret-like-token-exposed")
    if status.get("safety", {}).get("localhostOnly") is not True:
        blockers.append("localhost-only-flag-missing")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "riftreader-chatgpt-mcp-dashboard-self-test",
        "generatedAtUtc": utc_iso(),
        "status": "passed" if not blockers else "failed",
        "ok": not blockers,
        "blockers": blockers,
        "statusPreview": status,
        "safety": {**safety_flags(), "serverStarted": False, "statusOnly": True},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Localhost-only RiftReader ChatGPT MCP status dashboard.")
    parser.add_argument("--repo-root", default=None)
    parser.add_argument("--host", default=DEFAULT_DASHBOARD_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_DASHBOARD_PORT)
    parser.add_argument("--public-mcp-host", default=DEFAULT_PUBLIC_HOST)
    parser.add_argument("--no-public-smoke", action="store_true", help="Do not run public /mcp smoke from dashboard refreshes.")
    parser.add_argument("--once-json", action="store_true", help="Print one redacted status JSON payload and exit.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    if args.host != DEFAULT_DASHBOARD_HOST:
        payload = {"status": "failed", "ok": False, "blockers": ["dashboard-host-must-be-127.0.0.1"], "host": args.host}
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 1
    if args.self_test:
        payload = self_test(repo_root, args.public_mcp_host)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if payload.get("ok") else 1
    if args.once_json:
        payload = collect_status(repo_root, args.public_mcp_host, include_public_smoke=not args.no_public_smoke)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if payload.get("ok") else 2
    httpd = DashboardServer((args.host, args.port), Handler, repo_root, args.public_mcp_host, not args.no_public_smoke)
    print(f"RiftReader MCP dashboard: http://{args.host}:{args.port}/")
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
