#!/usr/bin/env python3
# Version: riftreader-mcp-domain-preflight-v0.1.1
# Purpose: No-secrets domain-only readiness check for the 360madden Cloudflare MCP lane.

from __future__ import annotations

import argparse
import json
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.riftreader_mcp.config import default_repo_root, runtime_root


VERSION = "riftreader-mcp-domain-preflight-v0.1.1"
DEFAULT_DOMAIN = "360madden.com"
DEFAULT_HOSTNAME = "mcp.360madden.com"
DNS_SERVER = "1.1.1.1"


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_nslookup(args: list[str]) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ["nslookup", *args, DNS_SERVER],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=20,
            check=False,
        )
        return {
            "args": ["nslookup", *args, DNS_SERVER],
            "exitCode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "timedOut": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "args": ["nslookup", *args, DNS_SERVER],
            "exitCode": None,
            "stdout": exc.stdout if isinstance(exc.stdout, str) else "",
            "stderr": exc.stderr if isinstance(exc.stderr, str) else "",
            "timedOut": True,
        }


def ns_records_detected(output: str) -> bool:
    lowered = output.lower()
    return "nameserver" in lowered and "can't find" not in lowered and "non-existent domain" not in lowered


def cloudflare_nameservers_detected(output: str) -> bool:
    return "cloudflare.com" in output.lower()


def hostname_resolves(hostname: str) -> dict[str, Any]:
    try:
        values = sorted({item[4][0] for item in socket.getaddrinfo(hostname, 443)})
        return {"ok": bool(values), "addresses": values, "error": None}
    except OSError as exc:
        return {"ok": False, "addresses": [], "error": f"{type(exc).__name__}: {exc}"}


def build_payload(repo: Path, *, domain: str, hostname: str) -> dict[str, Any]:
    ns = run_nslookup(["-type=NS", domain])
    host_lookup = run_nslookup([hostname])
    host_socket = hostname_resolves(hostname)

    domain_ns_ok = ns_records_detected(ns["stdout"])
    cloudflare_ns_ok = cloudflare_nameservers_detected(ns["stdout"])
    host_dns_ok = host_socket["ok"]
    status = "passed" if domain_ns_ok and cloudflare_ns_ok and host_dns_ok else "blocked"

    blockers: list[str] = []
    if not domain_ns_ok:
        blockers.append("Domain nameservers are not visible from public DNS yet.")
    elif not cloudflare_ns_ok:
        blockers.append("Domain resolves, but public nameservers do not look like Cloudflare nameservers.")
    if not host_dns_ok:
        blockers.append(f"{hostname} does not resolve yet. Create the Cloudflare Tunnel public hostname/DNS route.")

    next_actions = [
        "Confirm 360madden.com is an active zone in Cloudflare.",
        "If Cloudflare Registrar owns the domain, do not add home-IP A records; use Zero Trust Tunnel public hostname routing.",
        "Create a Cloudflare Zero Trust Tunnel and install/run the cloudflared connector on this Windows PC.",
        "Add public hostname mcp.360madden.com with service http://127.0.0.1:8765.",
        "Run scripts\\start_mcp_local_background.cmd and keep it running while testing the tunnel.",
    ]

    return {
        "version": VERSION,
        "generatedAtUtc": utc_iso(),
        "repo": str(repo),
        "domain": domain,
        "hostname": hostname,
        "dnsServer": DNS_SERVER,
        "status": status,
        "domainNameserversDetected": domain_ns_ok,
        "cloudflareNameserversDetected": cloudflare_ns_ok,
        "hostnameResolves": host_dns_ok,
        "hostnameAddresses": host_socket["addresses"],
        "blockers": blockers,
        "nextActions": next_actions,
        "checks": {
            "domainNsLookup": ns,
            "hostnameLookup": host_lookup,
            "hostnameSocketResolve": host_socket,
        },
    }


def write_summary(repo: Path, payload: dict[str, Any]) -> tuple[Path, Path]:
    out_dir = runtime_root(repo) / "domain-preflight" / utc_stamp()
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = out_dir / "summary.json"
    markdown = out_dir / "summary.md"
    summary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    markdown.write_text(
        "# RiftReader MCP Domain Preflight\n\n"
        f"- Status: `{payload['status']}`\n"
        f"- Domain: `{payload['domain']}`\n"
        f"- Hostname: `{payload['hostname']}`\n"
        f"- Domain NS detected: `{payload['domainNameserversDetected']}`\n"
        f"- Cloudflare NS detected: `{payload['cloudflareNameserversDetected']}`\n"
        f"- Hostname resolves: `{payload['hostnameResolves']}`\n\n"
        "## Blockers\n\n"
        + "\n".join(f"- {item}" for item in payload["blockers"])
        + "\n",
        encoding="utf-8",
    )
    return summary, markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check Cloudflare domain-only readiness for RiftReader MCP.")
    parser.add_argument("--repo", default=str(default_repo_root()))
    parser.add_argument("--domain", default=DEFAULT_DOMAIN)
    parser.add_argument("--hostname", default=DEFAULT_HOSTNAME)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    payload = build_payload(repo, domain=args.domain, hostname=args.hostname)
    if args.write:
        summary, markdown = write_summary(repo, payload)
        payload["summaryJson"] = str(summary)
        payload["summaryMarkdown"] = str(markdown)

    print(json.dumps(payload, indent=2))
    print("PASS" if payload["status"] == "passed" else "BLOCKED_DOMAIN_SETUP")
    print("END_RIFTREADER_MCP_DOMAIN_PREFLIGHT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
