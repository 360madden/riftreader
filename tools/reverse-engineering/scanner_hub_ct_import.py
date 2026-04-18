from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


MODULE_OFFSET_RE = re.compile(
    r"^(?P<module>.+?)(?P<operator>[+-])(?P<offset>0x[0-9A-Fa-f]+|\d+)$"
)
AOB_CALL_RE = re.compile(r"^(?P<name>aobscanmodule|aobscan)\((?P<args>.*)\)$", re.IGNORECASE)


def _clean_text(value: str | None) -> str:
    if value is None:
        return ""
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] == '"':
        text = text[1:-1]
    return text.strip()


def _parse_int(text: str) -> int | None:
    value = _clean_text(text)
    if not value:
        return None
    try:
        return int(value, 0)
    except ValueError:
        return None


def _split_call_arguments(text: str) -> list[str]:
    args: list[str] = []
    current: list[str] = []
    depth = 0
    quoted = False
    for char in text:
        if char == '"':
            quoted = not quoted
        elif not quoted:
            if char == "(":
                depth += 1
            elif char == ")" and depth > 0:
                depth -= 1
            elif char == "," and depth == 0:
                args.append("".join(current).strip())
                current = []
                continue
        current.append(char)
    if current:
        args.append("".join(current).strip())
    return args


@dataclass(slots=True)
class ParsedAddressExpression:
    kind: str
    raw_expression: str
    module_name: str | None = None
    module_rva: int | None = None
    absolute_address: int | None = None
    aob_module: str | None = None
    aob_pattern: str | None = None


@dataclass(slots=True)
class CtImportEntry:
    import_key: str
    label: str
    group_path: str | None
    kind: str
    value_type: str | None
    address_expression: str | None
    module_name: str | None
    module_rva: int | None
    absolute_address: int | None
    offsets: list[int]
    notes: str | None
    metadata: dict


@dataclass(slots=True)
class CtImportTable:
    source_path: Path
    label: str
    entries: list[CtImportEntry]
    warnings: list[str]


def parse_address_expression(expression: str | None) -> ParsedAddressExpression:
    raw = _clean_text(expression)
    if not raw:
        return ParsedAddressExpression(kind="empty", raw_expression="")

    absolute_value = _parse_int(raw)
    if absolute_value is not None:
        return ParsedAddressExpression(
            kind="absolute",
            raw_expression=raw,
            absolute_address=absolute_value,
        )

    module_match = MODULE_OFFSET_RE.fullmatch(raw)
    if module_match:
        offset_value = _parse_int(module_match.group("offset"))
        if offset_value is not None:
            if module_match.group("operator") == "-":
                offset_value *= -1
            return ParsedAddressExpression(
                kind="module-relative",
                raw_expression=raw,
                module_name=_clean_text(module_match.group("module")),
                module_rva=offset_value,
            )

    call_match = AOB_CALL_RE.fullmatch(raw)
    if call_match:
        call_name = call_match.group("name").lower()
        args = _split_call_arguments(call_match.group("args"))
        if call_name == "aobscanmodule" and len(args) >= 2:
            return ParsedAddressExpression(
                kind="aobscanmodule",
                raw_expression=raw,
                aob_module=_clean_text(args[0]),
                aob_pattern=_clean_text(args[1]),
            )
        if call_name == "aobscan" and args:
            return ParsedAddressExpression(
                kind="aobscan",
                raw_expression=raw,
                aob_pattern=_clean_text(args[0]),
            )

    return ParsedAddressExpression(kind="expression", raw_expression=raw)


def _make_import_key(
    source_path: Path,
    group_path: str | None,
    label: str,
    address_expression: str | None,
    offsets: list[int],
    entry_id: str | None,
) -> str:
    payload = "::".join(
        [
            str(source_path.resolve()),
            group_path or "",
            label,
            address_expression or "",
            ",".join(f"0x{offset:X}" for offset in offsets),
            entry_id or "",
        ]
    )
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
    return f"ct::{digest}"


