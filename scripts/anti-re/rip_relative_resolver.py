#!/usr/bin/env python3
"""
RIP-Relative Address Resolver for AOB Signature Matching.

Resolves RIP-relative operands in matched instructions to absolute
virtual addresses, bridging runtime AOB matches to static global pointers.

Usage:
    python rip_relative_resolver.py --binary <rift_x64.exe> --aob-file <signatures.json> --json
    python rip_relative_resolver.py --binary <rift_x64.exe> --aob "F3 0F 11 05 ?? ?? ?? ??" --json
"""

import argparse
import json
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import pefile
except ImportError:
    print('{"error": "pefile not installed. Run: pip install pefile"}', file=sys.stderr)
    sys.exit(1)

try:
    from capstone import Cs, CS_ARCH_X86, CS_MODE_64
except ImportError:
    print('{"error": "capstone not installed. Run: pip install capstone"}', file=sys.stderr)
    sys.exit(1)


def parse_aob_string(aob_str):
    """Parse AOB string like 'F3 0F 11 05 ?? ?? ?? ??' into bytes and mask."""
    tokens = aob_str.strip().split()
    raw_bytes = bytearray()
    mask = bytearray()
    for tok in tokens:
        if tok.lower() in ('??', '?'):
            raw_bytes.append(0x00)
            mask.append(0x00)  # wildcard
        else:
            raw_bytes.append(int(tok, 16))
            mask.append(0xFF)  # must match
    return bytes(raw_bytes), bytes(mask)


def scan_section_for_aob(section_data, section_rva, base_address, pattern, mask):
    """Scan a PE section for AOB pattern matches."""
    matches = []
    pat_len = len(pattern)
    for i in range(len(section_data) - pat_len + 1):
        match = True
        for j in range(pat_len):
            if mask[j] == 0xFF and section_data[i + j] != pattern[j]:
                match = False
                break
        if match:
            abs_addr = base_address + section_rva + i
            matches.append({
                'offset_in_section': i,
                'rva': section_rva + i,
                'absolute_address': abs_addr,
                'matched_bytes': section_data[i:i + pat_len].hex(' '),
            })
    return matches


def resolve_rip_relative(md, instruction_addr, instruction_bytes, operand_index=None, section_rva=0):
    """
    Resolve RIP-relative displacement in an instruction to an absolute address.

    Returns dict with displacement info or None if not RIP-relative.
    """
    disasm_iter = md.disasm(bytes(instruction_bytes), instruction_addr)
    for insn in disasm_iter:
        for op in insn.operands:
            if op.type == 4:  # X86_OP_MEM with RIP base
                if op.mem.base == 0:  # RIP-relative (base=0 means [RIP+disp32])
                    disp = op.mem.disp
                    absolute_target = insn.address + insn.size + disp
                    return {
                        'instruction': insn.mnemonic + ' ' + insn.op_str,
                        'rva': insn.address,
                        'instruction_size': insn.size,
                        'displacement': disp,
                        'displacement_hex': f'0x{disp & 0xFFFFFFFF:08X}',
                        'absolute_target': absolute_target,
                        'target_rva': absolute_target - section_rva,
                    }
    return None


# x86-64 register encoding: Reg field from ModRM or SIB
REG_NAMES = {0: 'rax', 1: 'rcx', 2: 'rdx', 3: 'rbx', 4: 'rsp', 5: 'rbp', 6: 'rsi', 7: 'rdi',
             8: 'r8', 9: 'r9', 10: 'r10', 11: 'r11', 12: 'r12', 13: 'r13', 14: 'r14', 15: 'r15'}


def find_base_register_loads(md, text_data, section_rva, base_address, match_rva, target_regs, lookback=200):
    """Scan backward from a ModRM cluster to find instructions that load a base register
    via RIP-relative addressing (LEA reg, [RIP+disp32] or MOV reg, [mem]).

    Returns list of (offset_in_section, instruction) for each RIP-relative load found.
    """
    offset = match_rva - section_rva
    start = max(0, offset - lookback)
    region = text_data[start:offset + 15]
    results = []

    pos = 0
    while pos < len(region):
        chunk = region[pos:pos + 15]
        if not chunk:
            break
        decoded = list(md.disasm(bytes(chunk), base_address + section_rva + start + pos))
        if not decoded:
            pos += 1
            continue
        insn = decoded[0]

        # Check if this instruction loads a register via RIP-relative addressing
        # Pattern: MOV reg, [RIP+disp32] or LEA reg, [RIP+disp32]
        if insn.mnemonic in ('mov', 'lea', 'movups', 'movaps', 'vmovss', 'vmovups'):
            for op in insn.operands:
                if op.type == 4:  # MEM operand
                    if op.mem.base == 0 and op.mem.disp != 0:  # RIP-relative
                        # Check if destination is one of our target registers
                        dest_reg = insn.reg_name(insn.operands[0].reg) if insn.operands[0].type == 1 else ''
                        if dest_reg.lower() in [r.lower() for r in target_regs]:
                            disp = op.mem.disp
                            abs_target = insn.address + insn.size + disp
                            target_rva = abs_target - base_address
                            results.append({
                                'offset_from_match': pos - (offset - start),
                                'rva': section_rva + start + pos,
                                'mnemonic': insn.mnemonic,
                                'op_str': insn.op_str,
                                'dest_register': dest_reg,
                                'displacement': disp,
                                'displacement_hex': f'0x{disp & 0xFFFFFFFF:08X}',
                                'absolute_target': abs_target,
                                'target_rva': target_rva,
                                'size': insn.size,
                            })

        pos += insn.size if insn.size > 0 else 1

    return results


