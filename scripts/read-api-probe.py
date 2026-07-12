#!/usr/bin/env python3
"""
Read RiftReaderApiProbe globals from RIFT's Lua string heap.

Searches for known value prefixes in committed private memory regions:
  - RiftReaderApiProbe_Player:    "version=2|seq="
  - RiftReaderApiProbe_Target:    "version=2|seq=" (separate instance)
  - RiftReaderApiProbe_Environment: "version=2|..."
  - RiftReaderApiProbe_Nearby:    "version=2|count="
  - RiftReaderApiProbe_Live:      "RRAPICOORD1|schema=1"

Usage:
    python read-api-probe.py --pid <pid>
    python read-api-probe.py --pid <pid> --json
    python read-api-probe.py --pid <pid> --global Player
"""

import argparse
import ctypes
import json
import struct
import sys

kernel32 = ctypes.windll.kernel32
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
ACCESS = PROCESS_VM_READ | PROCESS_QUERY_INFORMATION


class MBI(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", ctypes.c_uint32),
        ("RegionSize", ctypes.c_size_t),
        ("State", ctypes.c_uint32),
        ("Protect", ctypes.c_uint32),
        ("Type", ctypes.c_uint32),
    ]


def read_bytes(handle, address, size):
    buf = ctypes.create_string_buffer(size)
    br = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(handle, ctypes.c_void_p(address), buf, size, ctypes.byref(br))
    if not ok or br.value != size:
        return None
    return buf.raw


def find_null_terminated(data, start_pos):
    """Find the end of a null-terminated string starting at start_pos."""
    end = start_pos
    while end < len(data) and data[end] != 0:
        end += 1
    return data[start_pos:end]


def search_region(handle, needle, region_start, region_size):
    """Search a single memory region for needle and return the null-terminated string containing it."""
    CHUNK = 0x100000
    for offset in range(0, region_size, CHUNK):
        size = min(CHUNK, region_size - offset)
        data = read_bytes(handle, region_start + offset, size)
        if not data:
            continue
        idx = 0
        while True:
            pos = data.find(needle, idx)
            if pos == -1:
                break
            # Find the start of the string (scan backward to null or start)
            str_start = pos
            while str_start > 0 and data[str_start - 1] != 0:
                str_start -= 1
            # Find the end of the string
            str_end = pos + len(needle)
            while str_end < len(data) and data[str_end] != 0:
                str_end += 1
            content = data[str_start:str_end]
            try:
                text = content.decode("utf-8", errors="replace")
                if needle.decode("utf-8") in text:
                    return region_start + offset + str_start, text
            except Exception:
                pass
            idx = pos + 1
    return None, None


def search_all_heaps(handle, needle):
    """Search all committed private heap regions for a string containing needle."""
    addr = 0
    while addr < 0x7FFFFFFFFFFFFFFF:
        mbi = MBI()
        r = kernel32.VirtualQueryEx(handle, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi))
        if r == 0:
            break
        if mbi.State == 0x1000 and mbi.Type == 0x20000 and mbi.RegionSize > 0x10000:
            start = mbi.BaseAddress or 0
            found_addr, found_text = search_region(handle, needle, start, mbi.RegionSize)
            if found_addr:
                return found_addr, found_text
        addr = (mbi.BaseAddress or 0) + mbi.RegionSize
    return None, None


