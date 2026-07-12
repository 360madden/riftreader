"""Low-level Windows process memory access via ReadProcessMemory.

Provides safe, structured access to another process's virtual memory,
including region enumeration, pattern scanning, and structured reads.
"""

import ctypes
import ctypes.wintypes as wintypes
from ctypes import (
    c_bool,
    c_byte,
    c_double,
    c_float,
    c_int,
    c_long,
    c_size_t,
    c_uint,
    c_uint8,
    c_uint16,
    c_uint32,
    c_uint64,
    c_ulong,
    c_void_p,
    byref,
    create_string_buffer,
    sizeof,
)
from dataclasses import dataclass
from enum import IntFlag
from typing import Iterator, Optional

# Windows constants
PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

MEM_COMMIT = 0x1000
MEM_PRIVATE = 0x20000
MEM_IMAGE = 0x1000000
MEM_MAPPED = 0x40000

PAGE_NOACCESS = 0x01
PAGE_READONLY = 0x02
PAGE_READWRITE = 0x04
PAGE_WRITECOPY = 0x08
PAGE_EXECUTE = 0x10
PAGE_EXECUTE_READ = 0x20
PAGE_EXECUTE_READWRITE = 0x40
PAGE_GUARD = 0x100
PAGE_NOCACHE = 0x200

# Kernel32
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", c_void_p),
        ("AllocationBase", c_void_p),
        ("AllocationProtect", wintypes.DWORD),
        ("PartitionId", wintypes.WORD),
        ("RegionSize", c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]


@dataclass(frozen=True)
class MemoryRegion:
    """A contiguous region of committed virtual memory."""
    base: int
    alloc_base: int
    alloc_protect: int
    size: int
    state: int
    protect: int
    type: int

    @property
    def is_readable(self) -> bool:
        readable = PAGE_READONLY | PAGE_READWRITE | PAGE_WRITECOPY | PAGE_EXECUTE_READ | PAGE_EXECUTE_READWRITE
        return bool(self.protect & readable) and not bool(self.protect & PAGE_GUARD)

    @property
    def is_private(self) -> bool:
        return self.type == MEM_PRIVATE

    @property
    def is_committed(self) -> bool:
        return self.state == MEM_COMMIT


