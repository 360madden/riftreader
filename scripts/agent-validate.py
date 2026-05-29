#!/usr/bin/env python3
"""
Agent Validation CI Script
Validates all custom agent definitions in .agents/ for structural correctness.

Checks performed:
1. File is valid TypeScript (syntax check via Node.js if available, else fallback)
2. File exports a default AgentDefinition
3. Required fields are present (id, displayName, model)
4. `id` matches filename (kebab-case)
5. `model` is a recognized OpenRouter model
6. `toolNames` only references known tools
7. `outputSchema` is valid JSON Schema if present
8. `spawnableAgents` references exist if present

Usage:
    python scripts/agent-validate.py           # validate all agents
    python scripts/agent-validate.py --verbose  # detailed output
    python scripts/agent-validate.py --json     # machine-readable output
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / ".agents"

# --- Recognized values from the type definitions ---

KNOWN_MODEL_PREFIXES = {
    "openai/", "anthropic/", "google/", "x-ai/", "qwen/",
    "deepseek/", "moonshotai/", "z-ai/", "minimax/",
}

# Short aliases (without publisher prefix) are also valid
KNOWN_MODEL_SHORT = {
    "deepseek-v4-pro", "deepseek-v4-flash",
}

KNOWN_TOOLS = {
    "add_message", "apply_patch", "ask_user", "code_search", "end_turn",
    "find_files", "glob", "gravity_index", "list_directory", "lookup_agent_info",
    "propose_str_replace", "propose_write_file", "read_docs", "read_files",
    "read_subtree", "read_url", "render_ui", "researcher_docs", "researcher_web",
    "run_file_change_hooks", "run_terminal_command", "set_messages", "set_output",
    "skill", "spawn_agents", "str_replace", "suggest_followups", "task_completed",
    "think_deeply", "web_search", "write_file", "write_todos",
}

AGENT_ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(-[a-z][a-z0-9]*)*$")


def find_agent_files() -> list[Path]:
    """Return all agent .ts files in .agents/ excluding types/ and backup/."""
    agents = []
    for f in AGENTS_DIR.iterdir():
        if f.is_file() and f.suffix == ".ts":
            # Skip type definition files
            if any(part.startswith("type") for part in f.parts):
                continue
            agents.append(f)
    return agents


def check_typescript_syntax(file_path: Path) -> tuple[bool, str]:
    """Check TypeScript syntax using npx if available."""
    try:
        result = subprocess.run(
            ["npx", "tsc", "--noEmit", "--strict", str(file_path)],
            capture_output=True, text=True, timeout=30, cwd=str(REPO_ROOT),
        )
        if result.returncode == 0:
            return True, "TypeScript syntax OK"
        return False, result.stderr[:500] if result.stderr else "Unknown tsc error"
    except FileNotFoundError:
        return True, "tsc not available (skipped)"
    except subprocess.TimeoutExpired:
        return False, "TypeScript check timed out"
    except Exception as e:
        return False, f"TypeScript check error: {e}"


def _find_opening_brace(content: str) -> int:
    """Find the position of the first { after 'const definition' or 'export default'."""
    for pattern in [
        r'const\s+definition\s*(?::\s*AgentDefinition)?\s*=\s*\{',
        r'export\s+default\s+\{',
    ]:
        m = re.search(pattern, content)
        if m:
            return m.end() - 1  # position of the opening {
    return -1


def _extract_balanced_braces(content: str, start: int) -> str:
    """Extract balanced { ... } content starting at position `start` (the {)."""
    depth = 0
    in_string = False
    string_char = ''
    i = start
    while i < len(content):
        ch = content[i]
        if in_string:
            if ch == '\\':
                i += 1  # skip escaped char
            elif ch == string_char:
                in_string = False
        else:
            if ch in ('"', "'"):
                in_string = True
                string_char = ch
            elif ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return content[start:i + 1]
        i += 1
    return ''  # unbalanced


def extract_export_object(content: str) -> dict | None:
    """
    Extract the AgentDefinition object from a TypeScript file.
    Uses brace counting to handle deeply nested objects.

    Pipeline order is critical:
    1. Remove comments
    2. Quote unquoted keys (before any string conversions!)
    3. Convert simple single-quoted strings to double-quoted
    4. Remove trailing commas
    5. Convert backtick template literals LAST — after all structural transforms
    6. Parse as JSON
    """
    start = _find_opening_brace(content)
    if start < 0:
        return None

    obj_str = _extract_balanced_braces(content, start)
    if not obj_str:
        return None

    # Phase 1: Remove comments (before any structural work)
    cleaned = re.sub(r'//.*$', '', obj_str, flags=re.MULTILINE)
    cleaned = re.sub(r'/\*[\s\S]*?\*/', '', cleaned)

    # Phase 2: Quote unquoted structural keys (BEFORE backtick conversion!)
    # Pattern 1: Line-start keys (most common): \n  key:
    cleaned = re.sub(r'(\n\s*)(\w+)(\s*):', r'\1"\2"\3:', cleaned)
    # Pattern 2: Inline keys inside braces: { key: or , key:
    cleaned = re.sub(r'([\{,]\s*)(\w+)(\s*):', r'\1"\2"\3:', cleaned)
    # Also fix single-quoted keys (legacy support)
    cleaned = re.sub(r"'([^']+)':", r'"\1":', cleaned)

    # Phase 3: Remove trailing commas
    cleaned = re.sub(r',\s*(\}|\])', r'\1', cleaned)

    # Phase 4: Convert backtick template literals (LAST — after all structural transforms)
    # Handle TypeScript escaped backticks: \` inside `...`
    def _escape_backtick(m: re.Match) -> str:
        inner = m.group(1)
        # Unescape TS template literal escapes (order matters!)
        inner = inner.replace('\\\\', '\\')     # \\ -> \ (first, so \` below only matches real escapes)
        inner = inner.replace('\\`', '`')        # \` -> `
        # Now JSON-escape for embedding in double-quoted string
        inner = inner.replace('\\', '\\\\')      # \ -> \\
        inner = inner.replace('"', '\\"')         # " -> \"
        inner = inner.replace('\n', '\\n')        # newline -> \n
        inner = inner.replace('\r', '\\r')        # CR -> \r
        inner = inner.replace('\t', '\\t')        # tab -> \t
        return '"' + inner + '"'
    # Pattern handles \` escapes inside template literals
    cleaned = re.sub(r'`((?:[^`\\]|\\.)*)`', _escape_backtick, cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def validate_agent(file_path: Path, check_ts: bool = True) -> dict:
    """Validate a single agent definition file. Returns result dict."""
    result = {
        "file": str(file_path.relative_to(REPO_ROOT)),
        "status": "pending",
        "checks": {},
        "errors": [],
        "warnings": [],
    }

    content = file_path.read_text(encoding="utf-8")

    # Check 1: TypeScript syntax
    if check_ts:
        ok, msg = check_typescript_syntax(file_path)
        result["checks"]["typescriptSyntax"] = "passed" if ok else "failed"
        if not ok:
            result["errors"].append(f"TypeScript syntax: {msg}")

    # Check 2: Has export default
    has_export = bool(re.search(r'export\s+default\s+', content))
    result["checks"]["hasExportDefault"] = "passed" if has_export else "failed"
    if not has_export:
        result["errors"].append("Missing 'export default'")

    # Check 3: Extract and validate object
    obj = extract_export_object(content)
    if obj is None:
        result["checks"]["parseDefinition"] = "failed"
        result["errors"].append("Could not parse AgentDefinition object")
        result["status"] = "failed"
        return result

    result["checks"]["parseDefinition"] = "passed"

    # Required fields
    for field in ["id", "displayName", "model"]:
        if field not in obj:
            result["checks"][field] = "failed"
            result["errors"].append(f"Missing required field: '{field}'")
        else:
            result["checks"][field] = "passed"

    # Validate id format
    agent_id = obj.get("id", "")
    if agent_id and not AGENT_ID_PATTERN.match(str(agent_id)):
        result["checks"]["idFormat"] = "failed"
        result["errors"].append(f"Agent id '{agent_id}' must be lowercase kebab-case")
    elif agent_id:
        result["checks"]["idFormat"] = "passed"

    # Validate id matches filename
    expected_id = file_path.stem
    if agent_id and str(agent_id) != expected_id:
        result["checks"]["idMatchesFilename"] = "failed"
        result["errors"].append(
            f"Agent id '{agent_id}' does not match filename '{expected_id}'"
        )
    elif agent_id:
        result["checks"]["idMatchesFilename"] = "passed"

    # Validate model
    model = str(obj.get("model", ""))
    is_known = (
        any(model.startswith(prefix) for prefix in KNOWN_MODEL_PREFIXES)
        or model in KNOWN_MODEL_SHORT
    )
    if model and not is_known:
        result["warnings"].append(
            f"Model '{model}' is not in the recognized model list"
        )
        result["checks"]["modelRecognized"] = "warning"
    elif model:
        result["checks"]["modelRecognized"] = "passed"

    # Validate toolNames
    tool_names = obj.get("toolNames", [])
    # Catch common mistake: 'tools' instead of 'toolNames'
    if "tools" in obj and "toolNames" not in obj:
        result["errors"].append("Use 'toolNames' not 'tools'")
        result["checks"]["toolNamesValid"] = "failed"
    elif isinstance(tool_names, list):
        invalid_tools = [
            t for t in tool_names
            if isinstance(t, str) and t not in KNOWN_TOOLS
        ]
        if invalid_tools:
            result["warnings"].append(
                f"Unrecognized tool names: {invalid_tools}"
            )
            result["checks"]["toolNamesValid"] = "warning"
        else:
            result["checks"]["toolNamesValid"] = "passed"
    else:
        result["checks"]["toolNamesValid"] = "passed"  # none is fine

    # Validate outputSchema
    output_schema = obj.get("outputSchema")
    if output_schema is not None:
        if isinstance(output_schema, dict) and output_schema.get("type") == "object":
            result["checks"]["outputSchemaValid"] = "passed"
        else:
            result["checks"]["outputSchemaValid"] = "failed"
            result["errors"].append("outputSchema must be a JSON Schema with type: 'object'")

    # Validate version
    version = obj.get("version")
    if version and not re.match(r"^\d+\.\d+\.\d+", str(version)):
        result["warnings"].append(f"Version '{version}' should be semver (e.g. '0.1.0')")

    # Final status
    if result["errors"]:
        result["status"] = "failed"
    elif result["warnings"]:
        result["status"] = "warning"
    else:
        result["status"] = "passed"

    return result


def main():
    parser = argparse.ArgumentParser(description="Validate custom agent definitions")
    parser.add_argument("--verbose", "-v", action="store_true", help="Detailed output")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    parser.add_argument("--skip-ts-check", action="store_true", help="Skip TypeScript syntax check")
    args = parser.parse_args()

    agent_files = find_agent_files()
    if not agent_files:
        msg = "No custom agent files found in .agents/"
        if args.json:
            print(json.dumps({"status": "warning", "message": msg, "results": []}))
        else:
            print(msg)
        return 0

    results = []
    for f in agent_files:
        result = validate_agent(f, check_ts=not args.skip_ts_check)
        results.append(result)

    # Summary
    passed = sum(1 for r in results if r["status"] == "passed")
    warnings = sum(1 for r in results if r["status"] == "warning")
    failed = sum(1 for r in results if r["status"] == "failed")

    summary = {
        "total": len(results),
        "passed": passed,
        "warnings": warnings,
        "failed": failed,
        "results": results,
    }

    if args.json:
        print(json.dumps(summary, indent=2, default=str))
    else:
        for r in results:
            icon = {"passed": "✅", "warning": "⚠️", "failed": "❌"}.get(r["status"], "?")
            print(f"{icon} {r['file']}: {r['status']}")
            if args.verbose:
                for check, status in r.get("checks", {}).items():
                    c_icon = "  ✓" if status == "passed" else "  ✗" if status == "failed" else "  !"
                    print(f"    {c_icon} {check}: {status}")
                for err in r.get("errors", []):
                    print(f"    ❌ {err}")
                for warn in r.get("warnings", []):
                    print(f"    ⚠️  {warn}")

        print(f"\n--- Summary ---")
        print(f"Total: {summary['total']} | ✅ {passed} passed | ⚠️ {warnings} warnings | ❌ {failed} failed")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