def search_all_heaps_all(handle, needle):
    """Search all committed private heap regions and return ALL matches."""
    results = []
    addr = 0
    while addr < 0x7FFFFFFFFFFFFFFF:
        mbi = MBI()
        r = kernel32.VirtualQueryEx(handle, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi))
        if r == 0:
            break
        if mbi.State == 0x1000 and mbi.Type == 0x20000 and mbi.RegionSize > 0x10000:
            start = mbi.BaseAddress or 0
            CHUNK = 0x100000
            for offset in range(0, mbi.RegionSize, CHUNK):
                size = min(CHUNK, mbi.RegionSize - offset)
                data = read_bytes(handle, start + offset, size)
                if not data:
                    continue
                idx = 0
                while True:
                    pos = data.find(needle, idx)
                    if pos == -1:
                        break
                    str_start = pos
                    while str_start > 0 and data[str_start - 1] != 0:
                        str_start -= 1
                    str_end = pos + len(needle)
                    while str_end < len(data) and data[str_end] != 0:
                        str_end += 1
                    content = data[str_start:str_end]
                    try:
                        text = content.decode("utf-8", errors="replace")
                        if needle.decode("utf-8") in text:
                            results.append((start + offset + str_start, text))
                    except Exception:
                        pass
                    idx = pos + 1
        addr = (mbi.BaseAddress or 0) + mbi.RegionSize
    return results


def parse_player_string(text):
    """Parse pipe-delimited player string into dict."""
    result = {}
    for part in text.split("|"):
        if "=" in part:
            key, _, val = part.partition("=")
            result[key.strip()] = val.strip()
    return result


def parse_nearby_string(text):
    """Parse pipe-delimited nearby units string."""
    parts = text.split("|")
    if len(parts) < 3:
        return []
    units = []
    i = 2  # skip "version=2" and "count=N"
    while i < len(parts):
        if i + 10 <= len(parts):
            units.append({
                "index": parts[i],
                "id": parts[i + 1],
                "name": parts[i + 2],
                "level": parts[i + 3],
                "calling": parts[i + 4],
                "relation": parts[i + 5],
                "x": parts[i + 6],
                "y": parts[i + 7],
                "z": parts[i + 8],
                "health": parts[i + 9],
                "healthMax": parts[i + 10],
            })
            i += 11
        else:
            break
    return units


def parse_abilities_string(text):
    """Parse pipe-delimited abilities string.

    Format: RRAPICAPABILITIES|count=N|index|id|name|cd|cast|rangeMax|rangeMin|weapon|channeled|passive|autoattack|cdRemain|index|id|...
    Each ability = 12 fields (index, id, name, cooldown, castingTime, rangeMax, rangeMin, weapon, channeled, passive, autoattack, cooldownRemaining)
    """
    parts = text.split("|")
    if len(parts) < 3:
        return []
    try:
        count = int(parts[1].split("=", 1)[1])
    except (ValueError, IndexError):
        return []
    abilities = []
    i = 2
    FIELDS_PER_ABILITY = 12
    while i + FIELDS_PER_ABILITY <= len(parts):
        abilities.append({
            "index": parts[i],
            "id": parts[i + 1],
            "name": parts[i + 2],
            "cooldown": parts[i + 3],
            "castingTime": parts[i + 4],
            "rangeMax": parts[i + 5],
            "rangeMin": parts[i + 6],
            "weapon": parts[i + 7],
            "channeled": parts[i + 8],
            "passive": parts[i + 9],
            "autoattack": parts[i + 10],
            "cooldownRemaining": parts[i + 11],
        })
        i += FIELDS_PER_ABILITY
    return abilities


def parse_stats_string(text):
    """Parse pipe-delimited stats string. Format: RRAPISTATS|key=value|..."""
    parts = text.split("|")
    stats = {}
    for part in parts:
        if "=" in part:
            k, v = part.split("=", 1)
            if k != "RRAPISTATS":
                stats[k] = v
    return stats


