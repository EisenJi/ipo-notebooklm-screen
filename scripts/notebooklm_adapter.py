#!/usr/bin/env python3
"""NotebookLM client adapter with capability detection and basic operations."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


LOCAL_CREATE_HELPER = Path(__file__).resolve().parent / "notebooklm_create.mjs"
UUID_RE = re.compile(r"[a-f0-9-]{36}", re.IGNORECASE)


class NotebookLMError(RuntimeError):
    """Raised when a NotebookLM command cannot be completed."""


@dataclass
class ClientProbe:
    """Describes one available NotebookLM client."""

    name: str
    kind: str
    command: list[str]
    available: bool
    supports_file: bool
    supports_url: bool
    supports_create: bool
    supports_configure: bool
    help_excerpt: str | None = None
    error: str | None = None


def _run_command(command: list[str], *, timeout: int = 120, cwd: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        cwd=cwd,
    )


def _safe_help(command: list[str]) -> tuple[bool, str]:
    try:
        result = _run_command(command + ["--help"], timeout=30)
        output = (result.stdout or "") + (result.stderr or "")
        return result.returncode == 0, output
    except Exception as exc:  # pragma: no cover - defensive shell integration
        return False, str(exc)


def _command_supported(command: list[str]) -> tuple[bool, str]:
    return _safe_help(command)


def _build_probe(name: str, kind: str, command: list[str]) -> ClientProbe:
    available, help_output = _safe_help(command)
    if not available:
        return ClientProbe(
            name=name,
            kind=kind,
            command=command,
            available=False,
            supports_file=False,
            supports_url=False,
            supports_create=False,
            supports_configure=False,
            error=help_output.strip() or "notebooklm not found",
        )

    root_help_normalized = normalize_help_output(help_output)
    source_add_ok, source_add_help = _command_supported(command + ["source", "add", "--help"])
    create_ok, create_help = _command_supported(command + ["create", "--help"])
    configure_ok, configure_help = _command_supported(command + ["configure", "--help"])
    source_lowered = source_add_help.lower() if source_add_ok else ""
    create_supported = (
        (create_ok and normalize_help_output(create_help) != root_help_normalized)
        or (name == "local_source_build" and LOCAL_CREATE_HELPER.exists())
    )
    configure_supported = configure_ok and normalize_help_output(configure_help) != root_help_normalized
    return ClientProbe(
        name=name,
        kind=kind,
        command=command,
        available=True,
        supports_file="--file" in source_lowered,
        supports_url="--url" in source_lowered,
        supports_create=create_supported,
        supports_configure=configure_supported,
        help_excerpt="\n".join(help_output.splitlines()[:30]),
    )


def normalize_help_output(output: str) -> str:
    return "\n".join(line.rstrip() for line in output.strip().splitlines())


def get_local_client_root() -> Path | None:
    root = os.environ.get("NOTEBOOKLM_CLIENT_ROOT")
    if root:
        return Path(root).expanduser().resolve()
    repo = _find_client_repo()
    if repo:
        return repo
    return None


def _find_client_repo() -> Path | None:
    """Auto-discover notebooklm-client repo in common locations."""
    skill_scripts = Path(__file__).resolve().parent
    candidates = [
        skill_scripts.parent / "notebooklm-client",           # sibling to skill
        Path.home() / ".codex" / "skills" / "notebooklm-client",
        Path.home() / "codes" / "notebooklm-client",
        Path.home() / "notebooklm-client",
        Path.home() / ".local" / "lib" / "notebooklm-client",
    ]
    for c in candidates:
        if (c / "dist" / "cli.js").exists() and (c / "dist" / "index.js").exists():
            return c
    return None


def _ensure_client_repo() -> Path | None:
    """Auto-clone and build notebooklm-client if missing."""
    existing = _find_client_repo()
    if existing:
        return existing

    target = Path.home() / ".codex" / "skills" / "notebooklm-client"
    target.parent.mkdir(parents=True, exist_ok=True)

    if not (target / ".git").exists():
        clone_result = _run_command(
            ["git", "clone", "https://github.com/icebear0828/notebooklm-client.git", str(target)],
            timeout=120,
        )
        if clone_result.returncode != 0:
            return None

    if not (target / "dist" / "cli.js").exists():
        npm_install = _run_command(["npm", "install"], timeout=120, cwd=str(target))
        if npm_install.returncode != 0:
            return None
        npm_build = _run_command(["npm", "run", "build"], timeout=120, cwd=str(target))
        if npm_build.returncode != 0:
            return None

    if (target / "dist" / "cli.js").exists():
        return target
    return None


def get_local_client_entry() -> Path | None:
    entry = os.environ.get("NOTEBOOKLM_CLIENT_ENTRY")
    if entry:
        return Path(entry).expanduser().resolve()
    root = get_local_client_root()
    if root:
        return root / "dist" / "cli.js"
    repo = _find_client_repo()
    if repo:
        return repo / "dist" / "cli.js"
    return None


def probe_global_cli() -> ClientProbe:
    return _build_probe("global", "cli", ["notebooklm"])


def probe_local_cli() -> ClientProbe:
    client_entry = get_local_client_entry()
    if not client_entry:
        repo = _ensure_client_repo()
        if repo:
            client_entry = repo / "dist" / "cli.js"

    if not client_entry:
        return ClientProbe(
            name="local_source_build",
            kind="node",
            command=["node", "<no notebooklm-client found>"],
            available=False,
            supports_file=False,
            supports_url=False,
            supports_create=False,
            supports_configure=False,
            error="notebooklm-client not found and auto-clone failed. Set NOTEBOOKLM_CLIENT_ENTRY / NOTEBOOKLM_CLIENT_ROOT, or ensure git and npm are available",
        )

    command = ["node", str(client_entry)]
    if not client_entry.exists():
        return ClientProbe(
            name="local_source_build",
            kind="node",
            command=command,
            available=False,
            supports_file=False,
            supports_url=False,
            supports_create=False,
            supports_configure=False,
            error=f"{client_entry} not found",
        )

    return _build_probe("local_source_build", "node", command)


def probe_clients() -> list[ClientProbe]:
    return [probe_global_cli(), probe_local_cli()]


def choose_client(*, needs_file: bool = False) -> ClientProbe:
    candidates = [probe for probe in probe_clients() if probe.available]
    if needs_file:
        candidates = [probe for probe in candidates if probe.supports_file]
    if not candidates:
        raise NotebookLMError("No compatible NotebookLM client found")
    candidates.sort(key=lambda probe: (probe.name != "global", not probe.supports_file))
    return candidates[0]


class NotebookLMAdapter:
    """Thin wrapper around an available NotebookLM client."""

    def __init__(self, probe: ClientProbe):
        self.probe = probe

    @classmethod
    def autodetect(cls, *, needs_file: bool = False) -> "NotebookLMAdapter":
        return cls(choose_client(needs_file=needs_file))

    def _run(self, args: Iterable[str], *, timeout: int = 300) -> str:
        result = _run_command(self.probe.command + list(args), timeout=timeout)
        output = ((result.stdout or "") + (result.stderr or "")).strip()
        if result.returncode != 0:
            raise NotebookLMError(output or f"NotebookLM command failed: {' '.join(args)}")
        return output

    def create_notebook(self, title: str) -> str:
        if self.probe.name == "local_source_build" and LOCAL_CREATE_HELPER.exists():
            result = _run_command(["node", str(LOCAL_CREATE_HELPER), title], timeout=180)
            output = ((result.stdout or "") + (result.stderr or "")).strip()
            if result.returncode != 0:
                raise NotebookLMError(output or "Local NotebookLM create helper failed")
            match = UUID_RE.search(output)
            if not match:
                raise NotebookLMError(f"Could not parse notebook id from helper output: {output}")
            return match.group(0)

        output = self._run(["create", title], timeout=120)
        match = UUID_RE.search(output)
        if not match:
            raise NotebookLMError(f"Could not parse notebook id from output: {output}")
        return match.group(0)

    def configure_persona(self, notebook_id: str, prompt_text: str) -> str:
        if not self.probe.supports_configure:
            raise NotebookLMError("Selected NotebookLM client does not support configure")
        args = [
            "configure",
            "--notebook",
            notebook_id,
            "--persona",
            prompt_text,
            "--response-length",
            "longer",
        ]
        return self._run(args, timeout=180)

    def add_file(self, notebook_id: str, path: Path) -> str:
        if not self.probe.supports_file:
            raise NotebookLMError("Selected NotebookLM client does not support file upload")
        return self._run(["source", "add", notebook_id, "--file", str(path)], timeout=300)

    def add_url(self, notebook_id: str, url: str) -> str:
        if not self.probe.supports_url:
            raise NotebookLMError("Selected NotebookLM client does not support URL sources")
        return self._run(["source", "add", notebook_id, "--url", url], timeout=180)

    def detail(self, notebook_id: str) -> str:
        return self._run(["detail", notebook_id], timeout=120)


def load_prompt(prompt_path: Path) -> str:
    return prompt_path.read_text(encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="NotebookLM client adapter")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Probe available clients")
    inspect_parser.add_argument("--needs-file", action="store_true")

    create_parser = subparsers.add_parser("create", help="Create notebook and print id")
    create_parser.add_argument("title")
    create_parser.add_argument("--needs-file", action="store_true")

    configure_parser = subparsers.add_parser("configure", help="Apply persona prompt")
    configure_parser.add_argument("notebook_id")
    configure_parser.add_argument("prompt_file")
    configure_parser.add_argument("--needs-file", action="store_true")

    add_file_parser = subparsers.add_parser("add-file", help="Upload file source")
    add_file_parser.add_argument("notebook_id")
    add_file_parser.add_argument("path")

    add_url_parser = subparsers.add_parser("add-url", help="Upload URL source")
    add_url_parser.add_argument("notebook_id")
    add_url_parser.add_argument("url")
    add_url_parser.add_argument("--needs-file", action="store_true")

    detail_parser = subparsers.add_parser("detail", help="Show notebook details")
    detail_parser.add_argument("notebook_id")
    detail_parser.add_argument("--needs-file", action="store_true")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "inspect":
        probes = probe_clients()
        payload = {
            "selected": asdict(choose_client(needs_file=args.needs_file)) if any(
                p.available and (not args.needs_file or p.supports_file) for p in probes
            ) else None,
            "clients": [asdict(probe) for probe in probes],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    try:
        adapter = NotebookLMAdapter.autodetect(needs_file=getattr(args, "needs_file", False))
        if args.command == "create":
            print(adapter.create_notebook(args.title))
        elif args.command == "configure":
            print(adapter.configure_persona(args.notebook_id, load_prompt(Path(args.prompt_file))))
        elif args.command == "add-file":
            print(adapter.add_file(args.notebook_id, Path(args.path).resolve()))
        elif args.command == "add-url":
            print(adapter.add_url(args.notebook_id, args.url))
        elif args.command == "detail":
            print(adapter.detail(args.notebook_id))
        return 0
    except NotebookLMError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