class ProcessMemory:
    """Safe wrapper around ReadProcessMemory for a target process."""

    def __init__(self, pid: int):
        self.pid = pid
        self._handle = kernel32.OpenProcess(
            PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid
        )
        if not self._handle:
            err = ctypes.get_last_error()
            raise OSError(f"Cannot open process {pid}: error {err}")

    def close(self):
        if self._handle:
            kernel32.CloseHandle(self._handle)
            self._handle = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def read_bytes(self, address: int, size: int) -> Optional[bytes]:
        """Read `size` bytes from the target process at `address`."""
        buf = create_string_buffer(size)
        n_read = c_size_t(0)
        ok = kernel32.ReadProcessMemory(
            self._handle, c_void_p(address), buf, size, byref(n_read)
        )
        if not ok:
            return None
        return buf.raw[: n_read.value]

    def read_uint8(self, address: int) -> Optional[int]:
        data = self.read_bytes(address, 1)
        return data[0] if data else None

    def read_uint16(self, address: int) -> Optional[int]:
        data = self.read_bytes(address, 2)
        return int.from_bytes(data, "little") if data else None

    def read_uint32(self, address: int) -> Optional[int]:
        data = self.read_bytes(address, 4)
        return int.from_bytes(data, "little") if data else None

    def read_uint64(self, address: int) -> Optional[int]:
        data = self.read_bytes(address, 8)
        return int.from_bytes(data, "little") if data else None

    def read_int32(self, address: int) -> Optional[int]:
        val = self.read_uint32(address)
        return val if val is None else (val - (1 << 32) if val >= (1 << 31) else val)

    def read_int64(self, address: int) -> Optional[int]:
        val = self.read_uint64(address)
        return val if val is None else (val - (1 << 64) if val >= (1 << 63) else val)

    def read_float32(self, address: int) -> Optional[float]:
        data = self.read_bytes(address, 4)
        return ctypes.cast(ctypes.c_char_p(data), ctypes.POINTER(c_float))[0] if data else None

    def read_float64(self, address: int) -> Optional[float]:
        data = self.read_bytes(address, 8)
        return ctypes.cast(ctypes.c_char_p(data), ctypes.POINTER(c_double))[0] if data else None

    def read_pointer(self, address: int) -> Optional[int]:
        """Read a pointer-sized value (4 or 8 bytes depending on process)."""
        data = self.read_bytes(address, 8)  # Assume 64-bit for RIFT
        return int.from_bytes(data, "little") if data else None

    def read_cstring(self, address: int, max_len: int = 1024) -> Optional[str]:
        """Read a null-terminated C string from the target process."""
        if not address:
            return None
        chunks = []
        total = 0
        while total < max_len:
            chunk = self.read_bytes(address + total, min(256, max_len - total))
            if not chunk:
                break
            null_pos = chunk.find(b"\x00")
            if null_pos >= 0:
                chunks.append(chunk[:null_pos])
                break
            chunks.append(chunk)
            total += len(chunk)
        if not chunks:
            return None
        return b"".join(chunks).decode("utf-8", errors="replace")

    def read_lua_string(self, address: int) -> Optional[str]:
        """Read a Lua string value. address points to the char data, not the header."""
        if not address:
            return None
        # Read length from the header (8 bytes before the char data)
        # For Lua 5.1: header is {type=4, refcount=4, hash=4, len=4} = 16 bytes
        len_data = self.read_bytes(address - 8, 4)
        if not len_data:
            return None
        length = int.from_bytes(len_data, "little")
        if length > 10_000_000:  # sanity check
            return None
        raw = self.read_bytes(address, length)
        if not raw:
            return None
        return raw.decode("utf-8", errors="replace")

    def read_lua_number(self, address: int) -> Optional[float]:
        """Read a Lua number (always double in Lua 5.1)."""
        return self.read_float64(address)

    def read_lua_bool(self, address: int) -> Optional[bool]:
        """Read a Lua boolean. In TValue, the value byte is at offset 16 (after tt)."""
        val = self.read_uint8(address + 16)
        return bool(val) if val is not None else None

    def enumerate_regions(self, private_only: bool = False) -> Iterator[MemoryRegion]:
        """Enumerate all committed virtual memory regions in the target process."""
        addr = 0
        while addr < 0x7FFFFFFFFFFFFFFF:
            mbi = MEMORY_BASIC_INFORMATION()
            r = kernel32.VirtualQueryEx(
                self._handle, c_void_p(addr), byref(mbi), sizeof(mbi)
            )
            if r == 0:
                break
            region = MemoryRegion(
                base=mbi.BaseAddress or 0,
                alloc_base=mbi.AllocationBase or 0,
                alloc_protect=mbi.AllocationProtect,
                size=mbi.RegionSize,
                state=mbi.State,
                protect=mbi.Protect,
                type=mbi.Type,
            )
            if region.is_committed and region.is_readable:
                if not private_only or region.is_private:
                    yield region
            addr = region.base + region.size

    def scan_pattern(
        self,
        pattern: bytes,
        start: int = 0,
        end: int = 0x7FFFFFFFFFFFFFFF,
        private_only: bool = True,
    ) -> Iterator[int]:
        """Scan memory for an exact byte pattern. Yields all match addresses."""
        needle_len = len(pattern)
        for region in self.enumerate_regions(private_only=private_only):
            rbase = region.base
            rsize = region.size
            if rbase + rsize < start or rbase >= end:
                continue
            CHUNK = 0x100000
            for offset in range(0, rsize, CHUNK):
                chunk_start = rbase + offset
                chunk_size = min(CHUNK, rsize - offset)
                data = self.read_bytes(chunk_start, chunk_size)
                if not data:
                    continue
                idx = 0
                while True:
                    pos = data.find(pattern, idx)
                    if pos == -1:
                        break
                    yield chunk_start + pos
                    idx = pos + 1

    def scan_for_null_terminated(
        self,
        needle: bytes,
        start: int = 0,
        end: int = 0x7FFFFFFFFFFFFFFF,
        private_only: bool = True,
    ) -> Iterator[tuple[int, str]]:
        """Scan for null-terminated strings containing `needle`. Yields (addr, text)."""
        needle_str = needle.decode("utf-8", errors="replace")
        for region in self.enumerate_regions(private_only=private_only):
            rbase = region.base
            rsize = region.size
            if rbase + rsize < start or rbase >= end:
                continue
            CHUNK = 0x100000
            for offset in range(0, rsize, CHUNK):
                chunk_start = rbase + offset
                chunk_size = min(CHUNK, rsize - offset)
                data = self.read_bytes(chunk_start, chunk_size)
                if not data:
                    continue
                idx = 0
                while True:
                    pos = data.find(needle, idx)
                    if pos == -1:
                        break
                    # Walk backward to null terminator (start of string)
                    str_start = pos
                    while str_start > 0 and data[str_start - 1] != 0:
                        str_start -= 1
                    # Walk forward to null terminator (end of string)
                    str_end = pos + len(needle)
                    while str_end < len(data) and data[str_end] != 0:
                        str_end += 1
                    text = data[str_start:str_end].decode("utf-8", errors="replace")
                    if needle_str in text:
                        yield (chunk_start + str_start, text)
                    idx = pos + 1
