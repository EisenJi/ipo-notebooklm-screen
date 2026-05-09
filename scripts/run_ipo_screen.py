#!/usr/bin/env python3
"""Orchestrate CNInfo collection and hand off to a selected backend."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backends import get_backend
from notebooklm_adapter import NotebookLMError, probe_clients


AUTO_NOTEBOOKLM_SOURCE_THRESHOLD = 10
AUTO_NOTEBOOKLM_PEER_THRESHOLD = 3
AUTO_NOTEBOOKLM_NOTEBOOK_THRESHOLD = 2
AUTO_NOTEBOOKLM_OBJECTIVE_SOURCE_FLOOR = 5


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an IPO NotebookLM screen from a JSON spec")
    parser.add_argument("--spec", required=True, help="Path to workflow spec JSON")
    parser.add_argument(
        "--backend",
        choices=["manifest_only", "notebooklm"],
        help="Override backend from the spec. Defaults to manifest_only.",
    )
    parser.add_argument(
        "--backend-policy",
        choices=["required", "auto", "forbid"],
        help="Override backend policy from the spec.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    from cninfo_fetch import CninfoFetcher, ReportRequest

    spec_path = Path(args.spec).resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["_spec_dir"] = str(spec_path.parent)

    workspace = resolve_spec_relative(spec_path.parent, str(spec["workspace"]))
    workspace.mkdir(parents=True, exist_ok=True)

    requested_backend_name = args.backend or spec.get("backend", "manifest_only")
    backend_policy = args.backend_policy or spec.get("backend_policy", "auto")

    summary = {
        "issuer": spec["issuer"],
        "workspace": str(workspace),
        "backend_requested": requested_backend_name,
        "backend_policy": backend_policy,
        "backend_effective": None,
        "policy_reason": None,
        "notebooklm_readiness": None,
        "notebooks": [],
    }

    fetcher = CninfoFetcher()
    readiness = assess_notebooklm_readiness(spec)
    planned_backend_name, policy_reason = resolve_backend_plan(
        spec,
        requested_backend_name,
        backend_policy,
        readiness,
    )
    if planned_backend_name == "notebooklm":
        ensure_notebooklm_ready(backend_policy, policy_reason, readiness)
    backend = get_backend(str(planned_backend_name))
    summary["backend_effective"] = backend.name
    summary["policy_reason"] = policy_reason
    summary["notebooklm_readiness"] = readiness

    for notebook_spec in spec["notebooks"]:
        notebook_summary = {
            "title": notebook_spec["title"],
            "materials": [],
            "notebook_id": None,
            "backend": backend.name,
            "backend_policy": backend_policy,
            "uploaded_sources": [],
            "notes": [],
        }

        for source in notebook_spec["sources"]:
            kind = source["kind"]
            if kind == "cninfo_reports":
                request = ReportRequest(
                    code=source["code"],
                    org_id=source["org_id"],
                    market=source["market"],
                    label=source["label"],
                    role=source["role"],
                    scope=source.get("scope", "latest"),
                )
                manifest = fetcher.fetch_latest_reports(
                    request=request,
                    output_root=workspace,
                    reporting_year=source["reporting_year"],
                )
                notebook_summary["materials"].append(manifest)
            elif kind == "file":
                notebook_summary["materials"].append({"kind": "file", "path": str(Path(source["path"]).resolve())})
            elif kind == "url":
                notebook_summary["materials"].append({"kind": "url", "url": source["url"]})
            else:
                raise ValueError(f"Unsupported source kind: {kind}")

        backend_result = backend.process(
            spec=spec,
            notebook_spec=notebook_spec,
            materials=notebook_summary["materials"],
        )
        notebook_summary["notebook_id"] = backend_result.notebook_id
        notebook_summary["uploaded_sources"] = backend_result.uploaded_sources
        notebook_summary["notes"] = backend_result.notes

        summary["notebooks"].append(notebook_summary)

    summary_path = workspace / "run-summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def resolve_spec_relative(spec_dir: Path, raw_path: str) -> Path:
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    return (spec_dir / candidate).resolve()


def resolve_backend_plan(
    spec: dict[str, object],
    requested_backend_name: str,
    backend_policy: str,
    readiness: dict[str, object],
) -> tuple[str, str]:
    if backend_policy == "forbid":
        return "manifest_only", "backend_policy=forbid"
    if backend_policy == "required":
        return "notebooklm", "backend_policy=required"

    assert backend_policy == "auto"
    auto_reason = detect_notebooklm_need(spec)
    if requested_backend_name == "notebooklm":
        if readiness["usable"]:
            return "notebooklm", "explicit backend=requested"
        return "manifest_only", (
            "explicit backend=requested but NotebookLM is not safely usable: "
            f"{readiness['reason']}"
        )
    if auto_reason:
        if readiness["usable"]:
            return "notebooklm", auto_reason
        return "manifest_only", (
            f"{auto_reason}; stayed on manifest_only because {readiness['reason']}"
        )
    return "manifest_only", "auto policy kept local manifest path"


def detect_notebooklm_need(spec: dict[str, object]) -> str | None:
    notebooks = spec.get("notebooks", [])
    if len(notebooks) >= AUTO_NOTEBOOKLM_NOTEBOOK_THRESHOLD:
        return "auto policy: multiple notebooks imply multi-segment analysis"

    peer_sources = 0
    total_sources = 0
    for notebook_spec in notebooks:
        for source in notebook_spec.get("sources", []):
            total_sources += 1
            if source.get("kind") == "cninfo_reports":
                peer_sources += 1

    if total_sources >= AUTO_NOTEBOOKLM_SOURCE_THRESHOLD:
        return (
            "auto policy: large material set "
            f"({total_sources} sources >= {AUTO_NOTEBOOKLM_SOURCE_THRESHOLD})"
        )
    if peer_sources >= AUTO_NOTEBOOKLM_PEER_THRESHOLD:
        return (
            "auto policy: peer comparison is large "
            f"({peer_sources} peer report sources >= {AUTO_NOTEBOOKLM_PEER_THRESHOLD})"
        )

    objective = str(spec.get("analysis_objective", ""))
    objective_lower = objective.lower()
    objective_keywords = ["notebooklm", "source-ids", "save token", "multi-round"]
    if any(keyword in objective_lower for keyword in objective_keywords):
        if total_sources >= AUTO_NOTEBOOKLM_OBJECTIVE_SOURCE_FLOOR or peer_sources >= 2:
            return "auto policy: objective and material volume jointly benefit from NotebookLM"

    return None


def assess_notebooklm_readiness(spec: dict[str, object]) -> dict[str, object]:
    probes = probe_clients()
    file_capable = [probe for probe in probes if probe.available and probe.supports_file]
    create_capable = [probe for probe in file_capable if probe.supports_create]
    notebook_ids = [
        notebook.get("notebook_id")
        for notebook in spec.get("notebooks", [])
        if isinstance(notebook, dict)
    ]
    all_notebooks_have_ids = bool(notebook_ids) and all(bool(notebook_id) for notebook_id in notebook_ids)

    usable = bool(file_capable) and (all_notebooks_have_ids or bool(create_capable))
    if not file_capable:
        reason = "no file-capable NotebookLM client detected"
    elif all_notebooks_have_ids:
        reason = "all notebooks already provide notebook_id"
    elif create_capable:
        reason = "a file-capable NotebookLM client can create notebooks"
    else:
        reason = "missing notebook_id and no file-capable client with create support"

    return {
        "usable": usable,
        "reason": reason,
        "probe_mode": "capability_only",
        "file_capable_clients": [probe.name for probe in file_capable],
        "create_capable_clients": [probe.name for probe in create_capable],
        "all_notebooks_have_ids": all_notebooks_have_ids,
        "missing_notebook_id_count": sum(1 for notebook_id in notebook_ids if not notebook_id),
        "network_caveat": (
            "Runtime NotebookLM commands may still fail in the default sandbox due to network restrictions. "
            "Treat this readiness result as capability detection, not connectivity confirmation."
        ),
    }


def ensure_notebooklm_ready(policy: str, reason: str, readiness: dict[str, object]) -> None:
    if readiness["usable"]:
        return

    recommendation = (
        "NotebookLM backend required by policy but the current environment is not safely executable. "
        "Run `python3 scripts/preflight.py` and "
        "`python3 scripts/notebooklm_adapter.py inspect --needs-file`, "
        "then either provide `notebook_id` for every notebook or use a client that supports create. "
        "Otherwise switch policy to `forbid`."
    )
    raise NotebookLMError(f"{reason}. Readiness: {readiness['reason']}. {recommendation}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, NotebookLMError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
