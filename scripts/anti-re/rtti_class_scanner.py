#!/usr/bin/env python3
"""
RTTI Class Name Scanner for RIFT.

Scans a PE binary for MSVC RTTI class names and vtable structures.
Identifies player/actor-related classes for vtable-based instance discovery.

Usage:
    python rtti_class_scanner.py --binary <rift_x64.exe> --json
    python rtti_class_scanner.py --binary <rift_x64.exe> --filter player,actor,character
"""

import argparse
import json
import re
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import pefile
except ImportError:
    print('{"error": "pefile not installed. Run: pip install pefile"}', file=sys.stderr)
    sys.exit(1)


def find_rtti_strings(pe_data, section_rva, section_data):
    """Find MSVC RTTI class name strings (start with '.?AV')."""
    rtti_entries = []
    # MSVC RTTI format: .?AVClassName@@ (class) or .?AVAClassName@@ (abstract)
    pattern = re.compile(rb'\.(\?AV[A-Za-z0-9_]+@@)')

    for match in pattern.finditer(section_data):
        name_bytes = match.group(1)
        try:
            name = name_bytes.decode('ascii')
        except UnicodeDecodeError:
            continue

        offset_in_section = match.start()
        abs_rva = section_rva + offset_in_section

        rtti_entries.append({
            'name': name,
            'clean_name': name.replace('@@', ''),
            'rva': abs_rva,
            'offset_in_section': offset_in_section,
            'is_abstract': name.startswith('A'),
            'raw_bytes': match.group(0).hex(' '),
        })

    return rtti_entries


def find_vtable_pointers(pe, section_rva, section_data, vtable_rva, base_address):
    """Scan writable sections for pointers to a specific vtable."""
    hits = []

    for section in pe.sections:
        sec_name = section.Name.rstrip(b'\x00').decode('ascii', errors='replace')
        sec_chars = section.Characteristics

        # Only scan writable sections
        if not (sec_chars & 0x80000000):  # IMAGE_SCN_MEM_WRITE
            continue

        sec_rva = section.VirtualAddress
        sec_data = pe.get_data(sec_rva, section.SizeOfRawData)
        vtable_abs = base_address + vtable_rva

        # Scan for 8-byte pointers matching the vtable address
        for i in range(0, len(sec_data) - 7, 8):
            val = struct.unpack_from('<Q', sec_data, i)[0]
            if val == vtable_abs:
                hits.append({
                    'section': sec_name,
                    'rva': sec_rva + i,
                    'absolute_address': base_address + sec_rva + i,
                    'value': f'0x{val:016X}',
                })

    return hits


def scan_for_rtti(pe):
    """Main RTTI scanning pipeline."""
    base_address = pe.OPTIONAL_HEADER.ImageBase
    all_rtti = []

    # Scan .rdata for RTTI strings
    for section in pe.sections:
        sec_name = section.Name.rstrip(b'\x00').decode('ascii', errors='replace')
        if sec_name not in ('.rdata', '.data'):
            continue

        sec_rva = section.VirtualAddress
        sec_data = pe.get_data(sec_rva, section.SizeOfRawData)

        entries = find_rtti_strings(pe, sec_rva, sec_data)
        for entry in entries:
            entry['section'] = sec_name
            entry['absolute_address'] = base_address + entry['rva']
        all_rtti.extend(entries)

    # Deduplicate by name
    seen = set()
    unique = []
    for entry in all_rtti:
        if entry['name'] not in seen:
            seen.add(entry['name'])
            unique.append(entry)

    return sorted(unique, key=lambda x: x['name'])


def classify_classes(rtti_entries):
    """Classify RTTI entries by likely role."""
    player_keywords = ['player', 'actor', 'character', 'avatar', 'pawn', 'entity']
    camera_keywords = ['camera', 'view', 'render']
    world_keywords = ['world', 'scene', 'zone', 'map', 'terrain']
    ui_keywords = ['ui', 'hud', 'frame', 'window', 'widget']

    classified = {
        'player_related': [],
        'camera_related': [],
        'world_related': [],
        'ui_related': [],
        'other': [],
    }

    for entry in rtti_entries:
        name_lower = entry['clean_name'].lower()
        if any(kw in name_lower for kw in player_keywords):
            entry['classification'] = 'player_related'
            classified['player_related'].append(entry)
        elif any(kw in name_lower for kw in camera_keywords):
            entry['classification'] = 'camera_related'
            classified['camera_related'].append(entry)
        elif any(kw in name_lower for kw in world_keywords):
            entry['classification'] = 'world_related'
            classified['world_related'].append(entry)
        elif any(kw in name_lower for kw in ui_keywords):
            entry['classification'] = 'ui_related'
            classified['ui_related'].append(entry)
        else:
            entry['classification'] = 'other'
            classified['other'].append(entry)

    return classified


def main():
    parser = argparse.ArgumentParser(description='Scan RIFT binary for RTTI class names')
    parser.add_argument('--binary', required=True, help='Path to rift_x64.exe')
    parser.add_argument('--filter', help='Comma-separated keywords to filter classes')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--output', help='Output file path')
    args = parser.parse_args()

    pe = pefile.PE(args.binary)

    # Scan for RTTI
    rtti_entries = scan_for_rtti(pe)

    # Classify
    classified = classify_classes(rtti_entries)

    # Apply filter if specified
    if args.filter:
        keywords = [k.strip().lower() for k in args.filter.split(',')]
        rtti_entries = [
            e for e in rtti_entries
            if any(kw in e['clean_name'].lower() for kw in keywords)
        ]

    # Build output
    output = {
        'schemaVersion': 1,
        'kind': 'riftreader-rtti-class-inventory',
        'binary': str(args.binary),
        'binaryHash': '',
        'generatedAtUtc': datetime.now(timezone.utc).isoformat(),
        'totalClasses': len(rtti_entries),
        'classificationCounts': {
            'player_related': len(classified['player_related']),
            'camera_related': len(classified['camera_related']),
            'world_related': len(classified['world_related']),
            'ui_related': len(classified['ui_related']),
            'other': len(classified['other']),
        },
        'playerRelatedClasses': classified['player_related'],
        'cameraRelatedClasses': classified['camera_related'],
        'worldRelatedClasses': classified['world_related'],
        'allClasses': rtti_entries if not args.filter else rtti_entries,
    }

    if args.json or True:
        print(json.dumps(output, indent=2))

    if args.output:
        Path(args.output).write_text(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
