#!/usr/bin/env python3
"""Environment checks for the IPO NotebookLM screen workflow."""

from __future__ import annotations

import json
import os
import shutil
import sys

from notebooklm_adapter import get_local_client_entry, probe_clients


def command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def main() -> int:
    probes = probe_clients()
    available_clients = [probe for probe in probes if probe.available]
    selected_with_file = next((probe for probe in available_clients if probe.supports_file), None)
    local_client_entry = get_local_client_entry()

    checks = [
        {
            "name": "python3",
            "ok": command_exists("python3"),
            "detail": shutil.which("python3") or "missing",
        },
        {
            "name": "node",
            "ok": command_exists("node"),
            "detail": shutil.which("node") or "missing",
        },
        {
            "name": "global_notebooklm",
            "ok": any(probe.name == "global" and probe.available for probe in probes),
            "detail": next((probe.error for probe in probes if probe.name == "global" and probe.error), "available"),
        },
        {
            "name": "local_notebooklm_source_build",
            "ok": bool(local_client_entry and local_client_entry.exists()),
            "detail": (
                str(local_client_entry)
                if local_client_entry and local_client_entry.exists()
                else "unset or missing; configure NOTEBOOKLM_CLIENT_ENTRY / NOTEBOOKLM_CLIENT_ROOT"
            ),
        },
        {
            "name": "httpx",
            "ok": _module_exists("httpx"),
            "detail": "installed" if _module_exists("httpx") else "pip install -r requirements.txt",
        },
    ]

    status = "ok" if all(item["ok"] for item in checks[:2]) and available_clients else "needs_attention"
    recommendations = []
    if not selected_with_file:
        recommendations.append("No NotebookLM client with file-upload support detected; local PDF ingestion will fail.")
    if not _module_exists("httpx"):
        recommendations.append("Install Python dependencies with `pip install -r requirements.txt`.")
    if not (local_client_entry and local_client_entry.exists()):
        recommendations.append(
            "Configure NOTEBOOKLM_CLIENT_ENTRY or NOTEBOOKLM_CLIENT_ROOT if you want to use a local notebooklm-client source build."
        )

    payload = {
        "status": status,
        "probe_mode": "capability_only",
        "notes": [
            "This probe checks local capability and helper availability; it does not guarantee runtime connectivity.",
            "If NotebookLM commands fail later under the default sandbox, the cause may be network restrictions rather than a missing client feature.",
        ],
        "checks": checks,
        "notebooklm_clients": [
            {
                "name": probe.name,
                "available": probe.available,
                "supports_file": probe.supports_file,
                "supports_url": probe.supports_url,
                "supports_create": probe.supports_create,
                "supports_configure": probe.supports_configure,
                "error": probe.error,
            }
            for probe in probes
        ],
        "selected_file_capable_client": selected_with_file.name if selected_with_file else None,
        "recommendations": recommendations,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if status == "ok" else 1


def _module_exists(module_name: str) -> bool:
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


if __name__ == "__main__":
    sys.exit(main())
