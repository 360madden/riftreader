from __future__ import annotations

import argparse
import html
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

from .reports import write_json, write_text_atomic


SCHEMA_VERSION = 1


def utc_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def list_or_empty(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def path_text(path: Path | str | None, repo_root: Path) -> str | None:
    if path is None:
        return None
    resolved = Path(str(path))
    try:
        return str(resolved.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
    except ValueError:
        return str(resolved)


def resolve_path(repo_root: Path, value: Path | str | None) -> Path | None:
    if value in (None, ""):
        return None
    path = Path(str(value))
    return path if path.is_absolute() else repo_root / path


def html_escape(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def load_latest_route(repo_root: Path, route_summary: Path | None) -> tuple[dict[str, Any] | None, str | None]:
    route_path = route_summary or repo_root / "scripts" / "captures" / "latest-coordinate-proof-route.json"
    route_path = route_path if route_path.is_absolute() else repo_root / route_path
    if not route_path.exists():
        return None, f"route-summary-missing:{path_text(route_path, repo_root)}"
    route = read_json_object(route_path)
    if route.get("kind") == "latest-coordinate-proof-route-pointer":
        summary_path = resolve_path(repo_root, route.get("summaryJson"))
        if summary_path is None or not summary_path.exists():
            return route, f"route-pointer-summary-missing:{route.get('summaryJson')}"
        resolved = read_json_object(summary_path)
        resolved["path"] = path_text(summary_path, repo_root)
        resolved["pointerPath"] = path_text(route_path, repo_root)
        return resolved, None
    route["path"] = path_text(route_path, repo_root)
    return route, None


def as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def collect_candidate_comparison(repo_root: Path, truth: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
    routing = dict_or_empty(route.get("candidateRouting"))
    items = [dict_or_empty(item) for item in list_or_empty(routing.get("candidateComparisons"))]
    if items:
        return {
            "source": "route",
            "items": items,
            "rawBothReferenceMatchCount": sum(as_int(item.get("rawBothReferenceMatchCount")) for item in items),
            "validBothReferenceMatchCount": sum(as_int(item.get("bothReferenceMatchCount")) for item in items),
            "blockers": list(dict.fromkeys(str(blocker) for item in items for blocker in list_or_empty(item.get("blockers")))),
        }

    visual = dict_or_empty(truth.get("visualEvidenceRouting"))
    comparison_path = resolve_path(repo_root, visual.get("latestCandidateComparison"))
    if comparison_path and comparison_path.exists():
        comparison = read_json_object(comparison_path)
        files = [dict_or_empty(item) for item in list_or_empty(comparison.get("candidateFiles"))]
        raw_count = sum(as_int(item.get("bothReferenceMatchCount")) for item in files)
        valid_count = raw_count if comparison.get("status") == "api-candidate-two-reference-match" and not comparison.get("blockers") else 0
        return {
            "source": "current-truth-latestCandidateComparison",
            "items": [
                {
                    "path": path_text(comparison_path, repo_root),
                    "status": comparison.get("status"),
                    "rawBothReferenceMatchCount": raw_count,
                    "bothReferenceMatchCount": valid_count,
                    "blockers": list_or_empty(comparison.get("blockers")),
                }
            ],
            "rawBothReferenceMatchCount": raw_count,
            "validBothReferenceMatchCount": valid_count,
            "blockers": [str(item) for item in list_or_empty(comparison.get("blockers"))],
        }

    return {
        "source": "absent",
        "items": [],
        "rawBothReferenceMatchCount": 0,
        "validBothReferenceMatchCount": 0,
        "blockers": [],
    }


def first_planar_distance(truth: dict[str, Any], route: dict[str, Any]) -> Any:
    readiness = dict_or_empty(route.get("displacedReadiness"))
    for item in list_or_empty(readiness.get("items")):
        item_map = dict_or_empty(item)
        if item_map.get("planarDistance") is not None:
            return item_map.get("planarDistance")
    visual = dict_or_empty(truth.get("visualEvidenceRouting"))
    return visual.get("latestDisplacedReferencePlanarDistance")


def compact_blockers(truth: dict[str, Any], route: dict[str, Any], comparison: dict[str, Any]) -> list[str]:
    promotion = dict_or_empty(route.get("promotionReadiness"))
    values = [
        *[str(item) for item in list_or_empty(truth.get("currentBlockers"))],
        *[str(item) for item in list_or_empty(route.get("blockers"))],
        *[str(item) for item in list_or_empty(promotion.get("blockers"))],
        *[str(item) for item in list_or_empty(comparison.get("blockers"))],
    ]
    return list(dict.fromkeys(item for item in values if item))[:12]


def build_summary(*, repo_root: Path, truth_json: Path, route_summary: Path | None) -> dict[str, Any]:
    truth = read_json_object(truth_json)
    route, route_issue = load_latest_route(repo_root, route_summary)
    route_map = route or {}
    target = dict_or_empty(route_map.get("target")) or dict_or_empty(truth.get("target"))
    movement = dict_or_empty(truth.get("movementGate"))
    candidate = dict_or_empty(truth.get("bestCurrentCandidate"))
    visual = dict_or_empty(truth.get("visualEvidenceRouting"))
    promotion = dict_or_empty(route_map.get("promotionReadiness"))
    comparison = collect_candidate_comparison(repo_root, truth, route_map)
    blockers = compact_blockers(truth, route_map, comparison)
    if route_issue:
        blockers.insert(0, route_issue)

    return {
        "schemaVersion": SCHEMA_VERSION,
        "mode": "riftreader-current-truth-compact-summary",
        "generatedAtUtc": utc_iso(),
        "status": truth.get("status"),
        "truthJson": path_text(truth_json, repo_root),
        "routeSummary": route_map.get("path") or path_text(route_summary, repo_root),
        "target": {
            "processName": target.get("processName"),
            "processId": target.get("processId"),
            "targetWindowHandle": target.get("targetWindowHandle"),
            "processStartUtc": target.get("processStartUtc"),
        },
        "movementGate": {
            "allowed": movement.get("allowed") is True,
            "status": movement.get("status"),
            "reason": movement.get("reason"),
        },
        "candidate": {
            "candidateId": candidate.get("candidateId"),
            "addressHex": candidate.get("addressHex") or candidate.get("address"),
            "status": candidate.get("status"),
            "candidateFile": candidate.get("candidateFile"),
            "readbackSummary": candidate.get("readbackSummary"),
        },
        "route": {
            "status": route_map.get("status") or visual.get("latestRouteStatus"),
            "readOnlyProofAllowed": dict_or_empty(route_map.get("decision")).get("readOnlyProofAllowed"),
            "movementAllowed": False,
            "promotionReadinessStatus": promotion.get("status") or visual.get("latestPromotionReadinessStatus"),
            "proofAnchorPromotionAllowed": promotion.get("proofAnchorPromotionAllowed") is True,
            "latestProofRouteHtml": dict_or_empty(route_map.get("artifacts")).get("summaryHtml")
            or visual.get("latestProofRouteHtml"),
        },
        "candidateComparison": comparison,
        "displacedReadiness": {
            "status": dict_or_empty(route_map.get("displacedReadiness")).get("status")
            or visual.get("latestDisplacedReadinessStatus"),
            "planarDistance": first_planar_distance(truth, route_map),
        },
        "blockers": blockers,
        "nextRecommendedAction": truth.get("nextRecommendedAction")
        or "Capture a fresh manually displaced pose before promoting the coordinate candidate.",
        "safety": {
            "movementSent": False,
            "inputSent": False,
            "reloaduiSent": False,
            "screenshotKeySent": False,
            "noCheatEngine": True,
            "x64dbgAttached": False,
            "providerWrite": False,
            "githubConnectorWrites": False,
        },
    }


def render_markdown(summary: dict[str, Any]) -> str:
    target = dict_or_empty(summary.get("target"))
    movement = dict_or_empty(summary.get("movementGate"))
    candidate = dict_or_empty(summary.get("candidate"))
    route = dict_or_empty(summary.get("route"))
    comparison = dict_or_empty(summary.get("candidateComparison"))
    displaced = dict_or_empty(summary.get("displacedReadiness"))
    lines = [
        "# RiftReader current truth compact summary",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Generated | `{summary.get('generatedAtUtc')}` |",
        f"| Status | `{summary.get('status')}` |",
        f"| Target | `{target.get('processName')}` PID `{target.get('processId')}`, HWND `{target.get('targetWindowHandle')}` |",
        f"| Movement allowed | `{str(movement.get('allowed')).lower()}` |",
        f"| Movement reason | `{movement.get('reason')}` |",
        f"| Candidate | `{candidate.get('candidateId')}` at `{candidate.get('addressHex')}` |",
        f"| Route | `{route.get('status')}` |",
        f"| Promotion readiness | `{route.get('promotionReadinessStatus')}` |",
        f"| Raw both-reference matches | `{comparison.get('rawBothReferenceMatchCount')}` |",
        f"| Valid both-reference matches | `{comparison.get('validBothReferenceMatchCount')}` |",
        f"| Displaced readiness | `{displaced.get('status')}` / planar `{displaced.get('planarDistance')}` |",
        f"| Next | `{summary.get('nextRecommendedAction')}` |",
        "",
        "## Blockers",
        "",
    ]
    blockers = list_or_empty(summary.get("blockers"))
    lines.extend(f"- `{item}`" for item in blockers) if blockers else lines.append("- None")
    return "\n".join(lines).rstrip() + "\n"


def render_html(summary: dict[str, Any]) -> str:
    target = dict_or_empty(summary.get("target"))
    movement = dict_or_empty(summary.get("movementGate"))
    candidate = dict_or_empty(summary.get("candidate"))
    route = dict_or_empty(summary.get("route"))
    comparison = dict_or_empty(summary.get("candidateComparison"))
    displaced = dict_or_empty(summary.get("displacedReadiness"))
    blockers = list_or_empty(summary.get("blockers"))
    blocker_items = "\n".join(f"<li>{html_escape(item)}</li>" for item in blockers) or "<li>None</li>"
    facts = [
        ("Generated", summary.get("generatedAtUtc")),
        ("Status", summary.get("status")),
        ("Target", f"{target.get('processName')} PID {target.get('processId')} HWND {target.get('targetWindowHandle')}"),
        ("Movement reason", movement.get("reason")),
        ("Candidate file", candidate.get("candidateFile")),
        ("Readback summary", candidate.get("readbackSummary")),
        ("Route HTML", route.get("latestProofRouteHtml")),
        ("Next", summary.get("nextRecommendedAction")),
    ]
    fact_rows = "\n".join(
        f"<tr><th>{html_escape(name)}</th><td>{html_escape(value)}</td></tr>" for name, value in facts
    )
    movement_class = "ok" if movement.get("allowed") is True else "bad"
    promotion_class = "ok" if route.get("proofAnchorPromotionAllowed") is True else "warn"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RiftReader current truth compact summary</title>
<style>
body{{margin:0;font-family:"Segoe UI",system-ui,sans-serif;background:#08111f;color:#e5eefb}}
header,main{{max-width:1180px;margin:auto;padding:28px}}
header{{border-bottom:1px solid #263a57}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:18px 0}}
.card{{background:#0f1b2e;border:1px solid #263a57;border-radius:18px;padding:16px;box-shadow:0 12px 28px #0006}}
.metric{{font-size:25px;font-weight:850;margin-top:6px}}
.muted{{color:#a7b7d5}}
.pill{{display:inline-block;border-radius:999px;padding:4px 10px;font-weight:800}}
.ok{{background:#14532d;color:#bbf7d0}}.warn{{background:#713f12;color:#fde68a}}.bad{{background:#7f1d1d;color:#fecaca}}
table{{width:100%;border-collapse:collapse;background:#0f1b2e;border:1px solid #263a57;border-radius:14px;overflow:hidden}}
th,td{{padding:11px 13px;border-bottom:1px solid #263a57;text-align:left;vertical-align:top}}
th{{color:#bae6fd;width:260px}}tr:last-child th,tr:last-child td{{border-bottom:0}}
code{{background:#020817;border:1px solid #263a57;padding:2px 6px;border-radius:6px;color:#bfdbfe}}
li{{margin:6px 0}}@media(max-width:900px){{.grid{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<header>
<h1>RiftReader current truth compact summary</h1>
<p class="muted">Timestamped, human-readable proof state. Movement remains blocked unless explicitly shown otherwise.</p>
</header>
<main>
<section class="grid">
<div class="card"><div class="muted">Route</div><div class="metric">{html_escape(route.get("status"))}</div></div>
<div class="card"><div class="muted">Movement</div><div class="metric"><span class="pill {movement_class}">{html_escape(str(movement.get("allowed")).lower())}</span></div></div>
<div class="card"><div class="muted">Promotion</div><div class="metric"><span class="pill {promotion_class}">{html_escape(route.get("promotionReadinessStatus"))}</span></div></div>
<div class="card"><div class="muted">Candidate</div><div class="metric">{html_escape(candidate.get("candidateId"))}</div><code>{html_escape(candidate.get("addressHex"))}</code></div>
</section>
<section class="card">
<h2>Proof counts</h2>
<table>
<tr><th>Raw both-reference matches</th><td>{html_escape(comparison.get("rawBothReferenceMatchCount"))}</td></tr>
<tr><th>Valid both-reference matches</th><td>{html_escape(comparison.get("validBothReferenceMatchCount"))}</td></tr>
<tr><th>Displaced readiness</th><td>{html_escape(displaced.get("status"))}</td></tr>
<tr><th>Displaced planar distance</th><td>{html_escape(displaced.get("planarDistance"))}</td></tr>
</table>
</section>
<section class="card"><h2>Facts</h2><table>{fact_rows}</table></section>
<section class="card"><h2>Blockers</h2><ul>{blocker_items}</ul></section>
</main>
</body>
</html>
"""


def update_current_truth_artifacts(
    *, truth_path: Path, repo_root: Path, summary_json: Path, summary_markdown: Path, summary_html: Path
) -> None:
    truth = read_json_object(truth_path)
    truth["updatedAtUtc"] = utc_iso()
    canonical = truth.setdefault("canonicalArtifacts", {})
    if not isinstance(canonical, dict):
        canonical = {}
        truth["canonicalArtifacts"] = canonical
    canonical["latestCompactTruthJson"] = path_text(summary_json, repo_root)
    canonical["latestCompactTruthSummary"] = path_text(summary_markdown, repo_root)
    canonical["latestCompactTruthHtml"] = path_text(summary_html, repo_root)
    visual = truth.setdefault("visualEvidenceRouting", {})
    if isinstance(visual, dict):
        visual["latestCompactTruthJson"] = path_text(summary_json, repo_root)
        visual["latestCompactTruthSummary"] = path_text(summary_markdown, repo_root)
        visual["latestCompactTruthHtml"] = path_text(summary_html, repo_root)
    write_json(truth_path, truth)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write a compact human-readable current-truth summary.")
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_module())
    parser.add_argument("--truth-json", type=Path, default=Path("docs/recovery/current-truth.json"))
    parser.add_argument("--route-summary", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("docs/recovery"))
    parser.add_argument("--update-current-truth", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    truth_path = args.truth_json if args.truth_json.is_absolute() else repo_root / args.truth_json
    output_dir = args.output_dir if args.output_dir.is_absolute() else repo_root / args.output_dir
    stamp = utc_stamp()
    summary_json = output_dir / f"current-truth-compact-summary-{stamp}.json"
    summary_md = output_dir / f"current-truth-compact-summary-{stamp}.md"
    summary_html = output_dir / f"current-truth-compact-summary-{stamp}.html"
    summary = build_summary(repo_root=repo_root, truth_json=truth_path, route_summary=args.route_summary)
    summary["artifacts"] = {
        "summaryJson": path_text(summary_json, repo_root),
        "summaryMarkdown": path_text(summary_md, repo_root),
        "summaryHtml": path_text(summary_html, repo_root),
    }
    write_json(summary_json, summary)
    write_text_atomic(summary_md, render_markdown(summary))
    write_text_atomic(summary_html, render_html(summary))
    if args.update_current_truth:
        update_current_truth_artifacts(
            truth_path=truth_path,
            repo_root=repo_root,
            summary_json=summary_json,
            summary_markdown=summary_md,
            summary_html=summary_html,
        )
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(json.dumps({"status": summary.get("status"), "summaryHtml": path_text(summary_html, repo_root)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
