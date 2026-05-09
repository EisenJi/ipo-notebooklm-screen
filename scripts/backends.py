#!/usr/bin/env python3
"""Backend abstractions for post-collection material handling."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from notebooklm_adapter import NotebookLMAdapter, NotebookLMError, load_prompt


@dataclass
class BackendResult:
    backend: str
    notebook_id: str | None
    uploaded_sources: list[str]
    notes: list[str]


class WorkflowBackend:
    """Abstract backend for collected materials."""

    name = "base"

    def process(
        self,
        *,
        spec: dict[str, object],
        notebook_spec: dict[str, object],
        materials: list[dict[str, object]],
    ) -> BackendResult:
        raise NotImplementedError


def resolve_repo_path(spec: dict[str, object], raw_path: str) -> Path:
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    spec_dir = Path(str(spec.get("_spec_dir", "."))).resolve()
    return (spec_dir / candidate).resolve()


class ManifestOnlyBackend(WorkflowBackend):
    """Stable backend that only produces local manifests and notes."""

    name = "manifest_only"

    def process(
        self,
        *,
        spec: dict[str, object],
        notebook_spec: dict[str, object],
        materials: list[dict[str, object]],
    ) -> BackendResult:
        notes = [
            "Material collection completed locally.",
            "No external notebook client was invoked.",
            "Use the generated manifests and file paths for manual upload or a future backend run.",
        ]
        return BackendResult(
            backend=self.name,
            notebook_id=notebook_spec.get("notebook_id"),
            uploaded_sources=[],
            notes=notes,
        )


class NotebookLMBackend(WorkflowBackend):
    """NotebookLM-backed ingestion backend."""

    name = "notebooklm"

    def __init__(self) -> None:
        self.adapter = NotebookLMAdapter.autodetect(needs_file=True)

    def process(
        self,
        *,
        spec: dict[str, object],
        notebook_spec: dict[str, object],
        materials: list[dict[str, object]],
    ) -> BackendResult:
        notebook_id = notebook_spec.get("notebook_id")
        if not notebook_id:
            if not self.adapter.probe.supports_create:
                raise NotebookLMError(
                    "Selected NotebookLM client cannot create notebooks. "
                    "Provide `notebook_id` in the spec or use `manifest_only`."
                )
            notebook_id = self.adapter.create_notebook(str(notebook_spec["title"]))

        notes: list[str] = []
        prompt_path = resolve_repo_path(spec, str(notebook_spec.get("persona_prompt", spec["default_persona_prompt"])))
        if self.adapter.probe.supports_configure:
            self.adapter.configure_persona(str(notebook_id), load_prompt(prompt_path))
        else:
            notes.append(f"Persona configure skipped: {prompt_path}")

        uploaded_sources: list[str] = []
        for source in flatten_sources(materials):
            if source["kind"] == "file":
                self.adapter.add_file(str(notebook_id), Path(source["path"]))
                uploaded_sources.append(source["path"])
            elif source["kind"] == "url":
                self.adapter.add_url(str(notebook_id), source["url"])
                uploaded_sources.append(source["url"])

        if not uploaded_sources:
            notes.append("No uploadable sources were produced by the collection step.")

        return BackendResult(
            backend=self.name,
            notebook_id=str(notebook_id),
            uploaded_sources=uploaded_sources,
            notes=notes,
        )


def get_backend(name: str) -> WorkflowBackend:
    if name == ManifestOnlyBackend.name:
        return ManifestOnlyBackend()
    if name == NotebookLMBackend.name:
        return NotebookLMBackend()
    raise ValueError(f"Unsupported backend: {name}")


def flatten_sources(materials: list[dict[str, object]]) -> list[dict[str, str]]:
    flattened: list[dict[str, str]] = []
    for material in materials:
        if material.get("kind") == "file":
            flattened.append({"kind": "file", "path": str(material["path"])})
            continue
        if material.get("kind") == "url":
            flattened.append({"kind": "url", "url": str(material["url"])})
            continue
        for item in material.get("downloaded", []):
            flattened.append({"kind": "file", "path": str(item["path"])})
    return flattened
