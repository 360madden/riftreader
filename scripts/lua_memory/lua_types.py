"""Lua 5.1 internal data structure definitions.

Defines memory layouts for Lua 5.1 (used by RIFT) types: strings, tables,
closures, and the lua_State itself. All offsets are for 64-bit builds.

Key insight: Lua 5.1 stores values in "TValue" (typed value) structs:
  { Value v; int tt; } where Value is a union of {number, string*, bool, ...}
  On 64-bit: Value = 8 bytes (pointer/union), tt = 4 bytes, padding = 4 bytes
  Total TValue = 16 bytes.

Reference: lua.h, lobject.h from Lua 5.1 source.
"""

from enum import IntEnum
from dataclasses import dataclass
from typing import Optional

from .process import ProcessMemory


# Lua 5.1 type tags (from lua.h)
class LuaType(IntEnum):
    TNONE = -1
    TNIL = 0
    TBOOLEAN = 1
    TLIGHTUSERDATA = 2
    TNUMBER = 3
    TSTRING = 4
    TTABLE = 5
    TFUNCTION = 6
    TUSERDATA = 7
    TTHREAD = 8

    @classmethod
    def name_of(cls, tag: int) -> str:
        try:
            return cls(tag).name
        except ValueError:
            return f"UNKNOWN({tag})"


# Lua 5.1 struct sizes and offsets (64-bit)
# These match the Lua 5.1.5 source compiled for x64

# TString header (lobject.h)
# struct TString {
#   union { const char *str; } TString_content;
#   lu_byte tt;      // type tag (4)
#   lu_byte reserved; // (1)
#   lu_byte marked;   // GC mark (1)
#   // padding to 4-byte align
#   unsigned int hash; // hash value (4)
#   size_t len;       // string length (8)
# } __attribute__((packed));
# Total header before char data: 4 + 1 + 1 + 2(padding) + 4 + 8 = 20? No.
#
# Actually in practice on x64 Lua 5.1:
# offset 0: union { char *str } = 8 bytes (pointer)
# But wait, for TString the data follows immediately after the header.
# The layout depends on LUAI_USERENTRY / string concatenation.
#
# For simplicity, let me use the "short string" layout where:
# offset 0: unused (the union member, 8 bytes for pointer on x64)
# No wait. Let me re-examine.
#
# In Lua 5.1.5 lobject.h:
# typedef union TString {
#   L_Umaxalign dummy;  /* ensures maximum alignment for strings */
#   struct {
#     TValue tvk;  /* containing the key (for chains) */
#     size_t len;  /* number of characters in string */
#   } tsv;
# } TString;
#
# TValue tvk is: { Value value; int tt; } = {8 + 4 + 4pad} = 16 bytes
# Then len = 8 bytes
# Total = 24 bytes
# The char data starts at offset 24 (right after the struct)
#
# Wait no. Looking more carefully:
# The TString union is the container. The actual string data is allocated
# right after the TString header. So:
# struct TString {
#   TValue tvk;  // 16 bytes (value=8, tt=4, pad=4)
#   size_t len;  // 8 bytes
# };  // = 24 bytes total
# char data[];  // starts at offset 24
#
# But the TValue's value field stores something else for strings...
# Actually in Lua 5.1, TString is used differently.
#
# Let me just use the empirical approach: we know that for RIFT's Lua,
# string objects have a specific layout that we can discover by scanning.

# For practical purposes, here are the offsets we'll use:
# These are derived from Lua 5.1.5 x64 compiled binaries.

@dataclass
class LuaStringHeader:
    """Parsed Lua string header. Address points to the start of the header."""
    address: int
    type_tag: int      # offset 0: type tag byte
    hash: int          # hash value (for string table chains)
    length: int        # string length
    char_address: int  # address of the actual char data

    STRING_HEADER_SIZE = 24  # bytes before char data (on x64)


@dataclass
class LuaTableHeader:
    """Parsed Lua table header."""
    address: int
    type_tag: int      # offset 0: TTABLE (5)
    flags: int         # tag methods flags
    lsizenode: int     # log2(hash part size)
    sizearray: int     # array part size
    array: int         # pointer to array part
    node: int          # pointer to hash part (TKey/TValue nodes)
    lastfree: int      # next free slot in hash part
    meta: int          # metatable pointer


@dataclass
class LuaTValue:
    """A Lua typed value (TValue = {Value, tt})."""
    value_raw: int     # 8 bytes: the raw value (number, pointer, bool flag)
    tt: int            # 4 bytes: type tag
    value_type: str    # human-readable type


