#!/usr/bin/env python3
"""Canonical ChatGPT MCP tool-surface constants for RiftReader.

This module is intentionally dependency-free so adapter, recorder, workflow
state, final-readiness, and mission-control code can share the approved tool
surface without creating import cycles.
"""

from __future__ import annotations

EXPECTED_CHATGPT_MCP_TOOL_NAMES = (
    "health",
    "get_repo_status",
    "get_latest_handoff",
    "get_workflow_control_summary",
    "get_package_proposal_template",
    "submit_package_proposal",
    "list_inbox",
    "create_package_draft_from_inbox",
    "review_latest_package_draft",
    "dry_run_latest_package_draft",
    "apply_latest_package_draft",
    "get_workflow_control_plan",
    "get_dirty_paths",
    "get_recent_commits",
    "repo_tree_tracked",
    "repo_search_tracked",
    "repo_read_tracked_file",
    "repo_read_many_tracked_files",
    "repo_context_pack",
)
EXPECTED_CHATGPT_MCP_TOOL_COUNT = len(EXPECTED_CHATGPT_MCP_TOOL_NAMES)

PACKAGE_PROOF_TOOL_NAMES = (
    "get_package_proposal_template",
    "submit_package_proposal",
    "list_inbox",
    "create_package_draft_from_inbox",
    "review_latest_package_draft",
    "dry_run_latest_package_draft",
    "apply_latest_package_draft",
)
PACKAGE_PROOF_TOOL_COUNT = len(PACKAGE_PROOF_TOOL_NAMES)

PUBLIC_READ_ONLY_TOOL_NAMES = (
    "health",
    "get_repo_status",
    "get_latest_handoff",
    "get_workflow_control_summary",
    "get_workflow_control_plan",
)
PUBLIC_READ_ONLY_TOOL_COUNT = len(PUBLIC_READ_ONLY_TOOL_NAMES)

# END_OF_SCRIPT_MARKER
