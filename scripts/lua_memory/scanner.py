"""Lua state finder — locates lua_State and global table in RIFT process.

Strategy (dual-mode):
1. API-string mode (Assets repo approach): Scan .rdata for Inspect.Unit.Detail,
   resolve handler → registry → unit object → coordinates
2. Heap-scan mode (legacy): Scan heap for Lua string objects containing known
   addon global names, walk string hash chain to find global table

The API-string mode is more robust because it uses stable binary anchors
rather than dynamic heap layout.
"""

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .process import ProcessMemory
from .lua_types import Lua51, LuaType, LuaTValue


SIGNATURE_DB_PATH = Path(__file__).parent / "rift-x64-signatures.json"


@dataclass
class FoundString:
    """A Lua string found in memory."""
    name: str
    char_address: int
    string_object_address: int
    header: object  # LuaStringHeader


@dataclass
class GlobalEntry:
    """A parsed global variable from the _G table."""
    name: str
    value_tt: int
    value_raw: int
    value_type: str


class LuaStateFinder:
    """Locates and parses Lua 5.1 interpreter state in RIFT process."""

    # Known patterns to search for when finding Lua strings
    # These are prefixes of addon global variable names
    SEARCH_PREFIXES = [
        b"RiftReaderApiProbe_",
        b"RRAPICOORD1",
    ]

    # Minimum string length for a valid addon global
    MIN_GLOBAL_NAME_LEN = 8
    MAX_GLOBAL_NAME_LEN = 200

    def __init__(self, pm: ProcessMemory):
        self.pm = pm
        self._cached_globals: dict[str, GlobalEntry] = {}
        self._global_table_addr: Optional[int] = None
        self._string_table_addrs: list[int] = []
        self._found_strings: list[FoundString] = []
        self._scan_time: float = 0
        self._signature_db: Optional[dict] = None
        self._api_anchors: dict[str, dict] = {}

    def _load_signature_db(self) -> dict:
        """Load the binary signature database from the Assets repo."""
        if self._signature_db is None:
            if SIGNATURE_DB_PATH.exists():
                self._signature_db = json.loads(SIGNATURE_DB_PATH.read_text(encoding="utf-8"))
                for anchor in self._signature_db.get("Anchors", []):
                    self._api_anchors[anchor["Name"]] = anchor
            else:
                self._signature_db = {}
        return self._signature_db

    def find_api_anchor(self, name: str, verbose: bool = False) -> Optional[int]:
        """Find an API anchor by scanning for its signature in the binary.

        Returns the runtime virtual address of the anchor.
        """
        self._load_signature_db()
        anchor = self._api_anchors.get(name)
        if not anchor:
            if verbose:
                print(f"  Anchor '{name}' not found in signature database")
            return None

        # Convert signature hex to bytes
        sig_hex = anchor["SignatureHex"]
        sig_bytes = bytes.fromhex(sig_hex.replace("??", "00").replace(" ", ""))

        # Scan for the pattern
        if verbose:
            print(f"  Scanning for anchor '{name}' ({sig_hex})...")

        for addr in self.pm.scan_pattern(sig_bytes):
            if verbose:
                print(f"  Found '{name}' at {addr:#x}")
            return addr

        if verbose:
            print(f"  Anchor '{name}' not found in memory")
        return None

    def find_registry_base(self, verbose: bool = False) -> Optional[int]:
        """Find the unit registry base address using the Assets repo approach.

        Strategy:
        1. Find the Inspect.Unit.Detail string
        2. Find the registry accessor instruction
        3. Resolve the LEA RIP-relative address to get the registry base
        """
        self._load_signature_db()

        # Find the registry accessor instruction
        accessor = self._api_anchors.get("registry-accessor")
        if not accessor:
            if verbose:
                print("  registry-accessor anchor not found in signature database")
            return None

        # Scan for the accessor instruction pattern
        sig_hex = accessor["SignatureHex"]
        sig_bytes = bytes.fromhex(sig_hex.replace("??", "00").replace(" ", ""))

        if verbose:
            print(f"  Scanning for registry accessor ({sig_hex})...")

        for addr in self.pm.scan_pattern(sig_bytes):
            # The LEA instruction is 7 bytes before the MOV instruction
            # LEA RCX, [RIP + 0x2ba33b5] at 0x140758b14
            # MOV RAX, [RCX + RAX * 8 + 0x810] at 0x140758bd3
            lea_addr = addr - (0x140758bd3 - 0x140758b14)

            # Read the LEA instruction: 48 8D 0D XX XX XX XX (LEA RCX, [RIP+disp32])
            lea_data = self.pm.read_bytes(lea_addr, 7)
            if lea_data and lea_data[0:3] == b"\x48\x8D\x0D":
                # Decode RIP-relative address
                disp32 = int.from_bytes(lea_data[3:7], "little", signed=True)
                # RIP points to next instruction (lea_addr + 7)
                target_va = lea_addr + 7 + disp32
                # Convert VA to runtime address
                runtime_base = self._get_module_base()
                if runtime_base:
                    registry_base = target_va - 0x140000000 + runtime_base
                    if verbose:
                        print(f"  Registry base resolved: {registry_base:#x}")
                    return registry_base

        if verbose:
            print("  Failed to resolve registry base")
        return None

    def _get_module_base(self) -> Optional[int]:
        """Get the base address of the main module (rift_x64.exe)."""
        import ctypes
        from ctypes import wintypes

        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        PROCESS_QUERY_INFORMATION = 0x0400

        # Get module handles
        buf = (ctypes.c_void_p * 1024)()
        cb = ctypes.sizeof(buf)
        cb_needed = wintypes.DWORD()

        ok = psapi.EnumProcessModules(
            self.pm._handle, buf, cb, ctypes.byref(cb_needed)
        )
        if ok:
            # First module is the main executable
            module_base = buf[0]
            if module_base:
                return module_base

        return None

    def read_player_coords_via_registry(self, verbose: bool = False) -> Optional[dict]:
        """Read player coordinates using the Assets repo registry-based approach.

        Returns dict with x, y, z, heading or None on failure.
        """
        self._load_signature_db()

        # Step 1: Find registry base
        registry_base = self.find_registry_base(verbose=verbose)
        if not registry_base:
            if verbose:
                print("  Cannot find registry base")
            return None

        # Step 2: Find the player unit in the registry
        # The registry is an array of pointers. We need to find the player entry.
        # Strategy: scan the registry for entries that look like valid unit objects
        # and check the player_flag at offset 0x120

        struct_db = self._signature_db.get("Structs", [])
        unit_struct = None
        player_struct = None
        for s in struct_db:
            if s["Name"] == "UnitObject":
                unit_struct = s
            elif s["Name"] == "LocalPlayer":
                player_struct = s

        if not unit_struct or not player_struct:
            if verbose:
                print("  UnitObject or LocalPlayer struct not found in signature database")
            return None

        # Build offset maps
        unit_offsets = {f["Name"]: f["Offset"] for f in unit_struct.get("Fields", [])}
        player_offsets = {f["Name"]: f["Offset"] for f in player_struct.get("Fields", [])}

        # Step 3: Scan registry for player entries
        # The registry base is a pointer to an array of pointers
        # Each pointer points to a unit object
        # We scan up to 1024 entries

        if verbose:
            print(f"  Scanning registry at {registry_base:#x} for player entries...")

        for i in range(1024):
            # Read the pointer at registry_base + i * 8
            unit_ptr = self.pm.read_pointer(registry_base + i * 8)
            if not unit_ptr or unit_ptr < 0x10000:
                continue

            # Check player_flag at offset 0x120
            player_flag = self.pm.read_uint32(unit_ptr + unit_offsets.get("player_flag", 0x120))
            if player_flag != 1:
                continue

            # Found a player! Read coordinates from the sub-structure
            # The details_substructure pointer is at offset 0x6E0
            details_ptr = self.pm.read_pointer(unit_ptr + unit_offsets.get("details_substructure", 0x6E0))
            if not details_ptr or details_ptr < 0x10000:
                continue

            # Read coordinates from the sub-structure
            x = self.pm.read_float32(details_ptr + player_offsets.get("pos_x", 0x320))
            y = self.pm.read_float32(details_ptr + player_offsets.get("pos_y", 0x324))
            z = self.pm.read_float32(details_ptr + player_offsets.get("pos_z", 0x328))

            if x is not None and y is not None and z is not None:
                # Validate coordinates are within reasonable bounds
                if abs(x) < 100000 and abs(y) < 100000 and abs(z) < 100000:
                    if verbose:
                        print(f"  Player found at registry[{i}]: x={x:.1f}, y={y:.1f}, z={z:.1f}")
                    return {
                        "x": x,
                        "y": y,
                        "z": z,
                        "registry_index": i,
                        "unit_ptr": unit_ptr,
                        "details_ptr": details_ptr,
                    }

        if verbose:
            print("  No player found in registry")
        return None

    def scan_for_lua_strings(self, verbose: bool = False) -> list[FoundString]:
        """Scan the heap for Lua string objects containing known addon names.

        Returns a list of FoundString objects.
        """
        t0 = time.time()
        found = []

        for prefix in self.SEARCH_PREFIXES:
            if verbose:
                print(f"  Scanning for prefix: {prefix.decode('utf-8', errors='replace')}...")
            for addr, text in self.pm.scan_for_null_terminated(prefix):
                # Validate the string looks like a valid global name
                if not self._is_valid_global_name(text):
                    continue

                # Try to read the TString header just before the char data
                # On x64 Lua 5.1, the TString struct is 24 bytes before the char data
                for header_offset in [24, 20, 16, 28]:
                    str_obj_addr = addr - header_offset
                    header = Lua51.read_string_header(self.pm, str_obj_addr)
                    if header and header.char_address == addr:
                        found.append(FoundString(
                            name=text,
                            char_address=addr,
                            string_object_address=str_obj_addr,
                            header=header,
                        ))
                        break

        self._found_strings = found
        self._scan_time = time.time() - t0
        if verbose:
            print(f"  Found {len(found)} Lua strings in {self._scan_time:.1f}s")
        return found

    def find_global_table(self, verbose: bool = False) -> Optional[int]:
        """Find the _G (global table) address.

        Strategy: Find a known string, then search for a table that references it.
        The global table's hash part should contain entries pointing to TValue
        structs whose keys point to TString objects we found.
        """
        if self._global_table_addr:
            return self._global_table_addr

        if not self._found_strings:
            self.scan_for_lua_strings(verbose=verbose)

        if not self._found_strings:
            return None

        if verbose:
            print(f"  Searching for global table via {len(self._found_strings)} known strings...")

        # Strategy: For each found string, look for table nodes that reference it.
        # A table node is a 32-byte struct: {TValue value, TValue key}
        # The key TValue's value_raw should point to the TString object address.
        target_string = self._found_strings[0]
        target_obj_addr = target_string.string_object_address

        if verbose:
            print(f"  Looking for table referencing: {target_string.name}")
            print(f"  String object at: {target_obj_addr:#x}")

        # Scan for Node structs that contain a reference to our known string.
        # A Node is {TValue value, TValue key} = 32 bytes.
        # The key's value_raw should be the string object address.
        #
        # Search for the string object pointer (8 bytes) in memory.
        target_bytes = target_obj_addr.to_bytes(8, "little")

        for region in self.pm.enumerate_regions(private_only=True):
            if region.size < 0x1000:
                continue

            CHUNK = 0x100000
            for offset in range(0, region.size, CHUNK):
                chunk_start = region.base + offset
                chunk_size = min(CHUNK, region.size)
                data = self.pm.read_bytes(chunk_start, chunk_size)
                if not data:
                    continue

                idx = 0
                while True:
                    pos = data.find(target_bytes, idx)
                    if pos == -1:
                        break

                    # Found a reference to our string. Check if it's inside a Node.
                    ref_addr = chunk_start + pos

                    # A Node has TValue value at offset -16 and TValue key at offset 0
                    # The key is at ref_addr (since value_raw is the first field of the key TValue)
                    # The value TValue is at ref_addr - 16
                    node_addr = ref_addr - 8  # ref_addr points to value_raw inside key TValue, which starts at node+16

                    # Actually: Node = {TValue value(16), TValue key(16)}
                    # key.value_raw is at node_addr + 16
                    # So if we found the pointer at ref_addr, node_addr = ref_addr - 16
                    potential_node = ref_addr - 16

                    # Validate: read the key's type tag (should be TSTRING)
                    key_tt = self.pm.read_uint8(potential_node + 16 + 8)
                    if key_tt == LuaType.TSTRING:
                        # Read the value TValue to get the global's value
                        val_tt_data = self.pm.read_bytes(potential_node, 16)
                        if val_tt_data:
                            val_tt = int.from_bytes(val_tt_data[8:12], "little")
                            if val_tt in (LuaType.TNIL, LuaType.TBOOLEAN, LuaType.TNUMBER,
                                           LuaType.TSTRING, LuaType.TTABLE, LuaType.TFUNCTION):
                                # This looks like a valid table node!
                                # Now find the table that owns this node.
                                # We need to find a Table header whose `node` field points
                                # to a region containing this node.
                                table_addr = self._find_owner_table(potential_node)
                                if table_addr:
                                    self._global_table_addr = table_addr
                                    if verbose:
                                        print(f"  Found global table at: {table_addr:#x}")
                                    return table_addr

                    idx = pos + 1

        return None

    def _find_owner_table(self, node_addr: int) -> Optional[int]:
        """Find the Table struct that owns a node at the given address.

        Strategy: Search for Table structs whose `node` field points to a region
        containing the given node address.
        """
        # A Table's node field is at offset 32 (after TValue kv + flags + lsizenode + sizearray + array_ptr)
        # node_ptr is at offset 32 of the Table struct.
        # We search for a pointer to (node_addr - i * 32) for i in 0..n where
        # the node is within the hash part.

        nhash_max = 256  # max hash size we'll check
        for nhash_log in range(0, 9):  # 2^0 to 2^8
            nhash = 1 << nhash_log
            if nhash > nhash_max:
                break
            node_size = 32
            for i in range(nhash):
                potential_base = node_addr - i * node_size
                base_bytes = potential_base.to_bytes(8, "little")

                # Search for this pointer in memory (as a Table's node field)
                for region in self.pm.enumerate_regions(private_only=True):
                    if region.size < 0x1000:
                        continue
                    CHUNK = 0x100000
                    for offset in range(0, region.size, CHUNK):
                        chunk_start = region.base + offset
                        chunk_size = min(CHUNK, region.size)
                        data = self.pm.read_bytes(chunk_start, chunk_size)
                        if not data:
                            continue
                        idx = 0
                        while True:
                            pos = data.find(base_bytes, idx)
                            if pos == -1:
                                break
                            candidate_field_addr = chunk_start + pos
                            # The Table struct's node field is at offset 32
                            table_addr = candidate_field_addr - 32
                            # Validate: check if it looks like a Table header
                            tbl = Lua51.read_table_header(self.pm, table_addr)
                            if tbl and tbl.node == potential_base:
                                return table_addr
                            idx = pos + 1
        return None

    def read_globals(self, verbose: bool = False) -> dict[str, GlobalEntry]:
        """Read all globals from the _G table. Caches the result."""
        if self._cached_globals:
            return self._cached_globals

        if not self._global_table_addr:
            self.find_global_table(verbose=verbose)

        if not self._global_table_addr:
            return {}

        globals_dict = {}
        for key_str, val in Lua51.iter_table_keys(self.pm, self._global_table_addr):
            if key_str and len(key_str) < self.MAX_GLOBAL_NAME_LEN:
                globals_dict[key_str] = GlobalEntry(
                    name=key_str,
                    value_tt=val.tt,
                    value_raw=val.value_raw,
                    value_type=val.value_type,
                )

        self._cached_globals = globals_dict
        if verbose:
            print(f"  Parsed {len(globals_dict)} globals from _G")
        return globals_dict

    def read_global_string(self, name: str) -> Optional[str]:
        """Read the value of a string global by name."""
        globals_dict = self.read_globals()
        entry = globals_dict.get(name)
        if not entry:
            return None
        if entry.value_tt == LuaType.TSTRING:
            return Lua51.read_string_value(self.pm, entry.value_raw)
        return None

    def read_global_number(self, name: str) -> Optional[float]:
        """Read the value of a number global by name."""
        globals_dict = self.read_globals()
        entry = globals_dict.get(name)
        if not entry:
            return None
        if entry.value_tt == LuaType.TNUMBER:
            # For Lua 5.1, the number is stored directly in the TValue's value field
            # as a double (8 bytes).
            data = self.pm.read_bytes(entry.value_raw, 8)  # Wait, value_raw IS the number for TNUMBER
            # Actually for TNUMBER, the number is stored in the TValue's value union
            # which is at offset 0 of the TValue. Since value_raw IS the value field,
            # we need to re-read it as a double.
            raw_bytes = entry.value_raw.to_bytes(8, "little")
            import struct
            return struct.unpack("d", raw_bytes)[0]
        return None

    def _is_valid_global_name(self, text: str) -> bool:
        """Check if a string looks like a valid Lua global variable name."""
        if len(text) < self.MIN_GLOBAL_NAME_LEN:
            return False
        if len(text) > self.MAX_GLOBAL_NAME_LEN:
            return False
        # Lua identifiers: letter or underscore, then letter/digit/underscore
        if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', text):
            return False
        return True

    def invalidate_cache(self):
        """Clear cached state. Forces a fresh scan on next read."""
        self._cached_globals.clear()
        self._global_table_addr = None
        self._string_table_addrs.clear()
        self._found_strings.clear()
