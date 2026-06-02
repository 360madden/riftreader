from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import math
import os
import re
import struct
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from .workflow_common import base_safety, repo_root, safe_mapping, utc_iso, utc_stamp, write_json
except ImportError:  # pragma: no cover - direct script execution
    from workflow_common import base_safety, repo_root, safe_mapping, utc_iso, utc_stamp, write_json  # type: ignore


SCHEMA_VERSION = 1
KIND = "riftreader-glyph-forensics-inventory"
DEFAULT_TEXT_PREVIEW_BYTES = 4096
DEFAULT_MAX_FILES_PER_ROOT = 500
DEFAULT_MAX_STRING_HITS = 250
DEFAULT_MAX_IMPORT_FUNCTIONS_PER_DLL = 250
DEFAULT_LOG_TIMELINE_EVENTS = 120
DEFAULT_MANIFEST_ENTRY_LIMIT = 40
SKIP_DIRECTORY_NAMES = {
    "$recycle.bin",
    ".git",
    "cache",
    "download",
    "downloads",
    "games",
    "logs-archived",
    "patchdata",
    "temp",
    "tmp",
}

SENSITIVE_KEY_RE = re.compile(
    r"(?i)(password|passwd|pwd|secret|token|session|cookie|auth|authorization|ticket|bearer|oauth|apikey|api_key|email|username|account)"
)
ASSIGNMENT_RE = re.compile(
    r"(?i)(?P<key>[A-Za-z0-9_.-]*(?:password|passwd|pwd|secret|token|session|cookie|auth|authorization|ticket|bearer|oauth|apikey|api_key|email|username|account)[A-Za-z0-9_.-]*)"
    r"(?P<sep>\s*[:=]\s*)"
    r"(?P<value>\"[^\"]*\"|'[^']*'|[^,\s;}\]]+)"
)
EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}")
LONG_TOKEN_RE = re.compile(r"\b[A-Za-z0-9._~+/=-]{32,}\b")
URL_RE = re.compile(r"(?i)\bhttps?://[^\s\"'<>]+")
HOST_RE = re.compile(r"(?i)\b(?:[a-z0-9-]+\.)+(?:com|net|org|io|gg|tv|cloud|cdn|games|trionworlds)\b")
REGISTRY_RE = re.compile(r"(?i)\b(?:HKCU|HKLM|HKEY_CURRENT_USER|HKEY_LOCAL_MACHINE)\\[^\s\"']+")

TEXT_EXTENSIONS = {
    ".cfg",
    ".conf",
    ".config",
    ".ini",
    ".json",
    ".log",
    ".manifest",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}

INTERESTING_EXTENSIONS = TEXT_EXTENSIONS | {
    ".dat",
    ".dll",
    ".exe",
    ".pak",
    ".patch",
    ".version",
}

REGISTRY_CANDIDATE_PATHS = (
    r"HKCU:\Software\Glyph",
    r"HKCU:\Software\Trion",
    r"HKCU:\Software\Trion Worlds",
    r"HKLM:\SOFTWARE\Glyph",
    r"HKLM:\SOFTWARE\Trion",
    r"HKLM:\SOFTWARE\Trion Worlds",
    r"HKLM:\SOFTWARE\WOW6432Node\Glyph",
    r"HKLM:\SOFTWARE\WOW6432Node\Trion",
    r"HKLM:\SOFTWARE\WOW6432Node\Trion Worlds",
)

PE_MACHINE_NAMES = {
    0x014C: "I386",
    0x0200: "IA64",
    0x8664: "AMD64",
    0x01C0: "ARM",
    0x01C4: "ARMv7",
    0xAA64: "ARM64",
}

PE_SUBSYSTEM_NAMES = {
    1: "NATIVE",
    2: "WINDOWS_GUI",
    3: "WINDOWS_CUI",
    7: "POSIX_CUI",
    9: "WINDOWS_CE_GUI",
    10: "EFI_APPLICATION",
    11: "EFI_BOOT_SERVICE_DRIVER",
    12: "EFI_RUNTIME_DRIVER",
    13: "EFI_ROM",
    14: "XBOX",
    16: "WINDOWS_BOOT_APPLICATION",
}

PE_CHARACTERISTIC_FLAGS = {
    0x0001: "RELOCS_STRIPPED",
    0x0002: "EXECUTABLE_IMAGE",
    0x0004: "LINE_NUMS_STRIPPED",
    0x0008: "LOCAL_SYMS_STRIPPED",
    0x0020: "LARGE_ADDRESS_AWARE",
    0x0080: "BYTES_REVERSED_LO",
    0x0100: "32BIT_MACHINE",
    0x0200: "DEBUG_STRIPPED",
    0x0400: "REMOVABLE_RUN_FROM_SWAP",
    0x0800: "NET_RUN_FROM_SWAP",
    0x1000: "SYSTEM",
    0x2000: "DLL",
    0x4000: "UP_SYSTEM_ONLY",
    0x8000: "BYTES_REVERSED_HI",
}

PE_DLL_CHARACTERISTIC_FLAGS = {
    0x0020: "HIGH_ENTROPY_VA",
    0x0040: "DYNAMIC_BASE",
    0x0080: "FORCE_INTEGRITY",
    0x0100: "NX_COMPAT",
    0x0200: "NO_ISOLATION",
    0x0400: "NO_SEH",
    0x0800: "NO_BIND",
    0x1000: "APPCONTAINER",
    0x2000: "WDM_DRIVER",
    0x4000: "GUARD_CF",
    0x8000: "TERMINAL_SERVER_AWARE",
}

PE_SECTION_CHARACTERISTIC_FLAGS = {
    0x00000020: "CNT_CODE",
    0x00000040: "CNT_INITIALIZED_DATA",
    0x00000080: "CNT_UNINITIALIZED_DATA",
    0x02000000: "MEM_DISCARDABLE",
    0x04000000: "MEM_NOT_CACHED",
    0x08000000: "MEM_NOT_PAGED",
    0x10000000: "MEM_SHARED",
    0x20000000: "MEM_EXECUTE",
    0x40000000: "MEM_READ",
    0x80000000: "MEM_WRITE",
}

PE_DATA_DIRECTORY_NAMES = (
    "export",
    "import",
    "resource",
    "exception",
    "certificate",
    "baseRelocation",
    "debug",
    "architecture",
    "globalPtr",
    "tls",
    "loadConfig",
    "boundImport",
    "iat",
    "delayImport",
    "clrRuntime",
    "reserved",
)


def redact_text(text: str) -> str:
    redacted = BEARER_RE.sub("Bearer <redacted>", text)
    redacted = ASSIGNMENT_RE.sub(lambda match: f"{match.group('key')}{match.group('sep')}<redacted>", redacted)
    redacted = EMAIL_RE.sub("<redacted-email>", redacted)
    redacted = LONG_TOKEN_RE.sub(lambda m: "<redacted-long-value>" if SENSITIVE_KEY_RE.search(text[max(0, m.start() - 40) : m.start()]) else m.group(0), redacted)
    return redacted


def redact_jsonish(value: Any, *, key_hint: str = "") -> Any:
    if SENSITIVE_KEY_RE.search(key_hint):
        return "<redacted>"
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_jsonish(item, key_hint=key_hint) for item in value]
    if isinstance(value, Mapping):
        return {str(key): redact_jsonish(item, key_hint=str(key)) for key, item in value.items()}
    return value


def sha256_file(path: Path, *, limit_bytes: int | None = None) -> str | None:
    try:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            remaining = limit_bytes
            while True:
                size = 1024 * 1024 if remaining is None else min(remaining, 1024 * 1024)
                if size <= 0:
                    break
                chunk = fh.read(size)
                if not chunk:
                    break
                h.update(chunk)
                if remaining is not None:
                    remaining -= len(chunk)
        return h.hexdigest()
    except OSError:
        return None


def file_metadata(path: Path, *, hash_file: bool = False) -> dict[str, Any]:
    try:
        stat = path.stat()
    except OSError as exc:
        return {"path": str(path), "exists": False, "error": f"{type(exc).__name__}:{exc}"}
    payload: dict[str, Any] = {
        "path": str(path),
        "exists": True,
        "isFile": path.is_file(),
        "isDirectory": path.is_dir(),
        "sizeBytes": stat.st_size,
        "modifiedUtc": datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
        "suffix": path.suffix.lower(),
    }
    if hash_file and path.is_file():
        payload["sha256"] = sha256_file(path)
    return payload


def install_root_from_processes(processes: Sequence[Mapping[str, Any]]) -> Path | None:
    for proc in processes:
        path_value = proc.get("ExecutablePath")
        if not isinstance(path_value, str) or not path_value:
            continue
        path = Path(path_value)
        if path.name.lower() == "glyphclientapp.exe" and path.parent.name.lower() == "glyph":
            return path.parent
        if path.parent.name.lower() in {"x64", "x86"} and path.parent.parent.name.lower() == "glyph":
            return path.parent.parent
    return None


