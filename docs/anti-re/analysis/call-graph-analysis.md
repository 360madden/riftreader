# Call Graph Analysis

Created: 2026-07-11
Status: **partial** — `postupdate_static_access_chain.py` provides constructor call breadcrumbs
Tool: Ghidra headless, `postupdate_static_access_chain.py`

## Purpose

Trace the call graph from coordinate-writing functions upward to find
module-global references that serve as stable static roots.

## Known Call Chains

### Constructor `0x3F8B0` breadcrumb trail

```text
0x3F8B0 ← 0x39CD0 ← 0x13D2D80 ← 0x13CA1F0 ← 0x13B7DE0 ← 0x13A37D0
  ← {0x13AFAD0, 0x13B5E00} ← 0x1392E10 ← 0x6A7890 ← {0xC38390, 0xF75D90}
```

### Coordinate access code block

```text
rift_x64.exe+0x579F75..0x579FE3 — XYZ compare/copy block
rift_x64.exe+0x57C2A5 — [rcx+0x10] access pattern
rift_x64.exe+0x687F90 — Common accessor (197 xrefs, rcx+0x48)
```

### Container reader

```text
0xC38390 reads rift_x64+0x32DD7E8 → container → child+0x28/+0x2C/+0x30
```

## Global Roots Found

| Global | Function | Classification |
|---|---|---|
| `rift_x64+0x335F508` | `0x3F8B0` constructor | Orientation/matrix root (not position) |
| `rift_x64+0x32DD7E8` | `0xC38390` reader | Container root (candidate position chain) |
| `rift_x64+0x32EBC80` | Various | **Null since 2026-06-02** — old promoted root |

## Analysis

The call graph analysis is partially complete via `postupdate_static_access_chain.py`.
The gap is automated upward traversal from any access event to the first
module-global reference. Current tools trace from known constructors but
cannot start from an arbitrary hardware watchpoint event.
