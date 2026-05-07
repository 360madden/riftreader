from __future__ import annotations

import base64
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class JsonCommandResult:
    label: str
    args: list[str]
    exit_code: int
    stdout: str
    stderr: str
    json_data: Any | None
    json_text: str | None
    parse_error: str | None

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and self.json_data is not None


def extract_first_json(text: str) -> tuple[Any, str]:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char not in "[{":
            continue
        try:
            value, end = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        return value, text[index : index + end]
    raise ValueError("No JSON object or array found in command output")


def run_json_command(
    args: list[str],
    *,
    cwd: Path,
    label: str,
    timeout_seconds: int | None = None,
) -> JsonCommandResult:
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = _timeout_stream_to_text(exc.stdout or exc.output)
        stderr = _timeout_stream_to_text(exc.stderr)
        timeout_text = f"Command timed out after {timeout_seconds} seconds"
        stderr = "\n".join(part for part in (stderr, timeout_text) if part)
        return JsonCommandResult(
            label=label,
            args=args,
            exit_code=124,
            stdout=stdout,
            stderr=stderr,
            json_data=None,
            json_text=None,
            parse_error=timeout_text,
        )

    combined = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    json_data = None
    json_text = None
    parse_error = None
    try:
        json_data, json_text = extract_first_json(completed.stdout or combined)
    except Exception as exc:  # noqa: BLE001 - keep parse failure in artifacts.
        parse_error = str(exc)
        if completed.stdout and completed.stderr:
            try:
                json_data, json_text = extract_first_json(combined)
                parse_error = None
            except Exception as combined_exc:  # noqa: BLE001
                parse_error = f"{parse_error}; combined parse failed: {combined_exc}"

    return JsonCommandResult(
        label=label,
        args=args,
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        json_data=json_data,
        json_text=json_text,
        parse_error=parse_error,
    )


def _timeout_stream_to_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def command_envelope(result: JsonCommandResult) -> dict[str, Any]:
    return {
        "label": result.label,
        "args": result.args,
        "exitCode": result.exit_code,
        "json": result.json_data,
        "jsonParseError": result.parse_error,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def pwsh_file_command(script_path: Path, args: list[str]) -> list[str]:
    return [
        "pwsh",
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_path),
        *args,
    ]


def ps_quote(value: str | Path) -> str:
    text = str(value)
    return "'" + text.replace("'", "''") + "'"


def pwsh_encoded_command(script_text: str) -> list[str]:
    encoded = base64.b64encode(script_text.encode("utf-16le")).decode("ascii")
    return [
        "pwsh",
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-EncodedCommand",
        encoded,
    ]