def targeted_glyph_paths(glyph_processes: Sequence[Mapping[str, Any]]) -> list[Path]:
    roots = likely_roots(glyph_processes)
    install_root = install_root_from_processes(glyph_processes)
    if install_root is not None and install_root not in roots:
        roots.append(install_root)
    paths: list[Path] = []
    for root in roots:
        for rel in (
            "GlyphClient.xml",
            "GlyphClient.cfg",
            "library_manifest.txt",
            "Library/GlyphLibrary.xml",
            "Notification.log",
            "Games/RIFT/Live/manifest64.txt",
            "Games/RIFT/Live/assets64.manifest",
            "Games/RIFT/Live/assets64_dev.manifest",
            "Games/RIFT/Live/assets64_debug.manifest",
            "Games/RIFT/Live/rift_x64.exe",
            "Games/RIFT/Live/rifterrorhandler_x64.exe",
            "Games/RIFT/Live/GlyphClientApp.exe",
        ):
            paths.append(root / rel)
    for env_key, rels in (
        (
            "LOCALAPPDATA",
            (
                "Glyph/GlyphClient.cfg",
                "Glyph/Logs/GlyphClient.0.log",
                "Glyph/Logs/GlyphClient.1.log",
                "Glyph/Logs/GlyphClient.2.log",
                "Glyph/Logs/GlyphClient.9.log",
            ),
        ),
        (
            "APPDATA",
            (
                "RIFT/recents.cfg",
                "RIFT/rift.cfg",
                "RIFT/rift.log",
                "RIFT/riftconnect.cfg",
                "RIFT/rifterrorhandler.cfg",
            ),
        ),
        ("ProgramData", ("Glyph/GlyphLibrary.cfg",)),
    ):
        base = os.environ.get(env_key)
        if base:
            for rel in rels:
                paths.append(Path(base) / rel)
    unique: list[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def targeted_file_inventory(paths: Sequence[Path]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in paths:
        suffix = path.suffix.lower()
        hash_file = suffix in {".exe", ".dll"} and path.exists()
        items.append(file_metadata(path, hash_file=hash_file))
    return items


def unpack_from(fmt: str, data: bytes, offset: int) -> tuple[Any, ...]:
    size = struct.calcsize(fmt)
    if offset < 0 or offset + size > len(data):
        raise ValueError(f"offset-out-of-range:{offset}+{size}>{len(data)}")
    return struct.unpack_from(fmt, data, offset)


def u16(data: bytes, offset: int) -> int:
    return int(unpack_from("<H", data, offset)[0])


def u32(data: bytes, offset: int) -> int:
    return int(unpack_from("<I", data, offset)[0])


def u64(data: bytes, offset: int) -> int:
    return int(unpack_from("<Q", data, offset)[0])


def hex_value(value: int | None) -> str | None:
    return None if value is None else f"0x{int(value):X}"


def bit_flags(value: int, names: Mapping[int, str]) -> list[str]:
    return [name for bit, name in names.items() if value & bit]


def section_entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = [0] * 256
    for item in data:
        counts[item] += 1
    total = float(len(data))
    entropy = 0.0
    for count in counts:
        if count:
            p = count / total
            entropy -= p * math.log2(p)
    return round(entropy, 4)


def read_cstring(data: bytes, offset: int, *, max_bytes: int = 4096) -> str:
    if offset < 0 or offset >= len(data):
        return ""
    end = min(len(data), offset + max_bytes)
    nul = data.find(b"\x00", offset, end)
    if nul == -1:
        nul = end
    return data[offset:nul].decode("utf-8", errors="replace")


def rva_to_offset(sections: Sequence[Mapping[str, Any]], rva: int) -> int | None:
    for section in sections:
        try:
            virtual_address = int(section.get("virtualAddress", 0))
            virtual_size = int(section.get("virtualSize", 0))
            raw_size = int(section.get("rawDataSize", 0))
            raw_pointer = int(section.get("pointerToRawData", 0))
        except (TypeError, ValueError):
            continue
        span = max(virtual_size, raw_size)
        if virtual_address <= rva < virtual_address + span:
            delta = rva - virtual_address
            if delta < raw_size:
                return raw_pointer + delta
            return None
    return None


def parse_pe_imports(
    data: bytes,
    sections: Sequence[Mapping[str, Any]],
    import_rva: int,
    *,
    is_pe32_plus: bool,
    max_functions_per_dll: int,
) -> list[dict[str, Any]]:
    imports: list[dict[str, Any]] = []
    import_offset = rva_to_offset(sections, import_rva)
    if import_offset is None:
        return imports
    descriptor_offset = import_offset
    thunk_size = 8 if is_pe32_plus else 4
    ordinal_flag = 0x8000000000000000 if is_pe32_plus else 0x80000000
    for _ in range(512):
        if descriptor_offset + 20 > len(data):
            break
        original_first_thunk, timestamp, forwarder_chain, name_rva, first_thunk = unpack_from("<IIIII", data, descriptor_offset)
        if not any((original_first_thunk, timestamp, forwarder_chain, name_rva, first_thunk)):
            break
        name_offset = rva_to_offset(sections, int(name_rva))
        dll_name = read_cstring(data, name_offset) if name_offset is not None else f"<name-rva:{hex_value(int(name_rva))}>"
        thunk_rva = int(original_first_thunk or first_thunk)
        thunk_offset = rva_to_offset(sections, thunk_rva)
        functions: list[str] = []
        ordinal_count = 0
        truncated = False
        if thunk_offset is not None:
            for index in range(4096):
                entry_offset = thunk_offset + index * thunk_size
                if entry_offset + thunk_size > len(data):
                    break
                thunk_value = u64(data, entry_offset) if is_pe32_plus else u32(data, entry_offset)
                if thunk_value == 0:
                    break
                if thunk_value & ordinal_flag:
                    ordinal_count += 1
                    rendered = f"ordinal:{thunk_value & 0xFFFF}"
                else:
                    hint_name_offset = rva_to_offset(sections, int(thunk_value))
                    rendered = (
                        read_cstring(data, hint_name_offset + 2)
                        if hint_name_offset is not None and hint_name_offset + 2 < len(data)
                        else f"<hint-name-rva:{hex_value(int(thunk_value))}>"
                    )
                if len(functions) < max_functions_per_dll:
                    functions.append(rendered)
                else:
                    truncated = True
        imports.append(
            {
                "dll": dll_name,
                "originalFirstThunkRva": hex_value(int(original_first_thunk)),
                "firstThunkRva": hex_value(int(first_thunk)),
                "functionCountCaptured": len(functions),
                "ordinalCount": ordinal_count,
                "truncated": truncated,
                "functions": functions,
            }
        )
        descriptor_offset += 20
    return imports


def parse_pe_exports(data: bytes, sections: Sequence[Mapping[str, Any]], export_rva: int, *, max_names: int = 300) -> dict[str, Any]:
    export_offset = rva_to_offset(sections, export_rva)
    if export_offset is None or export_offset + 40 > len(data):
        return {"status": "missing"}
    (
        _characteristics,
        timestamp,
        major_version,
        minor_version,
        name_rva,
        base,
        number_of_functions,
        number_of_names,
        address_of_functions,
        address_of_names,
        address_of_name_ordinals,
    ) = unpack_from("<IIHHIIIIIII", data, export_offset)
    name_offset = rva_to_offset(sections, int(name_rva))
    names_offset = rva_to_offset(sections, int(address_of_names))
    names: list[str] = []
    if names_offset is not None:
        for index in range(min(int(number_of_names), max_names)):
            entry_offset = names_offset + index * 4
            if entry_offset + 4 > len(data):
                break
            export_name_rva = u32(data, entry_offset)
            export_name_offset = rva_to_offset(sections, export_name_rva)
            if export_name_offset is not None:
                names.append(read_cstring(data, export_name_offset))
    return {
        "status": "present",
        "dllName": read_cstring(data, name_offset) if name_offset is not None else None,
        "timeDateStamp": int(timestamp),
        "version": f"{int(major_version)}.{int(minor_version)}",
        "ordinalBase": int(base),
        "numberOfFunctions": int(number_of_functions),
        "numberOfNames": int(number_of_names),
        "addressOfFunctionsRva": hex_value(int(address_of_functions)),
        "addressOfNamesRva": hex_value(int(address_of_names)),
        "addressOfNameOrdinalsRva": hex_value(int(address_of_name_ordinals)),
        "namesCaptured": names,
        "truncated": int(number_of_names) > len(names),
    }


def parse_pe_tls_callbacks(
    data: bytes,
    sections: Sequence[Mapping[str, Any]],
    tls_rva: int,
    *,
    image_base: int,
    is_pe32_plus: bool,
) -> dict[str, Any]:
    tls_offset = rva_to_offset(sections, tls_rva)
    if tls_offset is None:
        return {"status": "missing"}
    try:
        if is_pe32_plus:
            _start_raw, _end_raw, _address_of_index, address_of_callbacks, _zero_fill, _characteristics = unpack_from(
                "<QQQQII", data, tls_offset
            )
            ptr_size = 8
        else:
            _start_raw, _end_raw, _address_of_index, address_of_callbacks, _zero_fill, _characteristics = unpack_from(
                "<IIIIII", data, tls_offset
            )
            ptr_size = 4
    except ValueError as exc:
        return {"status": "failed", "error": str(exc)}
    callbacks_rva = int(address_of_callbacks) - int(image_base)
    callbacks_offset = rva_to_offset(sections, callbacks_rva)
    callbacks: list[dict[str, str]] = []
    if callbacks_offset is not None:
        for index in range(64):
            pointer_offset = callbacks_offset + index * ptr_size
            if pointer_offset + ptr_size > len(data):
                break
            callback_va = u64(data, pointer_offset) if is_pe32_plus else u32(data, pointer_offset)
            if callback_va == 0:
                break
            callbacks.append({"va": hex_value(int(callback_va)) or "", "rva": hex_value(int(callback_va - image_base)) or ""})
    return {
        "status": "present",
        "addressOfCallbacksVa": hex_value(int(address_of_callbacks)),
        "addressOfCallbacksRva": hex_value(callbacks_rva),
        "callbacks": callbacks,
    }


def parse_pe_metadata(path: Path, *, max_import_functions_per_dll: int = DEFAULT_MAX_IMPORT_FUNCTIONS_PER_DLL) -> dict[str, Any]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        return {"path": str(path), "status": "failed", "error": f"{type(exc).__name__}:{exc}"}
    try:
        if len(data) < 0x40 or data[:2] != b"MZ":
            return {"path": str(path), "status": "not-pe"}
        pe_offset = u32(data, 0x3C)
        if pe_offset + 24 > len(data) or data[pe_offset : pe_offset + 4] != b"PE\x00\x00":
            return {"path": str(path), "status": "not-pe", "error": "missing-pe-signature"}
        (
            machine,
            number_of_sections,
            timestamp,
            _pointer_to_symbols,
            _number_of_symbols,
            size_of_optional_header,
            characteristics,
        ) = unpack_from("<HHIIIHH", data, pe_offset + 4)
        optional_offset = pe_offset + 24
        magic = u16(data, optional_offset)
        if magic == 0x10B:
            pe_kind = "PE32"
            is_pe32_plus = False
            image_base = u32(data, optional_offset + 28)
            data_directory_offset = optional_offset + 96
        elif magic == 0x20B:
            pe_kind = "PE32+"
            is_pe32_plus = True
            image_base = u64(data, optional_offset + 24)
            data_directory_offset = optional_offset + 112
        else:
            return {"path": str(path), "status": "not-pe", "error": f"unknown-optional-header-magic:{hex_value(magic)}"}
        address_of_entry_point = u32(data, optional_offset + 16)
        section_alignment = u32(data, optional_offset + 32)
        file_alignment = u32(data, optional_offset + 36)
        size_of_image = u32(data, optional_offset + 56)
        size_of_headers = u32(data, optional_offset + 60)
        checksum = u32(data, optional_offset + 64)
        subsystem = u16(data, optional_offset + 68)
        dll_characteristics = u16(data, optional_offset + 70)
        number_of_rva_and_sizes = u32(data, optional_offset + (108 if is_pe32_plus else 92))

        directories: dict[str, dict[str, Any]] = {}
        for index, name in enumerate(PE_DATA_DIRECTORY_NAMES[: min(number_of_rva_and_sizes, len(PE_DATA_DIRECTORY_NAMES))]):
            entry_offset = data_directory_offset + index * 8
            if entry_offset + 8 > len(data):
                break
            rva, size = unpack_from("<II", data, entry_offset)
            directories[name] = {"rva": hex_value(int(rva)), "size": int(size), "present": bool(rva and size)}

        section_offset = optional_offset + int(size_of_optional_header)
        sections: list[dict[str, Any]] = []
        last_raw_end = 0
        for index in range(int(number_of_sections)):
            header_offset = section_offset + index * 40
            if header_offset + 40 > len(data):
                break
            name_bytes = data[header_offset : header_offset + 8].split(b"\x00", 1)[0]
            virtual_size, virtual_address, raw_data_size, pointer_to_raw_data = unpack_from("<IIII", data, header_offset + 8)
            section_characteristics = u32(data, header_offset + 36)
            raw_start = int(pointer_to_raw_data)
            raw_end = min(len(data), raw_start + int(raw_data_size)) if raw_start < len(data) else raw_start
            last_raw_end = max(last_raw_end, raw_start + int(raw_data_size))
            sections.append(
                {
                    "name": name_bytes.decode("ascii", errors="replace"),
                    "virtualSize": int(virtual_size),
                    "virtualAddress": int(virtual_address),
                    "virtualAddressHex": hex_value(int(virtual_address)),
                    "rawDataSize": int(raw_data_size),
                    "pointerToRawData": int(pointer_to_raw_data),
                    "characteristics": hex_value(int(section_characteristics)),
                    "characteristicFlags": bit_flags(int(section_characteristics), PE_SECTION_CHARACTERISTIC_FLAGS),
                    "entropy": section_entropy(data[raw_start:raw_end]) if raw_start < len(data) else None,
                }
            )
        import_directory = directories.get("import", {})
        export_directory = directories.get("export", {})
        tls_directory = directories.get("tls", {})
        imports = (
            parse_pe_imports(
                data,
                sections,
                int(str(import_directory.get("rva", "0")).replace("0x", ""), 16),
                is_pe32_plus=is_pe32_plus,
                max_functions_per_dll=max_import_functions_per_dll,
            )
            if import_directory.get("present")
            else []
        )
        exports = (
            parse_pe_exports(data, sections, int(str(export_directory.get("rva", "0")).replace("0x", ""), 16))
            if export_directory.get("present")
            else {"status": "missing"}
        )
        tls = (
            parse_pe_tls_callbacks(
                data,
                sections,
                int(str(tls_directory.get("rva", "0")).replace("0x", ""), 16),
                image_base=int(image_base),
                is_pe32_plus=is_pe32_plus,
            )
            if tls_directory.get("present")
            else {"status": "missing"}
        )
        return {
            "path": str(path),
            "status": "passed",
            "format": pe_kind,
            "machine": hex_value(int(machine)),
            "machineName": PE_MACHINE_NAMES.get(int(machine), "UNKNOWN"),
            "numberOfSections": int(number_of_sections),
            "timeDateStamp": int(timestamp),
            "characteristics": hex_value(int(characteristics)),
            "characteristicFlags": bit_flags(int(characteristics), PE_CHARACTERISTIC_FLAGS),
            "addressOfEntryPointRva": hex_value(int(address_of_entry_point)),
            "imageBase": hex_value(int(image_base)),
            "sectionAlignment": int(section_alignment),
            "fileAlignment": int(file_alignment),
            "sizeOfImage": int(size_of_image),
            "sizeOfHeaders": int(size_of_headers),
            "checksum": hex_value(int(checksum)),
            "subsystem": int(subsystem),
            "subsystemName": PE_SUBSYSTEM_NAMES.get(int(subsystem), "UNKNOWN"),
            "dllCharacteristics": hex_value(int(dll_characteristics)),
            "dllCharacteristicFlags": bit_flags(int(dll_characteristics), PE_DLL_CHARACTERISTIC_FLAGS),
            "dataDirectories": directories,
            "sections": sections,
            "imports": imports,
            "importDllCount": len(imports),
            "importFunctionCountCaptured": sum(len(item.get("functions", [])) for item in imports),
            "exports": exports,
            "tls": tls,
            "overlayBytes": max(0, len(data) - last_raw_end) if last_raw_end else 0,
        }
    except Exception as exc:  # noqa: BLE001 - metadata parser should fail closed per file.
        return {"path": str(path), "status": "failed", "error": f"{type(exc).__name__}:{exc}"}


def run_powershell_json(script: str, *, timeout_seconds: float = 20.0) -> Any:
    command = [
        "pwsh",
        "-NoProfile",
        "-Command",
        "$ErrorActionPreference='SilentlyContinue'; " + script,
    ]
    completed = subprocess.run(
        command,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    text = (completed.stdout or "").strip()
    if not text:
        return []
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"parseError": True, "stdoutPreview": text[:2000], "stderrPreview": completed.stderr[:1000]}


def process_inventory() -> list[dict[str, Any]]:
    script = r"""
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -match 'glyph' -or ($_.ExecutablePath -match '\\Glyph\\') } |
  Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,CommandLine,CreationDate |
  ConvertTo-Json -Depth 4
"""
    data = run_powershell_json(script)
    if isinstance(data, Mapping):
        rows = [dict(data)]
    elif isinstance(data, list):
        rows = [dict(item) for item in data if isinstance(item, Mapping)]
    else:
        rows = []
    for row in rows:
        if isinstance(row.get("CommandLine"), str):
            row["CommandLine"] = redact_text(str(row["CommandLine"]))
    return rows


def debugger_process_scan() -> list[dict[str, Any]]:
    script = r"""
$pattern = '(?i)(x64dbg|cheatengine|cheat engine|ollydbg|ida64|idaq|ghidra|windbg|cdb|dnspy|scylla|frida|processhacker|procmon|procexp|dbgeng)'
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -match $pattern -or $_.ExecutablePath -match $pattern } |
  Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,CommandLine,CreationDate |
  ConvertTo-Json -Depth 4
"""
    data = run_powershell_json(script)
    if isinstance(data, Mapping):
        rows = [dict(data)]
    elif isinstance(data, list):
        rows = [dict(item) for item in data if isinstance(item, Mapping)]
    else:
        rows = []
    for row in rows:
        if isinstance(row.get("CommandLine"), str):
            row["CommandLine"] = redact_text(str(row["CommandLine"]))
    return rows


def active_network_connections(processes: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    pids: list[int] = []
    for proc in processes:
        try:
            pids.append(int(proc.get("ProcessId")))
        except (TypeError, ValueError):
            continue
    if not pids:
        return []
    encoded = json.dumps(pids)
    script = rf"""
$pids = ConvertFrom-Json @'
{encoded}
'@
$items = foreach ($pid in $pids) {{
  Get-NetTCPConnection -OwningProcess $pid -ErrorAction SilentlyContinue |
    Select-Object OwningProcess,State,LocalAddress,LocalPort,RemoteAddress,RemotePort,AppliedSetting,CreationTime
}}
$items | ConvertTo-Json -Depth 4
"""
    data = run_powershell_json(script, timeout_seconds=20.0)
    if isinstance(data, Mapping):
        return [dict(data)]
    if isinstance(data, list):
        return [dict(item) for item in data if isinstance(item, Mapping)]
    return []


def service_inventory() -> list[dict[str, Any]]:
    script = r"""
$pattern = '(?i)(glyph|trion|rift|gamigo)'
Get-CimInstance Win32_Service |
  Where-Object { $_.Name -match $pattern -or $_.DisplayName -match $pattern -or $_.PathName -match $pattern } |
  Select-Object Name,DisplayName,State,StartMode,PathName,ProcessId,Started |
  ConvertTo-Json -Depth 4
"""
    data = run_powershell_json(script, timeout_seconds=20.0)
    if isinstance(data, Mapping):
        return [redact_jsonish(dict(data))]
    if isinstance(data, list):
        return [redact_jsonish(dict(item)) for item in data if isinstance(item, Mapping)]
    return []


def scheduled_task_inventory() -> list[dict[str, Any]]:
    script = r"""
$pattern = '(?i)(glyph|trion|rift|gamigo)'
$items = foreach ($task in Get-ScheduledTask -ErrorAction SilentlyContinue) {
  $actions = @($task.Actions | ForEach-Object { "$($_.Execute) $($_.Arguments)" })
  $text = "$($task.TaskName) $($task.TaskPath) $($actions -join ' ')"
  if ($text -match $pattern) {
    [PSCustomObject]@{
      TaskName = $task.TaskName
      TaskPath = $task.TaskPath
      State = [string]$task.State
      Actions = $actions
    }
  }
}
$items | ConvertTo-Json -Depth 5
"""
    data = run_powershell_json(script, timeout_seconds=30.0)
    if isinstance(data, Mapping):
        return [redact_jsonish(dict(data))]
    if isinstance(data, list):
        return [redact_jsonish(dict(item)) for item in data if isinstance(item, Mapping)]
    return []


def autorun_inventory() -> list[dict[str, Any]]:
    registry_roots = [
        r"HKCU:\Software\Microsoft\Windows\CurrentVersion\Run",
        r"HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce",
        r"HKLM:\Software\Microsoft\Windows\CurrentVersion\Run",
        r"HKLM:\Software\Microsoft\Windows\CurrentVersion\RunOnce",
        r"HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run",
        r"HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\RunOnce",
    ]
    encoded = json.dumps(registry_roots)
    script = rf"""
$roots = ConvertFrom-Json @'
{encoded}
'@
$pattern = '(?i)(glyph|trion|rift|gamigo)'
$items = @()
foreach ($root in $roots) {{
  if (Test-Path -LiteralPath $root) {{
    $props = Get-ItemProperty -LiteralPath $root -ErrorAction SilentlyContinue
    if ($props) {{
      foreach ($prop in $props.PSObject.Properties) {{
        if ($prop.Name -like 'PS*') {{ continue }}
        $value = [string]$prop.Value
        if ($prop.Name -match $pattern -or $value -match $pattern) {{
          $items += [PSCustomObject]@{{ source='registry-run'; path=$root; name=$prop.Name; value=$value }}
        }}
      }}
    }}
  }}
}}
$startupDirs = @(
  [Environment]::GetFolderPath('Startup'),
  [Environment]::GetFolderPath('CommonStartup')
)
foreach ($dir in $startupDirs) {{
  if (Test-Path -LiteralPath $dir) {{
    Get-ChildItem -LiteralPath $dir -File -ErrorAction SilentlyContinue | Where-Object {{
      $_.Name -match $pattern -or $_.FullName -match $pattern
    }} | ForEach-Object {{
      $items += [PSCustomObject]@{{ source='startup-folder'; path=$dir; name=$_.Name; value=$_.FullName }}
    }}
  }}
}}
$items | ConvertTo-Json -Depth 5
"""
    data = run_powershell_json(script, timeout_seconds=30.0)
    if isinstance(data, Mapping):
        return [redact_jsonish(dict(data))]
    if isinstance(data, list):
        return [redact_jsonish(dict(item)) for item in data if isinstance(item, Mapping)]
    return []


def uninstall_inventory() -> list[dict[str, Any]]:
    roots = [
        r"HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall",
        r"HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall",
        r"HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    ]
    encoded = json.dumps(roots)
    script = rf"""
$roots = ConvertFrom-Json @'
{encoded}
'@
$broadPattern = '(?i)(glyph|trion|gamigo)'
$items = foreach ($root in $roots) {{
  if (-not (Test-Path -LiteralPath $root)) {{ continue }}
  Get-ChildItem -LiteralPath $root -ErrorAction SilentlyContinue | ForEach-Object {{
    $props = Get-ItemProperty -LiteralPath $_.PSPath -ErrorAction SilentlyContinue
    $text = "$($props.DisplayName) $($props.Publisher) $($props.InstallLocation) $($props.DisplayIcon) $($props.UninstallString)"
    $riftGlyphInstall = (
      ([string]$props.DisplayName -eq 'RIFT' -and [string]$props.InstallLocation -match '(?i)\\Glyph\\') -or
      [string]$props.DisplayIcon -match '(?i)\\Glyph\\' -or
      [string]$props.UninstallString -match '(?i)GlyphClientApp'
    )
    if ($text -match $broadPattern -or $riftGlyphInstall) {{
      [PSCustomObject]@{{
        keyPath = $_.PSPath
        displayName = $props.DisplayName
        displayVersion = $props.DisplayVersion
        publisher = $props.Publisher
        installLocation = $props.InstallLocation
        displayIcon = $props.DisplayIcon
        uninstallString = $props.UninstallString
        quietUninstallString = $props.QuietUninstallString
        estimatedSize = $props.EstimatedSize
      }}
    }}
  }}
}}
$items | ConvertTo-Json -Depth 6
"""
    data = run_powershell_json(script, timeout_seconds=30.0)
    if isinstance(data, Mapping):
        return [redact_jsonish(dict(data))]
    if isinstance(data, list):
        return [redact_jsonish(dict(item)) for item in data if isinstance(item, Mapping)]
    return []


def debugger_indicators(pid: int) -> dict[str, Any]:
    if sys.platform != "win32":
        return {"status": "unsupported-non-windows"}
    PROCESS_QUERY_INFORMATION = 0x0400
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
    handle = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, int(pid))
    access = "PROCESS_QUERY_INFORMATION"
    if not handle:
        first_error = ctypes.get_last_error()
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        access = "PROCESS_QUERY_LIMITED_INFORMATION"
        if not handle:
            return {"status": "open-process-failed", "lastError": ctypes.get_last_error(), "firstOpenLastError": first_error}
    try:
        is_debugged = ctypes.c_bool(False)
        ok = kernel32.CheckRemoteDebuggerPresent(handle, ctypes.byref(is_debugged))
        result: dict[str, Any] = {
            "status": "checked",
            "openProcessAccess": access,
            "checkRemoteDebuggerPresentOk": bool(ok),
            "checkRemoteDebuggerPresent": bool(is_debugged.value) if ok else None,
        }
        for label, info_class in (
            ("processDebugPort", 7),
            ("processDebugObjectHandle", 30),
            ("processDebugFlags", 31),
        ):
            value = ctypes.c_size_t(0)
            return_length = ctypes.c_ulong(0)
            status = ntdll.NtQueryInformationProcess(
                handle,
                info_class,
                ctypes.byref(value),
                ctypes.sizeof(value),
                ctypes.byref(return_length),
            )
            result[label] = {
                "ntstatus": int(status),
                "value": int(value.value),
                "note": "debugFlags:0 can indicate debugged; debugFlags:1 usually indicates not debugged"
                if label == "processDebugFlags"
                else None,
            }
        return result
    finally:
        kernel32.CloseHandle(handle)


def likely_roots(processes: Sequence[Mapping[str, Any]]) -> list[Path]:
    roots: list[Path] = []
    for proc in processes:
        path_value = proc.get("ExecutablePath")
        if isinstance(path_value, str) and path_value:
            path = Path(path_value)
            roots.append(path.parent)
            if path.parent.name.lower() in {"x64", "x86", "bin"}:
                roots.append(path.parent.parent)
    env_candidates = [
        os.environ.get("PROGRAMDATA"),
        os.environ.get("APPDATA"),
        os.environ.get("LOCALAPPDATA"),
        str(Path.home() / "Documents"),
    ]
    for base in env_candidates:
        if not base:
            continue
        for name in ("Glyph", "Trion Worlds", "RIFT"):
            roots.append(Path(base) / name)
    roots.extend(
        [
            Path(r"C:\Program Files (x86)\Glyph"),
            Path(r"C:\Program Files\Glyph"),
            Path(r"C:\ProgramData\Glyph"),
            Path.home() / "AppData" / "Local" / "Glyph",
            Path.home() / "AppData" / "Roaming" / "Glyph",
        ]
    )
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root).lower()
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def walk_interesting_files(root: Path, *, max_files: int) -> dict[str, Any]:
    if not root.exists():
        return {"root": str(root), "exists": False, "files": []}
    files: list[dict[str, Any]] = []
    skipped = 0
    try:
        for current_root, dirnames, filenames in os.walk(root):
            dirnames[:] = [name for name in dirnames if name.lower() not in SKIP_DIRECTORY_NAMES]
            for filename in filenames:
                path = Path(current_root) / filename
                if len(files) >= max_files:
                    skipped += 1
                    break
                try:
                    suffix = path.suffix.lower()
                except OSError:
                    continue
                if suffix not in INTERESTING_EXTENSIONS:
                    continue
                files.append(file_metadata(path, hash_file=suffix in {".exe", ".dll"}))
            if len(files) >= max_files:
                break
    except OSError as exc:
        return {"root": str(root), "exists": True, "error": f"{type(exc).__name__}:{exc}", "files": files}
    return {"root": str(root), "exists": True, "files": files, "skippedAfterLimit": skipped}


def text_preview(path: Path, *, limit_bytes: int) -> dict[str, Any] | None:
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return None
    try:
        data = path.read_bytes()[:limit_bytes]
    except OSError as exc:
        return {"path": str(path), "error": f"{type(exc).__name__}:{exc}"}
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("utf-16", errors="replace") if data.startswith((b"\xff\xfe", b"\xfe\xff")) else data.decode("utf-8", errors="replace")
    redacted = redact_text(text)
    return {
        "path": str(path),
        "bytesRead": len(data),
        "truncated": path.stat().st_size > len(data) if path.exists() else None,
        "preview": redacted[:4000],
    }


def collect_previews(inventories: Sequence[Mapping[str, Any]], *, limit_bytes: int) -> list[dict[str, Any]]:
    previews: list[dict[str, Any]] = []
    for inventory in inventories:
        for file_info in inventory.get("files", []):
            if not isinstance(file_info, Mapping):
                continue
            path_value = file_info.get("path")
            if not isinstance(path_value, str):
                continue
            preview = text_preview(Path(path_value), limit_bytes=limit_bytes)
            if preview is not None:
                previews.append(preview)
    return previews


def collect_targeted_previews(file_infos: Sequence[Mapping[str, Any]], *, limit_bytes: int) -> list[dict[str, Any]]:
    previews: list[dict[str, Any]] = []
    for file_info in file_infos:
        if not file_info.get("exists") or not file_info.get("isFile"):
            continue
        path_value = file_info.get("path")
        if not isinstance(path_value, str):
            continue
        preview = text_preview(Path(path_value), limit_bytes=limit_bytes)
        if preview is not None:
            previews.append(preview)
    return previews


def endpoint_inventory(*sources: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}

    def add(value: str, source: str) -> None:
        value = redact_text(value.strip().rstrip(".,;)'>]\""))
        if not value or len(value) < 4:
            return
        lower_value = value.lower()
        if "gmail.com" in lower_value or "outlook.com" in lower_value or "hotmail.com" in lower_value:
            return
        bucket = found.setdefault(value, {"value": value, "count": 0, "sources": []})
        bucket["count"] = int(bucket["count"]) + 1
        if source not in bucket["sources"]:
            bucket["sources"].append(source)

    def scan_text(text: str, source: str) -> None:
        for match in URL_RE.finditer(text):
            add(match.group(0), source)
        for match in HOST_RE.finditer(text):
            add(match.group(0), source)

    def scan_item(item: Any, source_hint: str = "") -> None:
        if isinstance(item, str):
            scan_text(item, source_hint)
        elif isinstance(item, Mapping):
            source = str(item.get("path") or item.get("source") or source_hint or "unknown")
            for value in item.values():
                scan_item(value, source)
        elif isinstance(item, Sequence) and not isinstance(item, (bytes, bytearray)):
            for child in item:
                scan_item(child, source_hint)

    for source in sources:
        scan_item(source)
    return sorted(found.values(), key=lambda item: (-int(item["count"]), str(item["value"]).lower()))


def parse_manifest_file(path: Path, *, entry_limit: int) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {"path": str(path), "status": "missing"}
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return {"path": str(path), "status": "failed", "error": f"{type(exc).__name__}:{exc}"}
    version = None
    entries: list[dict[str, Any]] = []
    total_size = 0
    malformed = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.lower().startswith("version "):
            version = stripped.split(" ", 1)[1]
            continue
        parts = stripped.rsplit(":", 2)
        if len(parts) != 3:
            malformed += 1
            continue
        name, digest, size_text = parts
        try:
            size = int(size_text)
        except ValueError:
            malformed += 1
            continue
        total_size += size
        if len(entries) < entry_limit:
            entries.append({"name": name, "digest": digest, "sizeBytes": size})
    largest = sorted(entries, key=lambda item: int(item["sizeBytes"]), reverse=True)[:10]
    return {
        "path": str(path),
        "status": "passed",
        "version": version,
        "lineCount": len(lines),
        "entryCount": sum(1 for line in lines if ":" in line),
        "malformedLineCount": malformed,
        "totalSizeBytesFromParsedEntries": total_size,
        "entriesCaptured": entries,
        "largestCapturedEntries": largest,
        "truncated": len([line for line in lines if ":" in line]) > len(entries),
    }


def manifest_inventory(paths: Sequence[Path], *, entry_limit: int) -> list[dict[str, Any]]:
    manifests: list[dict[str, Any]] = []
    for path in paths:
        name = path.name.lower()
        if name == "manifest64.txt" or name == "library_manifest.txt":
            manifests.append(parse_manifest_file(path, entry_limit=entry_limit))
    return manifests


def log_timeline(paths: Sequence[Path], *, max_events: int) -> dict[str, Any]:
    event_re = re.compile(r"^\[(?P<timestamp>[^\]]+)\]\s*(?P<message>.*)$")
    events: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    scanned_lines = 0
    for path in paths:
        if not path.exists() or not path.is_file() or path.suffix.lower() != ".log":
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines[-2000:]:
            scanned_lines += 1
            match = event_re.match(line)
            if not match:
                continue
            message = redact_text(match.group("message"))
            lower = message.lower()
            if "error" in lower or "failed" in lower:
                category = "error"
            elif "warning" in lower:
                category = "warning"
            elif "manifest" in lower:
                category = "manifest"
            elif "version" in lower:
                category = "version"
            elif "download" in lower or "received header" in lower:
                category = "download"
            elif "auth" in lower or "cookie" in lower or "login" in lower:
                category = "auth"
            elif "maintenance" in lower:
                category = "maintenance"
            else:
                category = "other"
            counts[category] = counts.get(category, 0) + 1
            events.append(
                {
                    "source": str(path),
                    "timestamp": match.group("timestamp"),
                    "category": category,
                    "message": message[:500],
                }
            )
    return {
        "status": "passed",
        "scannedLines": scanned_lines,
        "eventCount": len(events),
        "categoryCounts": counts,
        "latestEvents": events[-max_events:],
    }


def selection_server_summary(timeline: Mapping[str, Any]) -> dict[str, Any]:
    events = timeline.get("latestEvents") if isinstance(timeline.get("latestEvents"), list) else []
    endpoint_re = re.compile(r"\b(?P<host>\d{1,3}(?:\.\d{1,3}){3}):(?P<port>\d{1,5})\b")
    selection_events: list[dict[str, Any]] = []
    endpoints: dict[str, dict[str, Any]] = {}
    failures = 0
    successes = 0
    for event in events:
        if not isinstance(event, Mapping):
            continue
        message = str(event.get("message") or "")
        lower = message.lower()
        if "selection server" not in lower and "character selection" not in lower:
            continue
        matches = [f"{match.group('host')}:{match.group('port')}" for match in endpoint_re.finditer(message)]
        failed = "failed" in lower
        success = "connected" in lower and not failed
        failures += 1 if failed else 0
        successes += 1 if success else 0
        for endpoint in matches:
            bucket = endpoints.setdefault(endpoint, {"endpoint": endpoint, "count": 0, "failedCount": 0})
            bucket["count"] = int(bucket["count"]) + 1
            bucket["failedCount"] = int(bucket["failedCount"]) + (1 if failed else 0)
        selection_events.append(
            {
                "timestamp": event.get("timestamp"),
                "category": event.get("category"),
                "failed": failed,
                "success": success,
                "endpoints": matches,
                "message": message,
                "source": event.get("source"),
            }
        )
    status = "unknown"
    if successes:
        status = "connected"
    if failures and not successes:
        status = "failed"
    if any("using any address" in str(event.get("message", "")).lower() for event in selection_events):
        status = "failed-all-addresses"
    return {
        "status": status,
        "eventCount": len(selection_events),
        "failureCount": failures,
        "successCount": successes,
        "endpoints": list(endpoints.values()),
        "latestEvents": selection_events[-20:],
    }


def signature_trust_summary(signatures: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    signer_counts: dict[str, int] = {}
    unsigned_or_invalid: list[dict[str, Any]] = []
    for item in signatures:
        status = str(item.get("signatureStatus") or "Unknown")
        signer = str(item.get("signerCertificateSubject") or "<none>")
        status_counts[status] = status_counts.get(status, 0) + 1
        signer_counts[signer] = signer_counts.get(signer, 0) + 1
        if status.lower() != "valid":
            unsigned_or_invalid.append(
                {
                    "path": item.get("path"),
                    "signatureStatus": status,
                    "version": item.get("version"),
                    "productName": item.get("productName"),
                    "companyName": item.get("companyName"),
                }
            )
    return {
        "statusCounts": status_counts,
        "signerCounts": signer_counts,
        "nonValidCount": len(unsigned_or_invalid),
        "nonValid": unsigned_or_invalid[:80],
    }


def signature_and_version(paths: Iterable[Path]) -> list[dict[str, Any]]:
    path_list = [str(path) for path in paths if path.exists() and path.is_file()]
    if not path_list:
        return []
    encoded = json.dumps(path_list)
    script = rf"""
$paths = ConvertFrom-Json @'
{encoded}
'@
$items = foreach ($p in $paths) {{
  $item = Get-Item -LiteralPath $p
  $sig = Get-AuthenticodeSignature -LiteralPath $p
  [PSCustomObject]@{{
    path = $p
    version = $item.VersionInfo.FileVersion
    productVersion = $item.VersionInfo.ProductVersion
    productName = $item.VersionInfo.ProductName
    companyName = $item.VersionInfo.CompanyName
    originalFilename = $item.VersionInfo.OriginalFilename
    signatureStatus = [string]$sig.Status
    signerCertificateSubject = if ($sig.SignerCertificate) {{ $sig.SignerCertificate.Subject }} else {{ $null }}
    signerCertificateThumbprint = if ($sig.SignerCertificate) {{ $sig.SignerCertificate.Thumbprint }} else {{ $null }}
  }}
}}
$items | ConvertTo-Json -Depth 5
"""
    data = run_powershell_json(script, timeout_seconds=30.0)
    if isinstance(data, Mapping):
        return [dict(data)]
    if isinstance(data, list):
        return [dict(item) for item in data if isinstance(item, Mapping)]
    return []


def module_inventory(pid: int) -> dict[str, Any]:
    script = rf"""
$p = Get-Process -Id {int(pid)}
$p.Modules |
  Select-Object ModuleName,FileName,BaseAddress,ModuleMemorySize |
  ConvertTo-Json -Depth 4
"""
    data = run_powershell_json(script, timeout_seconds=30.0)
    if isinstance(data, Mapping):
        modules = [dict(data)]
    elif isinstance(data, list):
        modules = [dict(item) for item in data if isinstance(item, Mapping)]
    else:
        modules = []
    return {"pid": int(pid), "moduleCount": len(modules), "modules": modules[:300], "truncated": len(modules) > 300}


def _normalized_path_text(value: Any) -> str:
    return str(value or "").replace("/", "\\").rstrip("\\").lower()


def _path_under_text(path_text: str, root: Path | str | None) -> bool:
    root_text = _normalized_path_text(root)
    if not path_text or not root_text:
        return False
    return path_text == root_text or path_text.startswith(root_text + "\\")


def classify_module_origin(file_name: Any, *, install_roots: Sequence[Path]) -> str:
    path_text = _normalized_path_text(file_name)
    if not path_text:
        return "unknown"
    windows_root = Path(os.environ.get("WINDIR", r"C:\Windows"))
    temp_roots = [
        Path(value)
        for value in (os.environ.get("TEMP"), os.environ.get("TMP"), str(Path.home() / "AppData" / "Local" / "Temp"), r"C:\Windows\Temp")
        if value
    ]
    program_files_roots = [
        Path(value)
        for value in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"), r"C:\Program Files", r"C:\Program Files (x86)")
        if value
    ]
    if any(_path_under_text(path_text, root) for root in install_roots):
        return "glyph-install"
    if _path_under_text(path_text, windows_root):
        return "windows"
    if any(_path_under_text(path_text, root) for root in temp_roots):
        return "temp"
    if _path_under_text(path_text, Path.home()):
        return "user-profile"
    if any(_path_under_text(path_text, root) for root in program_files_roots):
        return "program-files"
    return "other"


def module_origin_summary(module_inventories: Sequence[Mapping[str, Any]], *, install_roots: Sequence[Path]) -> dict[str, Any]:
    category_counts: dict[str, int] = {}
    process_rows: list[dict[str, Any]] = []
    non_windows_non_glyph: list[dict[str, Any]] = []
    for inventory in module_inventories:
        modules = inventory.get("modules") if isinstance(inventory.get("modules"), list) else []
        process_counts: dict[str, int] = {}
        for module in modules:
            if not isinstance(module, Mapping):
                continue
            category = classify_module_origin(module.get("FileName"), install_roots=install_roots)
            category_counts[category] = category_counts.get(category, 0) + 1
            process_counts[category] = process_counts.get(category, 0) + 1
            if category not in {"windows", "glyph-install"}:
                non_windows_non_glyph.append(
                    {
                        "pid": inventory.get("pid"),
                        "moduleName": module.get("ModuleName"),
                        "fileName": module.get("FileName"),
                        "category": category,
                        "moduleMemorySize": module.get("ModuleMemorySize"),
                    }
                )
        process_rows.append(
            {
                "pid": inventory.get("pid"),
                "moduleCount": inventory.get("moduleCount"),
                "truncated": inventory.get("truncated"),
                "categoryCounts": process_counts,
                "nonWindowsNonGlyphCount": sum(
                    count for category, count in process_counts.items() if category not in {"windows", "glyph-install"}
                ),
            }
        )
    return {
        "processCount": len(process_rows),
        "totalModuleCount": sum(int(item.get("moduleCount") or 0) for item in module_inventories),
        "categoryCounts": category_counts,
        "nonWindowsNonGlyphCount": len(non_windows_non_glyph),
        "nonWindowsNonGlyphModules": non_windows_non_glyph[:100],
        "processes": process_rows,
    }


def registry_inventory() -> list[dict[str, Any]]:
    encoded = json.dumps(list(REGISTRY_CANDIDATE_PATHS))
    script = rf"""
$seedPaths = ConvertFrom-Json @'
{encoded}
'@
$expanded = New-Object System.Collections.Generic.List[string]
foreach ($path in $seedPaths) {{
  $expanded.Add([string]$path)
  if (Test-Path -LiteralPath $path) {{
    Get-ChildItem -LiteralPath $path -ErrorAction SilentlyContinue | Select-Object -First 80 | ForEach-Object {{
      $childPath = [string]$_.PSPath
      $expanded.Add($childPath)
      Get-ChildItem -LiteralPath $childPath -ErrorAction SilentlyContinue | Select-Object -First 80 | ForEach-Object {{
        $expanded.Add([string]$_.PSPath)
      }}
    }}
  }}
}}
$items = foreach ($path in ($expanded | Select-Object -Unique)) {{
  if (-not (Test-Path -LiteralPath $path)) {{
    [PSCustomObject]@{{ path = $path; exists = $false; values = @{{}}; subKeys = @() }}
    continue
  }}
  $props = Get-ItemProperty -LiteralPath $path -ErrorAction SilentlyContinue
  $values = @{{}}
  if ($props) {{
    foreach ($prop in $props.PSObject.Properties) {{
      if ($prop.Name -notlike 'PS*') {{
        $values[$prop.Name] = $prop.Value
      }}
    }}
  }}
  $subKeys = @(Get-ChildItem -LiteralPath $path -ErrorAction SilentlyContinue | Select-Object -First 80 -ExpandProperty PSChildName)
  [PSCustomObject]@{{ path = $path; exists = $true; values = $values; subKeys = $subKeys }}
}}
$items | ConvertTo-Json -Depth 8
"""
    data = run_powershell_json(script, timeout_seconds=30.0)
    if isinstance(data, Mapping):
        rows = [dict(data)]
    elif isinstance(data, list):
        rows = [dict(item) for item in data if isinstance(item, Mapping)]
    else:
        rows = []
    return [redact_jsonish(row) for row in rows]


def extract_ascii_strings(path: Path, *, max_hits: int) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {"path": str(path), "status": "missing"}
    try:
        data = path.read_bytes()
    except OSError as exc:
        return {"path": str(path), "status": "failed", "error": f"{type(exc).__name__}:{exc}"}
    ascii_strings = re.findall(rb"[\x20-\x7e]{6,}", data)
    utf16_strings = re.findall((rb"(?:[\x20-\x7e]\x00){6,}"), data)
    decoded: list[str] = [item.decode("ascii", errors="ignore") for item in ascii_strings[:20000]]
    decoded.extend(item.decode("utf-16le", errors="ignore") for item in utf16_strings[:20000])
    interesting: list[str] = []
    seen: set[str] = set()
    for value in decoded:
        if URL_RE.search(value) or HOST_RE.search(value) or REGISTRY_RE.search(value) or any(
            term in value.lower() for term in ("glyph", "trion", "rift", "patch", "manifest", "login", "auth", "crash", "update")
        ):
            clean = redact_text(value.strip())
            if clean and clean not in seen:
                seen.add(clean)
                interesting.append(clean)
                if len(interesting) >= max_hits:
                    break
    return {
        "path": str(path),
        "status": "passed",
        "totalAsciiStringsSampled": len(ascii_strings),
        "totalUtf16StringsSampled": len(utf16_strings),
        "interestingCount": len(interesting),
        "interestingStrings": interesting,
    }


def build_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Glyph forensics inventory",
        "",
        f"Generated: `{summary.get('generatedAtUtc')}`",
        f"Status: `{summary.get('status')}`",
        "",
        "## Running processes",
        "",
    ]
    for proc in summary.get("processes", []):
        if isinstance(proc, Mapping):
            lines.append(
                f"- PID `{proc.get('ProcessId')}` `{proc.get('Name')}` path=`{proc.get('ExecutablePath')}` parent=`{proc.get('ParentProcessId')}`"
            )
    lines.extend(["", "## Debugger-like process scan", ""])
    debugger_processes = summary.get("debuggerProcessScan") if isinstance(summary.get("debuggerProcessScan"), list) else []
    if debugger_processes:
        for proc in debugger_processes:
            if isinstance(proc, Mapping):
                lines.append(f"- PID `{proc.get('ProcessId')}` `{proc.get('Name')}` path=`{proc.get('ExecutablePath')}`")
    else:
        lines.append("- no known debugger-like process names were found")
    lines.extend(["", "## Active network connections", ""])
    network_connections = summary.get("activeNetworkConnections") if isinstance(summary.get("activeNetworkConnections"), list) else []
    if network_connections:
        for item in network_connections:
            if isinstance(item, Mapping):
                lines.append(
                    f"- PID `{item.get('OwningProcess')}` `{item.get('State')}` "
                    f"{item.get('LocalAddress')}:{item.get('LocalPort')} -> {item.get('RemoteAddress')}:{item.get('RemotePort')}"
                )
    else:
        lines.append("- no active Glyph-owned TCP connections were reported")
    lines.extend(["", "## Executables", ""])
    for item in summary.get("executableMetadata", []):
        if isinstance(item, Mapping):
            lines.append(f"- `{item.get('path')}` sha256=`{item.get('sha256')}`")
    lines.extend(["", "## Signature trust", ""])
    executable_trust = safe_mapping(summary.get("executableTrustSummary"))
    dependency_trust = safe_mapping(summary.get("dependencyTrustSummary"))
    lines.append(f"- executable signature statuses: `{executable_trust.get('statusCounts')}`")
    lines.append(f"- dependency signature statuses: `{dependency_trust.get('statusCounts')}`")
    lines.append(f"- dependency non-valid signatures: `{dependency_trust.get('nonValidCount')}`")
    module_summary = safe_mapping(summary.get("moduleOriginSummary"))
    lines.extend(["", "## Loaded module origin summary", ""])
    lines.append(f"- total modules: `{module_summary.get('totalModuleCount')}`")
    lines.append(f"- category counts: `{module_summary.get('categoryCounts')}`")
    lines.append(f"- non-Windows/non-Glyph module count: `{module_summary.get('nonWindowsNonGlyphCount')}`")
    lines.extend(["", "## PE summaries", ""])
    for item in summary.get("peSummaries", []):
        if isinstance(item, Mapping):
            lines.append(
                f"- `{item.get('path')}` format=`{item.get('format')}` machine=`{item.get('machineName')}` "
                f"subsystem=`{item.get('subsystemName')}` imports=`{item.get('importDllCount')}` tls=`{safe_mapping(item.get('tls')).get('status')}`"
            )
    lines.extend(["", "## Dependencies and targeted files", ""])
    lines.append(f"- dependencyMetadata count: `{len(summary.get('dependencyMetadata', []))}`")
    lines.append(
        f"- targetedFileInventory existing count: "
        f"`{len([item for item in summary.get('targetedFileInventory', []) if isinstance(item, Mapping) and item.get('exists')])}`"
    )
    lines.extend(["", "## Manifest summaries", ""])
    manifests = summary.get("manifestInventory") if isinstance(summary.get("manifestInventory"), list) else []
    if manifests:
        for item in manifests:
            if isinstance(item, Mapping):
                lines.append(f"- `{item.get('path')}` version=`{item.get('version')}` entries=`{item.get('entryCount')}`")
    else:
        lines.append("- none")
    lines.extend(["", "## Endpoint inventory", ""])
    endpoints = summary.get("endpointInventory") if isinstance(summary.get("endpointInventory"), list) else []
    for item in endpoints[:25]:
        if isinstance(item, Mapping):
            lines.append(f"- `{item.get('value')}` count=`{item.get('count')}`")
    if not endpoints:
        lines.append("- none")
    timeline = safe_mapping(summary.get("logTimeline"))
    lines.extend(["", "## Log timeline", ""])
    lines.append(f"- events: `{timeline.get('eventCount')}`")
    lines.append(f"- categories: `{timeline.get('categoryCounts')}`")
    selection = safe_mapping(summary.get("selectionServerSummary"))
    lines.append(f"- selection server status: `{selection.get('status')}` failures=`{selection.get('failureCount')}`")
    registry_rows = summary.get("registryInventory") if isinstance(summary.get("registryInventory"), list) else []
    existing_registry = [item for item in registry_rows if isinstance(item, Mapping) and item.get("exists")]
    lines.extend(["", "## Registry keys", ""])
    if existing_registry:
        for item in existing_registry:
            value_count = len(item.get("values", {})) if isinstance(item.get("values"), Mapping) else 0
            subkey_count = len(item.get("subKeys", [])) if isinstance(item.get("subKeys"), list) else 0
            lines.append(f"- `{item.get('path')}` values=`{value_count}` subKeys=`{subkey_count}`")
    else:
        lines.append("- none of the seeded Glyph/Trion registry keys existed")
    lines.extend(["", "## Startup/service/install inventory", ""])
    for label, key in (
        ("Services", "serviceInventory"),
        ("Scheduled tasks", "scheduledTaskInventory"),
        ("Autoruns", "autorunInventory"),
        ("Uninstall entries", "uninstallInventory"),
    ):
        rows = summary.get(key) if isinstance(summary.get(key), list) else []
        lines.append(f"- {label}: `{len(rows)}`")
    lines.extend(["", "## Safety", ""])
    safety = safe_mapping(summary.get("safety"))
    for key in (
        "debuggerAttachedByThisHelper",
        "processMemoryDumped",
        "processMemoryRead",
        "processModuleEnumeration",
        "debuggerAttach",
        "tokensRedacted",
    ):
        lines.append(f"- {key}: `{safety.get(key)}`")
    if summary.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- `{item}`" for item in summary.get("warnings", []))
    if summary.get("errors"):
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- `{item}`" for item in summary.get("errors", []))
    return "\n".join(lines) + "\n"


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.repo_root).resolve() if args.repo_root else repo_root()
    output_root = Path(args.output_root).resolve() if args.output_root else root / "scripts" / "captures"
    run_dir = output_root / f"glyph-forensics-inventory-{utc_stamp()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    processes = process_inventory()
    debugger_processes = debugger_process_scan()
    glyph_processes = [proc for proc in processes if str(proc.get("Name", "")).lower().startswith("glyph")]
    install_root = install_root_from_processes(glyph_processes)
    targeted_paths = targeted_glyph_paths(glyph_processes)
    targeted_files = targeted_file_inventory(targeted_paths)
    network_connections = active_network_connections(glyph_processes)
    services = service_inventory()
    scheduled_tasks = scheduled_task_inventory()
    autoruns = autorun_inventory()
    uninstall_entries = uninstall_inventory()
    roots = likely_roots(glyph_processes)
    inventories = [walk_interesting_files(root_path, max_files=int(args.max_files_per_root)) for root_path in roots]
    exe_paths: list[Path] = []
    for proc in glyph_processes:
        exe = proc.get("ExecutablePath")
        if isinstance(exe, str) and exe:
            exe_paths.append(Path(exe))
    for inventory in inventories:
        for file_info in inventory.get("files", []):
            if isinstance(file_info, Mapping) and str(file_info.get("suffix", "")).lower() == ".exe":
                exe_paths.append(Path(str(file_info.get("path"))))
    unique_exes: list[Path] = []
    seen_exes: set[str] = set()
    for path in exe_paths:
        key = str(path).lower()
        if key not in seen_exes:
            seen_exes.add(key)
            unique_exes.append(path)
    executable_metadata = [file_metadata(path, hash_file=True) for path in unique_exes]
    signatures = signature_and_version(unique_exes)
    pe_summaries = [
        parse_pe_metadata(path, max_import_functions_per_dll=int(args.max_import_functions_per_dll))
        for path in unique_exes
    ]
    dependency_paths: list[Path] = []
    for inventory in inventories:
        for file_info in inventory.get("files", []):
            if isinstance(file_info, Mapping) and str(file_info.get("suffix", "")).lower() == ".dll" and file_info.get("exists"):
                dependency_paths.append(Path(str(file_info.get("path"))))
    for file_info in targeted_files:
        if str(file_info.get("suffix", "")).lower() == ".dll" and file_info.get("exists"):
            dependency_paths.append(Path(str(file_info.get("path"))))
    unique_dependency_paths: list[Path] = []
    seen_dependencies: set[str] = set()
    for path in dependency_paths:
        key = str(path).lower()
        if key not in seen_dependencies:
            seen_dependencies.add(key)
            unique_dependency_paths.append(path)
    dependency_metadata = [file_metadata(path, hash_file=True) for path in unique_dependency_paths]
    dependency_signatures = signature_and_version(unique_dependency_paths)
    executable_trust = signature_trust_summary(signatures)
    dependency_trust = signature_trust_summary(dependency_signatures)
    dependency_pe_summaries = [
        parse_pe_metadata(path, max_import_functions_per_dll=min(80, int(args.max_import_functions_per_dll)))
        for path in unique_dependency_paths[:80]
    ]
    registry = registry_inventory()
    debug_checks = []
    modules = []
    for proc in glyph_processes:
        try:
            pid = int(proc.get("ProcessId"))
        except (TypeError, ValueError):
            continue
        debug_checks.append({"pid": pid, **debugger_indicators(pid)})
        modules.append(module_inventory(pid))
    module_roots = [root for root in (install_root, Path(r"C:\Program Files (x86)\Glyph"), Path(r"C:\Program Files\Glyph")) if root]
    module_summary = module_origin_summary(modules, install_roots=module_roots)
    string_summaries = [extract_ascii_strings(path, max_hits=int(args.max_string_hits)) for path in unique_exes[:20]]
    previews = collect_previews(inventories, limit_bytes=int(args.text_preview_bytes))
    targeted_previews = collect_targeted_previews(targeted_files, limit_bytes=int(args.text_preview_bytes))
    manifests = manifest_inventory(targeted_paths, entry_limit=int(args.manifest_entry_limit))
    timeline = log_timeline(targeted_paths, max_events=int(args.log_timeline_events))
    selection_summary = selection_server_summary(timeline)
    endpoints = endpoint_inventory(previews, targeted_previews, string_summaries, registry, uninstall_entries, autoruns)
    safety = base_safety()
    safety.update(
        {
            "readOnlyForensics": True,
            "debuggerAttachedByThisHelper": False,
            "debuggerAttach": False,
            "processMemoryDumped": False,
            "processMemoryRead": False,
            "tokensRedacted": True,
            "credentialExtractionAttempted": False,
            "x64dbgAttach": False,
            "targetMemoryBytesRead": False,
            "targetMemoryBytesWritten": False,
            "processModuleEnumeration": bool(modules),
        }
    )
    warnings: list[str] = []
    if not glyph_processes:
        warnings.append("glyph-process-not-found")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": KIND,
        "generatedAtUtc": utc_iso(),
        "status": "passed",
        "repoRoot": str(root),
        "input": {
            "maxFilesPerRoot": int(args.max_files_per_root),
            "textPreviewBytes": int(args.text_preview_bytes),
            "maxStringHits": int(args.max_string_hits),
            "maxImportFunctionsPerDll": int(args.max_import_functions_per_dll),
            "logTimelineEvents": int(args.log_timeline_events),
            "manifestEntryLimit": int(args.manifest_entry_limit),
        },
        "processes": processes,
        "debuggerProcessScan": debugger_processes,
        "activeNetworkConnections": network_connections,
        "serviceInventory": services,
        "scheduledTaskInventory": scheduled_tasks,
        "autorunInventory": autoruns,
        "uninstallInventory": uninstall_entries,
        "debuggerIndicators": debug_checks,
        "moduleInventory": modules,
        "moduleOriginSummary": module_summary,
        "candidateRoots": [str(item) for item in roots],
        "fileInventories": inventories,
        "targetedFileInventory": targeted_files,
        "executableMetadata": executable_metadata,
        "signaturesAndVersions": signatures,
        "executableTrustSummary": executable_trust,
        "peSummaries": pe_summaries,
        "dependencyMetadata": dependency_metadata,
        "dependencySignaturesAndVersions": dependency_signatures,
        "dependencyTrustSummary": dependency_trust,
        "dependencyPeSummaries": dependency_pe_summaries,
        "registryInventory": registry,
        "textPreviewsRedacted": previews,
        "targetedTextPreviewsRedacted": targeted_previews,
        "staticStringSummaries": string_summaries,
        "manifestInventory": manifests,
        "logTimeline": timeline,
        "selectionServerSummary": selection_summary,
        "endpointInventory": endpoints,
        "warnings": warnings,
        "errors": [],
        "safety": safety,
        "artifacts": {
            "runDirectory": str(run_dir),
            "summaryJson": str(run_dir / "summary.json"),
            "summaryMarkdown": str(run_dir / "summary.md"),
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect safe read-only Glyph launcher forensics with redaction")
    parser.add_argument("--repo-root")
    parser.add_argument("--output-root")
    parser.add_argument("--max-files-per-root", type=int, default=DEFAULT_MAX_FILES_PER_ROOT)
    parser.add_argument("--text-preview-bytes", type=int, default=DEFAULT_TEXT_PREVIEW_BYTES)
    parser.add_argument("--max-string-hits", type=int, default=DEFAULT_MAX_STRING_HITS)
    parser.add_argument("--max-import-functions-per-dll", type=int, default=DEFAULT_MAX_IMPORT_FUNCTIONS_PER_DLL)
    parser.add_argument("--log-timeline-events", type=int, default=DEFAULT_LOG_TIMELINE_EVENTS)
    parser.add_argument("--manifest-entry-limit", type=int, default=DEFAULT_MANIFEST_ENTRY_LIMIT)
    parser.add_argument("--json", action="store_true")
    return parser


def compact(summary: Mapping[str, Any]) -> dict[str, Any]:
    artifacts = safe_mapping(summary.get("artifacts"))
    glyph_processes = [proc for proc in summary.get("processes", []) if isinstance(proc, Mapping) and str(proc.get("Name", "")).lower().startswith("glyph")]
    selection = safe_mapping(summary.get("selectionServerSummary"))
    executable_trust = safe_mapping(summary.get("executableTrustSummary"))
    dependency_trust = safe_mapping(summary.get("dependencyTrustSummary"))
    module_summary = safe_mapping(summary.get("moduleOriginSummary"))
    return {
        "status": summary.get("status"),
        "kind": summary.get("kind"),
        "glyphProcessCount": len(glyph_processes),
        "glyphPids": [proc.get("ProcessId") for proc in glyph_processes],
        "candidateRootCount": len(summary.get("candidateRoots", [])),
        "executableCount": len(summary.get("executableMetadata", [])),
        "peSummaryCount": len(summary.get("peSummaries", [])),
        "dependencyCount": len(summary.get("dependencyMetadata", [])),
        "targetedFileCount": len([item for item in summary.get("targetedFileInventory", []) if isinstance(item, Mapping) and item.get("exists")]),
        "manifestCount": len([item for item in summary.get("manifestInventory", []) if isinstance(item, Mapping) and item.get("status") == "passed"]),
        "endpointCount": len(summary.get("endpointInventory", [])),
        "selectionServerStatus": selection.get("status"),
        "selectionServerFailureCount": selection.get("failureCount"),
        "executableSignatureStatusCounts": executable_trust.get("statusCounts"),
        "dependencySignatureStatusCounts": dependency_trust.get("statusCounts"),
        "dependencyNonValidSignatureCount": dependency_trust.get("nonValidCount"),
        "loadedModuleTotalCount": module_summary.get("totalModuleCount"),
        "loadedModuleOriginCounts": module_summary.get("categoryCounts"),
        "nonWindowsNonGlyphModuleCount": module_summary.get("nonWindowsNonGlyphCount"),
        "debuggerLikeProcessCount": len(summary.get("debuggerProcessScan", [])),
        "activeNetworkConnectionCount": len(summary.get("activeNetworkConnections", [])),
        "serviceCount": len(summary.get("serviceInventory", [])),
        "scheduledTaskCount": len(summary.get("scheduledTaskInventory", [])),
        "autorunCount": len(summary.get("autorunInventory", [])),
        "uninstallEntryCount": len(summary.get("uninstallInventory", [])),
        "registryKeyCount": len([item for item in summary.get("registryInventory", []) if isinstance(item, Mapping) and item.get("exists")]),
        "textPreviewCount": len(summary.get("textPreviewsRedacted", [])),
        "summaryJson": artifacts.get("summaryJson"),
        "summaryMarkdown": artifacts.get("summaryMarkdown"),
        "warnings": summary.get("warnings", []),
        "errors": summary.get("errors", []),
        "safety": {
            key: safe_mapping(summary.get("safety")).get(key)
            for key in (
                "debuggerAttachedByThisHelper",
                "processMemoryDumped",
                "processMemoryRead",
                "processModuleEnumeration",
                "tokensRedacted",
            )
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    summary = build_report(args)
    artifacts = safe_mapping(summary.get("artifacts"))
    write_json(Path(str(artifacts["summaryJson"])), summary)
    Path(str(artifacts["summaryMarkdown"])).write_text(build_markdown(summary), encoding="utf-8")
    print(json.dumps(compact(summary)) if args.json else json.dumps(compact(summary), indent=2))
    return 0 if summary.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
