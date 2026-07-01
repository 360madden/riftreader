#!/usr/bin/env python3
# Version: riftreader-bridge-tunnel-session-v0.2.1
# Total-Character-Count: 23265
# Purpose: Start the RiftReader Local Artifact Bridge and Cloudflare quick tunnel using Python core logic with a thin CMD wrapper. This version avoids nested cmd.exe quoting by launching local_artifact_bridge.py directly with sys.executable, validates path-with-spaces subprocess behavior in --self-test, detects the public trycloudflare URL, copies the final ChatGPT URL to clipboard, writes logs/artifacts, and cleans up safely.

from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import secrets
import signal
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


VERSION = "riftreader-bridge-tunnel-session-v0.2.1"
DEFAULT_REPO_ROOT = Path(r"C:\RIFT MODDING\RiftReader")
DEFAULT_PAYLOAD_ROOT = Path(r"artifacts\chatgpt-payloads")
DEFAULT_PORT = 8765
DEFAULT_MAX_RESPONSE_MB = 25
DEFAULT_MAX_INBOX_MB = 1
DEFAULT_WAIT_SECONDS = 90
TRYCLOUDFLARE_RE = re.compile(r"https://[A-Za-z0-9-]+\.trycloudflare\.com")


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    BG_GREEN = "\033[42m"


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def enable_windows_ansi() -> None:
    if os.name != "nt":
        return
    try:
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def supports_color(no_color: bool) -> bool:
    if no_color or os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


class Console:
    def __init__(self, no_color: bool = False) -> None:
        enable_windows_ansi()
        self.use_color = supports_color(no_color)

    def c(self, text: str, color: str = "") -> str:
        if not self.use_color or not color:
            return text
        return f"{color}{text}{Colors.RESET}"

    def line(self, text: str = "", color: str = "") -> None:
        print(self.c(text, color), flush=True)

    def title(self, text: str) -> None:
        self.line()
        self.line("=" * 72, Colors.CYAN)
        self.line(f"  {text}", Colors.BOLD + Colors.CYAN)
        self.line("=" * 72, Colors.CYAN)

    def step(self, text: str) -> None:
        self.line()
        self.line(f"[..] {text}", Colors.YELLOW)

    def ok(self, text: str) -> None:
        self.line(f"[OK] {text}", Colors.GREEN)

    def warn(self, text: str) -> None:
        self.line(f"[WARN] {text}", Colors.YELLOW)

    def fail(self, text: str) -> None:
        self.line(f"[FAIL] {text}", Colors.RED)

    def info(self, label: str, value: str) -> None:
        print(self.c(f"{label + ':':<24}", Colors.DIM) + value, flush=True)

    def copy_block(self, url: str) -> None:
        self.line()
        self.line("#" * 72, Colors.GREEN)
        self.line("#" + " " * 70 + "#", Colors.GREEN)
        self.line("#" + "COPY THIS TO CHATGPT".center(70) + "#", Colors.GREEN)
        self.line("#" + " " * 70 + "#", Colors.GREEN)
        self.line("#" * 72, Colors.GREEN)
        self.line()
        if self.use_color:
            print(f"{Colors.BG_GREEN}{Colors.WHITE}{url}{Colors.RESET}", flush=True)
        else:
            print(url, flush=True)
        self.line()
        self.line("#" * 72, Colors.GREEN)
        self.line()


@dataclass
class Paths:
    repo_root: Path
    payload_root: Path
    log_dir: Path
    bridge_py: Path
    bridge_pid: Path
    tunnel_pid: Path
    bridge_out: Path
    bridge_err: Path
    tunnel_out: Path
    tunnel_err: Path
    url_file: Path
    run_summary: Path


@dataclass
class SessionState:
    token: str
    bridge_pid: int | None = None
    tunnel_pid: int | None = None
    final_url: str | None = None