def main():
    parser = argparse.ArgumentParser(description="Read RiftReaderApiProbe globals from RIFT memory")
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--global", dest="global_name", help="Read a specific global (Player, Target, Environment, Nearby, Live)")
    parser.add_argument("--all", action="store_true", help="Show all matches (debug)")
    args = parser.parse_args()

    handle = kernel32.OpenProcess(ACCESS, False, args.pid)
    if not handle:
        print("Cannot open process", file=sys.stderr)
        sys.exit(1)

    # Map global names to their value prefixes
    # Unique-prefix globals: search directly
    UNIQUE_MAP = {
        "Player": b"version=2|seq=",
        "Target": b"present=1|sampledAt=",
        "Environment": b"secure=",
        "Stats": b"RRAPISTATS|",
        "Live": b"RRAPICOORD1|schema=1",
    }

    def pick_latest(matches):
        """From all matches, return the cleanest one with the highest sampledAt or seq."""
        if not matches:
            return None
        best = None
        best_val = -2
        for addr, text in matches:
            if "<" in text or ">" in text or "\ufffd" in text:
                continue
            if not text.startswith("version=2") and not text.startswith("present=1") and not text.startswith("RRAPICOORD1") and not text.startswith("secure=") and not text.startswith("RRAPISTATS") and not text.startswith("RRAPICAPABILITIES"):
                continue
            val = -1
            for part in text.split("|"):
                if part.startswith("sampledAt="):
                    try:
                        val = float(part.split("=", 1)[1])
                    except (ValueError, IndexError):
                        pass
                elif part.startswith("seq="):
                    try:
                        val = int(part.split("=", 1)[1])
                    except (ValueError, IndexError):
                        pass
            if val > best_val:
                best_val = val
                best = text
        return best

    def classify_count_match(text):
        """Classify a version=2|count=... string as Nearby or Abilities by content."""
        if "|friendly|" in text or "|hostile|" in text:
            return "Nearby"
        return "Abilities"

    if args.global_name:
        match = [k for k in UNIQUE_MAP if args.global_name.lower() in k.lower()]
        if not match and args.global_name.lower() in ("nearby", "abilities"):
            match = [args.global_name.capitalize()]
        if not match:
            print(f"Unknown global: {args.global_name}", file=sys.stderr)
            sys.exit(1)
        targets = {k: UNIQUE_MAP.get(k, b"version=2|count=") for k in match}
    else:
        targets = dict(UNIQUE_MAP)

    results = {}

    # Search unique-prefix globals
    for global_name, prefix in targets.items():
        if global_name in ("Nearby", "Abilities"):
            continue  # handled below
        matches = search_all_heaps_all(handle, prefix)
        results[global_name] = pick_latest(matches)

    # Search version=2|count= once, classify as Nearby or Abilities
    count_matches = search_all_heaps_all(handle, b"version=2|count=")
    nearby_candidates = []
    abilities_candidates = []
    for addr, text in count_matches:
        if "<" in text or ">" in text or "\ufffd" in text:
            continue
        if not text.startswith("version=2|count="):
            continue
        if classify_count_match(text) == "Abilities":
            abilities_candidates.append((addr, text))
        else:
            nearby_candidates.append((addr, text))

    # Also search for RRAPICAPABILITIES| (unique prefix for abilities)
    cap_matches = search_all_heaps_all(handle, b"RRAPICAPABILITIES|")
    for addr, text in cap_matches:
        if "<" in text or ">" in text or "\ufffd" in text:
            continue
        if text.startswith("RRAPICAPABILITIES|"):
            abilities_candidates.append((addr, text))

    show_all = args.global_name is None or args.global_name.lower() in ("nearby", "abilities")
    if show_all:
        if args.global_name is None or args.global_name.lower() == "nearby":
            results["Nearby"] = pick_latest(nearby_candidates)
        if args.global_name is None or args.global_name.lower() == "abilities":
            results["Abilities"] = pick_latest(abilities_candidates)

    kernel32.CloseHandle(handle)

    if args.json:
        output = {}
        for k, v in results.items():
            if v is None:
                output[k] = None
            elif k in ("Player", "Target"):
                output[k] = parse_player_string(v)
            elif k == "Environment":
                output[k] = parse_player_string(v)
            elif k == "Nearby":
                output[k] = parse_nearby_string(v)
            elif k == "Abilities":
                output[k] = parse_abilities_string(v)
            elif k == "Stats":
                output[k] = parse_stats_string(v)
            else:
                output[k] = v
        print(json.dumps(output, indent=2))
    else:
        for k, v in results.items():
            if v:
                print(f"\n=== {k} ===")
                print(v[:500])
            else:
                print(f"\n=== {k} === (not found)")


if __name__ == "__main__":
    main()