def resolve_matches(pe, md, matches, section_rva, base_address):
    """Resolve RIP-relative operands in all instructions within each AOB match region.

    For multi-instruction AOB patterns, scans the entire matched byte region
    and finds all instructions with RIP-relative operands, not just the first.
    Also scans backward to find where base registers (RDI, RBX, RCX, RBP) are loaded.
    """
    results = []
    text_data = pe.get_data(section_rva, pe.sections[0].SizeOfRawData)

    for match in matches:
        rva = match['rva']
        pat_len = len(match.get('matched_bytes', '').split()) if match.get('matched_bytes') else 15
        offset_in_section = rva - section_rva
        region_end = min(offset_in_section + pat_len + 8, len(text_data))
        if offset_in_section >= len(text_data):
            continue

        region_bytes = text_data[offset_in_section:region_end]
        region_abs_addr = base_address + rva

        # Linear-sweep the match region to find all RIP-relative instructions
        rip_instructions = []
        pos = 0
        while pos < len(region_bytes):
            chunk = region_bytes[pos:pos + 15]
            if not chunk:
                break
            decoded = list(md.disasm(bytes(chunk), region_abs_addr + pos))
            if not decoded:
                pos += 1
                continue
            insn = decoded[0]
            insn_offset = pos
            if insn_offset < pat_len:
                for op in insn.operands:
                    if op.type == 4:  # X86_OP_MEM
                        if op.mem.base == 0 and op.mem.disp != 0:  # RIP-relative
                            disp = op.mem.disp
                            abs_target = insn.address + insn.size + disp
                            target_rva = abs_target - base_address
                            rip_instructions.append({
                                'address': insn.address,
                                'rva': rva + pos,
                                'mnemonic': insn.mnemonic,
                                'op_str': insn.op_str,
                                'bytes': insn.bytes.hex(' '),
                                'size': insn.size,
                                'displacement': disp,
                                'displacement_hex': f'0x{disp & 0xFFFFFFFF:08X}',
                                'absolute_target': abs_target,
                                'target_rva': target_rva,
                            })
                            break
            pos += insn.size if insn.size > 0 else 1

        # Scan backward to find base register loads via RIP-relative
        base_regs = ['rdi', 'rbx', 'rcx', 'rbp']
        base_register_loads = find_base_register_loads(md, text_data, section_rva, base_address, rva, base_regs)

        result = {
            'match': match,
            'rip_instructions': rip_instructions,
            'rip_count': len(rip_instructions),
            'base_register_loads': base_register_loads,
            'base_register_load_count': len(base_register_loads),
        }
        results.append(result)

    return results


def main():
    parser = argparse.ArgumentParser(description='Resolve RIP-relative addresses from AOB matches')
    parser.add_argument('--binary', required=True, help='Path to rift_x64.exe')
    parser.add_argument('--aob', help='AOB pattern string (e.g., "F3 0F 11 05 ?? ?? ?? ??")')
    parser.add_argument('--aob-file', help='JSON file with AOB signatures')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--output', help='Output file path')
    args = parser.parse_args()

    if not args.aob and not args.aob_file:
        print('Error: --aob or --aob-file required', file=sys.stderr)
        sys.exit(1)

    # Load PE
    pe = pefile.PE(args.binary)
    base_address = pe.OPTIONAL_HEADER.ImageBase

    # Find .text section
    text_section = None
    for section in pe.sections:
        if section.Name.rstrip(b'\x00') == b'.text':
            text_section = section
            break
    if not text_section:
        print('Error: .text section not found', file=sys.stderr)
        sys.exit(1)

    text_rva = text_section.VirtualAddress
    text_data = pe.get_data(text_rva, text_section.SizeOfRawData)

    # Initialize Capstone
    md = Cs(CS_ARCH_X86, CS_MODE_64)
    md.detail = True

    # Parse AOB patterns
    aobs = []
    if args.aob:
        pattern, mask = parse_aob_string(args.aob)
        aobs.append({'id': 'cli', 'aob': args.aob, 'pattern': pattern, 'mask': mask})
    elif args.aob_file:
        with open(args.aob_file) as f:
            db = json.load(f)
        for sig in db.get('signatures', db) if isinstance(db, list) else db.get('signatures', []):
            if 'aob' in sig:
                pattern, mask = parse_aob_string(sig['aob'])
                aobs.append({**sig, 'pattern': pattern, 'mask': mask})

    # Scan and resolve
    all_results = []
    for aob_entry in aobs:
        matches = scan_section_for_aob(text_data, text_rva, base_address, aob_entry['pattern'], aob_entry['mask'])
        resolved = resolve_matches(pe, md, matches, text_rva, base_address)

        all_results.append({
            'aob_id': aob_entry.get('id', 'unknown'),
            'aob_pattern': aob_entry.get('aob', ''),
            'target_offsets': aob_entry.get('targetOffsets', []),
            'match_count': len(matches),
            'resolutions': resolved,
        })

    # Output
    output = {
        'schemaVersion': 1,
        'kind': 'riftreader-rip-relative-resolution',
        'binary': str(args.binary),
        'generatedAtUtc': datetime.now(timezone.utc).isoformat(),
        'baseAddress': base_address,
        'textSectionRva': text_rva,
        'results': all_results,
    }

    if args.json or True:
        print(json.dumps(output, indent=2))

    if args.output:
        Path(args.output).write_text(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()