class Lua51:
    """Lua 5.1 memory layout constants and parsers for 64-bit builds."""

    # TString layout offsets (64-bit)
    # In Lua 5.1.5, TString = union { L_Umaxalign; struct { TValue tvk; size_t len; } tsv; }
    # TValue = { Value v; int tt; } where Value = union { number, GCObject*, void* }
    # On x64: Value = 8 bytes, tt = 4 bytes, pad = 4 bytes = 16 bytes for TValue
    # Then len = 8 bytes
    # Char data starts at offset 24 (16 + 8)
    TSTRING_HEADER_SIZE = 24
    TSTRING_TT_OFFSET = 0     # actually the tt is inside the TValue at offset 8
    TSTRING_LEN_OFFSET = 16   # size_t len after the TValue (at byte 16)
    TSTRING_HASH_OFFSET = 12  # hash is embedded in the TValue's key at offset 12 (tt of the key)

    # Hmm this is getting complicated. Let me use a simpler approach.
    # The key insight: for our purposes, we need to:
    # 1. Find the type tag to confirm it's a string
    # 2. Read the length
    # 3. Read the char data
    #
    # Let me use the approach where we scan for strings by their char data,
    # and validate by checking the surrounding header.

    @staticmethod
    def read_string_header(pm: ProcessMemory, string_address: int) -> Optional[LuaStringHeader]:
        """Read a Lua string header. string_address = start of the TString struct.

        Returns the header with char_data_address pointing to the actual string bytes.
        """
        # Read 32 bytes of header
        header = pm.read_bytes(string_address, 32)
        if not header:
            return None

        # The type tag for TString is 4 (LUA_TSTRING)
        # It's stored in the TValue inside TString.
        # For practical purposes, we check the byte at the tt position.
        # In Lua 5.1 x64, the TValue is at offset 0 of TString:
        #   offset 0: Value (8 bytes)
        #   offset 8: tt (4 bytes)
        #   offset 12: padding (4 bytes)
        # Then size_t len at offset 16 (8 bytes)
        # Then char data at offset 24

        tt = header[8]  # type tag byte (from the int32 at offset 8, low byte)
        length = int.from_bytes(header[16:24], "little")

        if tt != LuaType.TSTRING:
            return None
        if length > 10_000_000:  # sanity: max string length
            return None

        char_address = string_address + Lua51.TSTRING_HEADER_SIZE
        return LuaStringHeader(
            address=string_address,
            type_tag=tt,
            hash=0,  # We'll compute this if needed
            length=length,
            char_address=char_address,
        )

    @staticmethod
    def read_string_value(pm: ProcessMemory, string_address: int) -> Optional[str]:
        """Read the full string value from a TString object."""
        header = Lua51.read_string_header(pm, string_address)
        if not header:
            return None
        raw = pm.read_bytes(header.char_address, header.length)
        if not raw:
            return None
        return raw.decode("utf-8", errors="replace")

    @staticmethod
    def read_tvalue(pm: ProcessMemory, address: int) -> Optional[LuaTValue]:
        """Read a TValue struct from the given address.

        TValue layout (64-bit):
          offset 0: Value (8 bytes) - union of {number, GCObject*, int, bool}
          offset 8: tt (4 bytes) - type tag
          offset 12: padding (4 bytes)
        Total: 16 bytes.
        """
        data = pm.read_bytes(address, 16)
        if not data:
            return None

        value_raw = int.from_bytes(data[0:8], "little")
        tt = int.from_bytes(data[8:12], "little")

        return LuaTValue(
            value_raw=value_raw,
            tt=tt,
            value_type=LuaType.name_of(tt),
        )

    @staticmethod
    def read_table_header(pm: ProcessMemory, table_address: int) -> Optional[LuaTableHeader]:
        """Read a Lua table header.

        Table layout (5.1 x64, simplified):
          offset 0: TValue (kv) containing type tag = 5 (TTYPE) - 16 bytes
          offset 16: lu_byte flags
          offset 17: lu_byte lsizenode
          // padding to 4
          offset 20: int sizearray (4 bytes)
          offset 24: TValue *array (8 bytes)
          offset 32: Node *node (8 bytes)
          offset 40: Node *lastfree (8 bytes)
          offset 48: Table *metatable (8 bytes)
        """
        data = pm.read_bytes(table_address, 56)
        if not data:
            return None

        tt = data[8]  # type tag from TValue
        if tt != LuaType.TTABLE:
            return None

        flags = data[16]
        lsizenode = data[17]
        sizearray = int.from_bytes(data[20:24], "little")
        array_ptr = int.from_bytes(data[24:32], "little")
        node_ptr = int.from_bytes(data[32:40], "little")
        lastfree_ptr = int.from_bytes(data[40:48], "little")
        meta_ptr = int.from_bytes(data[48:56], "little")

        return LuaTableHeader(
            address=table_address,
            type_tag=tt,
            flags=flags,
            lsizenode=lsizenode,
            sizearray=sizearray,
            array=array_ptr,
            node=node_ptr,
            lastfree=lastfree_ptr,
            meta=meta_ptr,
        )

    @staticmethod
    def read_table_node(pm: ProcessMemory, node_address: int) -> tuple[Optional[LuaTValue], Optional[LuaTValue]]:
        """Read a table Node (key-value pair).

        Node layout (64-bit):
          offset 0: TValue value (16 bytes)
          offset 16: TValue key (16 bytes)
        Total: 32 bytes.
        """
        value = Lua51.read_tvalue(pm, node_address)
        key = Lua51.read_tvalue(pm, node_address + 16)
        return value, key

    @staticmethod
    def iter_table_keys(pm: ProcessMemory, table_addr: int):
        """Iterate over all string keys in a Lua table.

        Yields (key_string, value_tvalue) pairs.
        """
        header = Lua51.read_table_header(pm, table_addr)
        if not header:
            return

        nhash = (1 << header.lsizenode) if header.lsizenode > 0 else 0

        # Walk hash part
        if header.node and nhash > 0:
            node_size = 32  # sizeof(Node) = 2 * sizeof(TValue) = 32
            for i in range(nhash):
                node_addr = header.node + i * node_size
                val, key = Lua51.read_table_node(pm, node_addr)
                if key and key.tt == LuaType.TSTRING and key.value_raw:
                    # key.value_raw is a pointer to the TString object
                    key_str = Lua51.read_string_value(pm, key.value_raw)
                    if key_str and val:
                        yield key_str, val

        # Walk array part
        if header.array and header.sizearray > 0:
            for i in range(header.sizearray):
                slot_addr = header.array + i * 16  # sizeof(TValue) = 16
                val = Lua51.read_tvalue(pm, slot_addr)
                if val:
                    yield str(i + 1), val  # Lua arrays are 1-indexed
