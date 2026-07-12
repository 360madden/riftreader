#!/usr/bin/env python3
"""CLI tool for reading Lua globals from RIFT process memory.

Usage:
    python -m lua_memory --pid 36332
    python -m lua_memory --pid 36332 --global RiftReaderApiProbe_Player
    python -m lua_memory --pid 36332 --all --json
    python -m lua_memory --pid 36332 --list
    python -m lua_memory --pid 36332 --scan-only --verbose
"""

import argparse
import json
import sys
import time

# Add parent dir to path so we can import lua_memory
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent.parent))

from lua_memory.process import ProcessMemory
from lua_memory.scanner import LuaStateFinder
from lua_memory.lua_types import LuaType


def main():
    parser = argparse.ArgumentParser(
        description="Read Lua globals from RIFT process memory"
    )
    parser.add_argument("--pid", type=int, required=True, help="RIFT process ID")
    parser.add_argument("--global", dest="global_name", help="Read a specific global by name")
    parser.add_argument("--all", action="store_true", help="Read all globals")
    parser.add_argument("--list", action="store_true", help="List all global names")
    parser.add_argument("--strings-only", action="store_true", help="Show only string globals")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--scan-only", action="store_true", help="Just scan, don't parse globals")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    pm = ProcessMemory(args.pid)
    finder = LuaStateFinder(pm)

    try:
        # Phase 1: Scan for Lua strings
        t0 = time.time()
        strings = finder.scan_for_lua_strings(verbose=args.verbose)
        scan_time = time.time() - t0

        if args.scan_only:
            print(f"Scan complete: {len(strings)} Lua strings found in {scan_time:.1f}s")
            for s in strings[:20]:
                print(f"  [{s.string_object_address:#x}] {s.name}")
            return

        if not strings:
            print("No Lua strings found. Is the addon loaded?", file=sys.stderr)
            print("Try: /reloadui in RIFT, then run this again.", file=sys.stderr)
            sys.exit(1)

        # Phase 2: Find global table
        gt = finder.find_global_table(verbose=args.verbose)
        if not gt:
            print("Could not find global table (_G).", file=sys.stderr)
            sys.exit(1)

        # Phase 3: Read globals
        globals_dict = finder.read_globals(verbose=args.verbose)

        # Output
        if args.global_name:
            entry = globals_dict.get(args.global_name)
            if not entry:
                print(f"Global '{args.global_name}' not found.", file=sys.stderr)
                print(f"Available globals ({len(globals_dict)}):", file=sys.stderr)
                for name in sorted(globals_dict.keys())[:20]:
                    print(f"  {name} ({globals_dict[name].value_type})", file=sys.stderr)
                sys.exit(1)

            if entry.value_tt == LuaType.TSTRING:
                val = finder.read_global_string(args.global_name)
                if args.json:
                    print(json.dumps({"name": args.global_name, "type": "string", "value": val}))
                else:
                    print(val or "(empty)")
            elif entry.value_tt == LuaType.TNUMBER:
                raw_bytes = entry.value_raw.to_bytes(8, "little")
                import struct
                val = struct.unpack("d", raw_bytes)[0]
                if args.json:
                    print(json.dumps({"name": args.global_name, "type": "number", "value": val}))
                else:
                    print(f"{args.global_name} = {val}")
            else:
                if args.json:
                    print(json.dumps({
                        "name": args.global_name,
                        "type": entry.value_type,
                        "address": hex(entry.value_raw),
                    }))
                else:
                    print(f"{args.global_name} = <{entry.value_type}> at {hex(entry.value_raw)}")

        elif args.all or args.list:
            if args.list:
                names = sorted(globals_dict.keys())
                if args.json:
                    print(json.dumps(names))
                else:
                    for name in names:
                        entry = globals_dict[name]
                        print(f"  {name} ({entry.value_type})")
                print(f"\n{len(names)} globals total")
            else:
                results = {}
                for name, entry in sorted(globals_dict.items()):
                    if args.strings_only and entry.value_tt != LuaType.TSTRING:
                        continue
                    if entry.value_tt == LuaType.TSTRING:
                        val = finder.read_global_string(name)
                        results[name] = val
                    elif entry.value_tt == LuaType.TNUMBER:
                        raw_bytes = entry.value_raw.to_bytes(8, "little")
                        import struct
                        results[name] = struct.unpack("d", raw_bytes)[0]
                    elif entry.value_tt == LuaType.TBOOLEAN:
                        results[name] = bool(entry.value_raw)
                    elif entry.value_tt == LuaType.TNIL:
                        results[name] = None
                    else:
                        results[name] = f"<{entry.value_type}>"

                if args.json:
                    print(json.dumps(results, indent=2, default=str))
                else:
                    for name, val in results.items():
                        if isinstance(val, str) and len(val) > 120:
                            print(f"  {name}: {val[:120]}...")
                        else:
                            print(f"  {name}: {val}")
                    print(f"\n{len(results)} globals")

        else:
            # Default: show summary
            print(f"Lua state found at global table: {hex(gt)}")
            print(f"Total globals: {len(globals_dict)}")
            string_globals = [n for n, e in globals_dict.items() if e.value_tt == LuaType.TSTRING]
            print(f"String globals: {len(string_globals)}")
            print(f"\nUse --all, --list, or --global <name> to read values.")

    finally:
        pm.close()


if __name__ == "__main__":
    main()