def _entry_notes(node: ET.Element) -> str | None:
    note_parts: list[str] = []
    for tag_name in ("Comment", "LuaScript", "AssemblerScript", "Hotkeys"):
        text = _clean_text(node.findtext(tag_name))
        if text:
            note_parts.append(f"{tag_name}: {text}")
    if not note_parts:
        return None
    return "\n".join(note_parts)


def _parse_offsets(node: ET.Element) -> list[int]:
    offsets: list[int] = []
    offsets_root = node.find("Offsets")
    if offsets_root is None:
        return offsets

    for offset_node in offsets_root.findall("Offset"):
        offset_value = _parse_int(offset_node.text or "")
        if offset_value is not None:
            offsets.append(offset_value)
    return offsets


def _guess_entry_kind(parsed: ParsedAddressExpression, offsets: list[int], has_children: bool) -> str:
    if has_children and parsed.kind == "empty":
        return "group"
    if offsets:
        return "pointer"
    if parsed.kind == "module-relative":
        return "module-offset"
    if parsed.kind in {"aobscan", "aobscanmodule"}:
        return "aob"
    if parsed.kind == "absolute":
        return "address"
    if parsed.kind == "empty":
        return "group" if has_children else "expression"
    return parsed.kind


def _parse_cheat_entry(
    node: ET.Element,
    *,
    source_path: Path,
    group_stack: list[str],
    warnings: list[str],
    sink: list[CtImportEntry],
) -> None:
    label = _clean_text(node.findtext("Description")) or _clean_text(node.findtext("Name")) or "Unnamed entry"
    value_type = _clean_text(node.findtext("VariableType")) or None
    address_expression = _clean_text(node.findtext("Address")) or None
    offsets = _parse_offsets(node)
    parsed_address = parse_address_expression(address_expression)

    child_entries_root = node.find("CheatEntries")
    child_nodes = child_entries_root.findall("CheatEntry") if child_entries_root is not None else []
    has_children = bool(child_nodes)
    kind = _guess_entry_kind(parsed_address, offsets, has_children)
    group_path = " / ".join(group_stack) if group_stack else None
    entry_id = _clean_text(node.findtext("ID")) or None

    metadata = {
        "entry_id": entry_id,
        "is_group": kind == "group",
        "address_kind": parsed_address.kind,
        "show_as_hex": _clean_text(node.findtext("ShowAsHex")) or None,
        "aob_module": parsed_address.aob_module,
        "aob_pattern": parsed_address.aob_pattern,
    }

    if parsed_address.kind == "expression" and address_expression:
        warnings.append(f"Unsupported CT address expression preserved as metadata: {address_expression}")

    sink.append(
        CtImportEntry(
            import_key=_make_import_key(
                source_path,
                group_path,
                label,
                address_expression,
                offsets,
                entry_id,
            ),
            label=label,
            group_path=group_path,
            kind=kind,
            value_type=value_type,
            address_expression=address_expression,
            module_name=parsed_address.module_name or parsed_address.aob_module,
            module_rva=parsed_address.module_rva,
            absolute_address=parsed_address.absolute_address,
            offsets=offsets,
            notes=_entry_notes(node),
            metadata=metadata,
        )
    )

    child_group_stack = [*group_stack, label] if kind == "group" else [*group_stack]
    for child_node in child_nodes:
        _parse_cheat_entry(
            child_node,
            source_path=source_path,
            group_stack=child_group_stack,
            warnings=warnings,
            sink=sink,
        )


def parse_cheat_table(source_path: str | Path) -> CtImportTable:
    path = Path(source_path).resolve()
    tree = ET.parse(path)
    root = tree.getroot()
    cheat_entries_root = root.find("CheatEntries")
    if cheat_entries_root is None:
        raise ValueError(f"{path} does not contain a CheatEntries root.")

    warnings: list[str] = []
    entries: list[CtImportEntry] = []
    for cheat_entry in cheat_entries_root.findall("CheatEntry"):
        _parse_cheat_entry(
            cheat_entry,
            source_path=path,
            group_stack=[],
            warnings=warnings,
            sink=entries,
        )

    return CtImportTable(
        source_path=path,
        label=path.stem,
        entries=entries,
        warnings=list(dict.fromkeys(warnings)),
    )