def build_paths(repo_root: Path, payload_root: Path) -> Paths:
    log_dir = repo_root / ".riftreader-local" / "bridge-one-tab"
    return Paths(
        repo_root=repo_root,
        payload_root=payload_root,
        log_dir=log_dir,
        bridge_py=repo_root / "tools" / "riftreader_workflow" / "local_artifact_bridge.py",
        bridge_pid=log_dir / "bridge.pid",
        tunnel_pid=log_dir / "cloudflared.pid",
        bridge_out=log_dir / "bridge.out.log",
        bridge_err=log_dir / "bridge.err.log",
        tunnel_out=log_dir / "cloudflared.out.log",
        tunnel_err=log_dir / "cloudflared.err.log",
        url_file=log_dir / "COPY_THIS_CHATGPT_URL.txt",
        run_summary=log_dir / "bridge-tunnel-session-summary.json",
    )


def read_text_tail(path: Path, max_chars: int = 12000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""
    except OSError as exc:
        return f"<failed to read {path}: {type(exc).__name__}: {exc}>"
    return text[-max_chars:] if len(text) > max_chars else text


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def run_checked(args: Sequence[str], *, cwd: Path, description: str, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(args),
        cwd=str(cwd),
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        detail = {
            "command": list(args),
            "returncode": result.returncode,
            "stdout_tail": result.stdout[-4000:],
            "stderr_tail": result.stderr[-4000:],
        }
        raise RuntimeError(f"{description} failed: {json.dumps(detail, indent=2)}")
    return result


def parse_pid_file(path: Path) -> int | None:
    try:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
    except (FileNotFoundError, OSError):
        return None
    return int(text) if text.isdigit() else None


def stop_pid(pid: int, console: Console, reason: str) -> None:
    if pid <= 0:
        return
    if os.name == "nt":
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            text=True,
        )
        if result.returncode == 0:
            console.warn(f"Stopped PID {pid} ({reason}).")
        return
    try:
        os.kill(pid, signal.SIGTERM)
        console.warn(f"Stopped PID {pid} ({reason}).")
    except (ProcessLookupError, PermissionError):
        return


def stop_pid_file(path: Path, console: Console, reason: str) -> None:
    pid = parse_pid_file(path)
    if pid is not None:
        stop_pid(pid, console, reason)


def listening_pids_from_netstat(output: str, port: int) -> list[int]:
    pids: set[int] = set()
    marker = f":{port}"
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        if parts[0].upper() != "TCP":
            continue
        local_address = parts[1]
        state = parts[3].upper()
        pid_text = parts[4]
        if state != "LISTENING":
            continue
        if not local_address.endswith(marker):
            continue
        if pid_text.isdigit():
            pids.add(int(pid_text))
    return sorted(pids)


def listening_pids_windows(port: int) -> list[int]:
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return []
    if result.returncode != 0:
        return []
    return listening_pids_from_netstat(result.stdout, port)


def stop_port_listener(port: int, console: Console) -> None:
    if os.name != "nt":
        console.warn(f"Automatic stale listener cleanup is Windows-focused; skipping port {port} process cleanup on this OS.")
        return
    pids = listening_pids_windows(port)
    if not pids:
        console.ok(f"No stale listener found on port {port}.")
        return
    for pid in pids:
        stop_pid(pid, console, f"stale listener on port {port}")


def remove_old_runtime_files(paths: Paths) -> None:
    for path in [
        paths.bridge_pid,
        paths.tunnel_pid,
        paths.bridge_out,
        paths.bridge_err,
        paths.tunnel_out,
        paths.tunnel_err,
        paths.url_file,
        paths.run_summary,
    ]:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def validate_environment(paths: Paths, console: Console) -> None:
    console.step("Checking environment")
    if not paths.repo_root.is_dir():
        raise RuntimeError(f"Repo root not found: {paths.repo_root}")
    if not paths.bridge_py.is_file():
        raise RuntimeError(f"Missing bridge Python core: {paths.bridge_py}")
    if shutil.which("cloudflared") is None:
        raise RuntimeError("cloudflared was not found on PATH.")
    paths.log_dir.mkdir(parents=True, exist_ok=True)
    console.ok("Environment checks passed.")
    console.info("Repo", str(paths.repo_root))
    console.info("Bridge core", str(paths.bridge_py))
    console.info("Payload root", str(paths.payload_root))
    console.info("Log folder", str(paths.log_dir))


def bridge_python_command(paths: Paths, *extra: str) -> list[str]:
    return [sys.executable, str(paths.bridge_py), *extra]


def run_bridge_preflight(paths: Paths, console: Console) -> dict:
    console.step("Running bridge preflight")
    result = run_checked(
        bridge_python_command(
            paths,
            "--preflight",
            "--payload-root",
            str(paths.payload_root),
            "--json",
        ),
        cwd=paths.repo_root,
        description="Bridge preflight",
        timeout=60,
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = {"status": "unknown", "rawStdout": result.stdout[-4000:]}
    if payload.get("status") != "passed":
        raise RuntimeError(f"Bridge preflight did not pass: {json.dumps(payload, indent=2)[:4000]}")
    console.ok("Bridge preflight passed.")
    if payload.get("latestPayloadId"):
        console.info("Latest payload", str(payload.get("latestPayloadId")))
    return payload


def start_bridge(paths: Paths, state: SessionState, console: Console, max_response_mb: int, max_inbox_mb: int, port: int) -> subprocess.Popen[str]:
    console.step("Starting RiftReader bridge")
    out_handle = paths.bridge_out.open("w", encoding="utf-8", errors="replace")
    err_handle = paths.bridge_err.open("w", encoding="utf-8", errors="replace")
    try:
        process = subprocess.Popen(
            bridge_python_command(
                paths,
                "--serve",
                "--payload-root",
                str(paths.payload_root),
                "--port",
                str(port),
                "--token",
                state.token,
                "--max-response-mb",
                str(max_response_mb),
                "--max-inbox-mb",
                str(max_inbox_mb),
            ),
            cwd=str(paths.repo_root),
            stdout=out_handle,
            stderr=err_handle,
            text=True,
        )
    finally:
        out_handle.close()
        err_handle.close()

    state.bridge_pid = int(process.pid)
    paths.bridge_pid.write_text(str(state.bridge_pid), encoding="ascii")
    time.sleep(4.0)

    if process.poll() is not None:
        console.fail("Bridge process exited early.")
        console.line("---- bridge.out.log ----", Colors.DIM)
        console.line(read_text_tail(paths.bridge_out))
        console.line("---- bridge.err.log ----", Colors.DIM)
        console.line(read_text_tail(paths.bridge_err))
        raise RuntimeError("Bridge process exited early.")

    console.ok("Bridge started.")
    console.info("Bridge PID", str(state.bridge_pid))
    return process


def check_bridge_health(port: int, token: str, console: Console) -> None:
    console.step("Checking bridge health with exact generated token")
    url = f"http://127.0.0.1:{port}/{token}/health"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            status = int(getattr(response, "status", 0))
            body = response.read(2000).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Bridge health returned HTTP {exc.code} for {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Bridge health request failed for {url}: {exc}") from exc

    if status != 200:
        raise RuntimeError(f"Bridge health returned HTTP {status}: {body}")
    console.ok("Bridge health check passed.")


def start_tunnel(paths: Paths, state: SessionState, console: Console, port: int) -> subprocess.Popen[str]:
    console.step("Starting cloudflared tunnel")
    out_handle = paths.tunnel_out.open("w", encoding="utf-8", errors="replace")
    err_handle = paths.tunnel_err.open("w", encoding="utf-8", errors="replace")
    try:
        process = subprocess.Popen(
            ["cloudflared", "tunnel", "--url", f"http://127.0.0.1:{port}"],
            cwd=str(paths.repo_root),
            stdout=out_handle,
            stderr=err_handle,
            text=True,
        )
    finally:
        out_handle.close()
        err_handle.close()

    state.tunnel_pid = int(process.pid)
    paths.tunnel_pid.write_text(str(state.tunnel_pid), encoding="ascii")
    time.sleep(2.0)

    if process.poll() is not None:
        console.fail("cloudflared exited early.")
        console.line("---- cloudflared.out.log ----", Colors.DIM)
        console.line(read_text_tail(paths.tunnel_out))
        console.line("---- cloudflared.err.log ----", Colors.DIM)
        console.line(read_text_tail(paths.tunnel_err))
        raise RuntimeError("cloudflared exited early.")

    console.ok("cloudflared started.")
    console.info("Tunnel PID", str(state.tunnel_pid))
    return process


def detect_tunnel_url_from_text(text: str) -> str | None:
    match = TRYCLOUDFLARE_RE.search(text)
    return match.group(0) if match else None


def detect_tunnel_url(paths: Paths, state: SessionState, console: Console, wait_seconds: int) -> None:
    console.step("Waiting for public trycloudflare URL")
    deadline = time.time() + wait_seconds
    found: str | None = None
    while time.time() < deadline and not found:
        for log in (paths.tunnel_err, paths.tunnel_out):
            text = read_text_tail(log, max_chars=60000)
            found = detect_tunnel_url_from_text(text)
            if found:
                break
        if not found:
            time.sleep(0.5)

    if not found:
        console.fail("Timed out waiting for trycloudflare URL.")
        console.info("cloudflared stderr", str(paths.tunnel_err))
        console.info("cloudflared stdout", str(paths.tunnel_out))
        raise RuntimeError("No trycloudflare URL detected.")

    state.final_url = f"{found}/{state.token}/chatgpt-handoff.json"
    paths.url_file.write_text(state.final_url + "\n", encoding="utf-8")
    console.ok("Public URL detected.")
    copy_to_clipboard(state.final_url, console)


def copy_to_clipboard(text: str, console: Console) -> None:
    if os.name == "nt":
        try:
            subprocess.run(["clip"], input=text, text=True, check=True)
            console.ok("URL copied to clipboard.")
            return
        except (OSError, subprocess.CalledProcessError):
            pass
    console.warn("Could not copy URL to clipboard; use the saved URL file or printed URL.")


def cleanup(state: SessionState, console: Console) -> None:
    console.step("Cleaning up")
    if state.tunnel_pid is not None:
        stop_pid(state.tunnel_pid, console, "launcher exit")
    if state.bridge_pid is not None:
        stop_pid(state.bridge_pid, console, "launcher exit")
    console.ok("Cleanup complete.")


def synthetic_path_with_spaces_test() -> dict:
    # This self-test runs inside broad Windows CI/unittest discovery, where a
    # cold Python subprocess can be delayed by CPU contention or AV scanning.
    synthetic_timeout_seconds = 60
    with tempfile.TemporaryDirectory(prefix="Rift Reader Space Test ") as temp_raw:
        temp = Path(temp_raw)
        script = temp / "fake bridge core.py"
        script.write_text(
            textwrap.dedent(
                """
                import json
                import sys
                print(json.dumps({"ok": True, "argv": sys.argv[1:]}, separators=(",", ":")))
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )
        result = run_checked(
            [sys.executable, str(script), "--preflight", "--payload-root", str(temp / "payload root with spaces"), "--json"],
            cwd=temp,
            description="Synthetic path-with-spaces Python launch",
            timeout=synthetic_timeout_seconds,
        )
        payload = json.loads(result.stdout)
        return {
            "status": "passed" if payload.get("ok") else "failed",
            "scriptPathHadSpaces": " " in str(script),
            "argv": payload.get("argv"),
        }


def self_test() -> int:
    checks = []

    token = secrets.token_hex(16)
    checks.append({"name": "token-format", "passed": bool(re.fullmatch(r"[a-f0-9]{32}", token))})

    sample = "Visit it at: https://example-testing.trycloudflare.com"
    checks.append({"name": "trycloudflare-url-regex", "passed": detect_tunnel_url_from_text(sample) == "https://example-testing.trycloudflare.com"})

    netstat_sample = "  TCP    127.0.0.1:8765         0.0.0.0:0              LISTENING       12345"
    checks.append({"name": "netstat-port-parser", "passed": listening_pids_from_netstat(netstat_sample, 8765) == [12345]})

    space_test = synthetic_path_with_spaces_test()
    checks.append({"name": "python-subprocess-path-with-spaces", "passed": space_test["status"] == "passed" and space_test["scriptPathHadSpaces"]})

    status = "passed" if all(item["passed"] for item in checks) else "failed"
    print(json.dumps({"schemaVersion": 1, "tool": VERSION, "status": status, "checks": checks, "spaceTest": space_test}, separators=(",", ":")))
    return 0 if status == "passed" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run RiftReader bridge and cloudflared tunnel as a guarded local session.")
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT))
    parser.add_argument("--payload-root", default=str(DEFAULT_PAYLOAD_ROOT))
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--max-response-mb", type=int, default=DEFAULT_MAX_RESPONSE_MB)
    parser.add_argument("--max-inbox-mb", type=int, default=DEFAULT_MAX_INBOX_MB)
    parser.add_argument("--wait-seconds", type=int, default=DEFAULT_WAIT_SECONDS)
    parser.add_argument("--no-clean-stale", action="store_true")
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.self_test:
        return self_test()

    console = Console(no_color=bool(args.no_color))
    repo_root = Path(args.repo_root).resolve()
    payload_root = Path(args.payload_root)
    if not payload_root.is_absolute():
        payload_root = repo_root / payload_root
    paths = build_paths(repo_root=repo_root, payload_root=payload_root)
    state = SessionState(token=secrets.token_hex(16))

    try:
        console.title("RiftReader Bridge + Tunnel Session v0.2.1")
        validate_environment(paths, console)

        if not args.no_clean_stale:
            console.step("Stopping stale bridge and tunnel state")
            stop_pid_file(paths.bridge_pid, console, "old bridge PID file")
            stop_pid_file(paths.tunnel_pid, console, "old tunnel PID file")
            stop_port_listener(args.port, console)
            remove_old_runtime_files(paths)
            console.ok("Stale cleanup complete.")

        console.info("Token path", f"/{state.token}/chatgpt-handoff.json")

        preflight = run_bridge_preflight(paths, console)
        start_bridge(paths, state, console, args.max_response_mb, args.max_inbox_mb, args.port)
        check_bridge_health(args.port, state.token, console)
        start_tunnel(paths, state, console, args.port)
        detect_tunnel_url(paths, state, console, args.wait_seconds)

        summary = {
            "schemaVersion": 1,
            "tool": VERSION,
            "status": "ready",
            "timestampUtc": utc_iso(),
            "bridgePid": state.bridge_pid,
            "tunnelPid": state.tunnel_pid,
            "handoffUrl": state.final_url,
            "urlFile": str(paths.url_file),
            "logs": {
                "bridgeOut": str(paths.bridge_out),
                "bridgeErr": str(paths.bridge_err),
                "tunnelOut": str(paths.tunnel_out),
                "tunnelErr": str(paths.tunnel_err),
            },
            "preflightStatus": preflight.get("status"),
            "latestPayloadId": preflight.get("latestPayloadId"),
            "safety": {
                "noGitMutation": True,
                "noLiveRiftInput": True,
                "noDebuggerAttach": True,
                "noCommandExecutionEndpoint": True,
            },
        }
        write_json(paths.run_summary, summary)

        console.copy_block(state.final_url or "")
        console.info("Saved URL file", str(paths.url_file))
        console.info("Run summary", str(paths.run_summary))
        console.info("Bridge PID", str(state.bridge_pid))
        console.info("Tunnel PID", str(state.tunnel_pid))
        console.line()
        console.line("Keep this window open while ChatGPT reads the bridge.", Colors.CYAN)
        console.line("Press ENTER only when you are finished. This will stop both processes.", Colors.YELLOW)
        input()
        return 0

    except KeyboardInterrupt:
        console.warn("Interrupted by user.")
        return 130
    except Exception as exc:
        console.line()
        console.fail(str(exc))
        console.line()
        console.line("Useful logs:", Colors.YELLOW)
        console.line(f"  {paths.bridge_out}", Colors.YELLOW)
        console.line(f"  {paths.bridge_err}", Colors.YELLOW)
        console.line(f"  {paths.tunnel_out}", Colors.YELLOW)
        console.line(f"  {paths.tunnel_err}", Colors.YELLOW)
        console.line()
        console.line("Press ENTER to clean up and exit.", Colors.YELLOW)
        try:
            input()
        except EOFError:
            pass
        return 1
    finally:
        cleanup(state, console)


if __name__ == "__main__":
    raise SystemExit(main())

# END_OF_SCRIPT_MARKER
