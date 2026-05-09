# IPO NotebookLM Screen

> A repeatable diligence pipeline for A-share and Hong Kong IPOs.
> Collect prospectuses, peer financials, and policy documents; optionally hand them to a NotebookLM backend; produce a markdown participate-or-skip decision table.

**Inspired by:** [Min Li's X post on NotebookLM IPO screening](https://x.com/MinLiBuilds/status/2046002143937941988) — adapted into an agent-executable, backend-decoupled workflow.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Node.js 18+](https://img.shields.io/badge/node-18+-green.svg)](https://nodejs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
  - [1. Preflight check](#1-preflight-check)
  - [2. Write a workflow spec](#2-write-a-workflow-spec)
  - [3. Run the screen](#3-run-the-screen)
  - [4. Ask questions via NotebookLM](#4-ask-questions-via-notebooklm)
  - [5. Produce the decision table](#5-produce-the-decision-table)
- [Backend Policies](#backend-policies)
- [Project Structure](#project-structure)
- [Dependencies](#dependencies)
- [Auto-Clone Behavior](#auto-clone-behavior)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Overview

This skill turns a named IPO candidate into a repeatable diligence package and a final markdown decision table.

**Default assumptions:**

- You already have one issuer in mind.
- The output is a practical participation decision, not an academic summary.
- The freshest official materials matter most.

**Workflow:**

1. Fix the scope — issuer name, listing market, current stage, business lines, peer set.
2. Gather the minimum decision set — prospectus, issuance notices, peer reports, policy documents.
3. Build a clean materials folder with manifests.
4. Optionally hand materials to a NotebookLM backend.
5. Rewrite standard diligence questions issuer-specifically.
6. Ask in a deliberate order and produce a markdown decision table.

---

## Features

| Feature | Description |
|---------|-------------|
| **Market-aware** | Distinguishes A-share vs Hong Kong IPO question sets automatically. |
| **Multi-segment split** | If business lines require different peer sets, creates separate notebooks per segment. |
| **PDF-first ingestion** | Prefers official PDFs over URLs; falls back to URLs only when PDFs are unavailable. |
| **Backend decoupling** | Stable `manifest_only` path always works; `notebooklm` is optional and gated by policy. |
| **Auto-upgrade** | `auto` policy switches to `notebooklm` when material scale or complexity warrants it. |
| **Source scope control** | Uses `--source-ids` to limit each question to the smallest relevant source set. |
| **CLI instability fallback** | If NotebookLM client times out, switch to web UI for reading; the agent still summarizes. |
| **CNInfo integration** | `scripts/cninfo_fetch.py` fetches peer reports from 巨潮资讯网 with one command. |
| **Auto-clone dependency** | If `notebooklm-client` source build is missing, the skill auto-clones and builds it. |

---

## Installation

```bash
git clone https://github.com/YOUR_ORG/ipo-notebooklm-screen.git
cd ipo-notebooklm-screen
pip install -r requirements.txt
```

Requirements:

- Python 3.10+
- Node.js 18+
- `git` and `npm` (for auto-clone)

---

## Quick Start

```bash
# 1. Check environment
python3 scripts/preflight.py

# 2. Copy the example spec and edit it
cp assets/ipo-workflow-spec.example.json my-spec.json
# --- edit my-spec.json with your issuer, peers, and paths ---

# 3. Run the screen (default: manifest_only)
python3 scripts/run_ipo_screen.py --spec my-spec.json

# 4. Or force NotebookLM backend
python3 scripts/run_ipo_screen.py --spec my-spec.json --backend notebooklm --backend-policy required
```

---

## Usage

### 1. Preflight check

```bash
python3 scripts/preflight.py
```

Outputs a JSON report covering:

- `python3`, `node`, `notebooklm` CLI availability
- Local source build detection (auto-discovered or auto-cloned)
- Python dependency status (`httpx`)
- Selected file-capable client

### 2. Write a workflow spec

See `assets/ipo-workflow-spec.example.json` for the full schema. Minimal example:

```json
{
  "issuer": "Example Corp",
  "workspace": "./output/example-corp",
  "backend": "manifest_only",
  "backend_policy": "auto",
  "notebooks": [
    {
      "title": "Example Corp — Core Business",
      "sources": [
        { "kind": "file", "path": "./prospectus.pdf" },
        { "kind": "url", "url": "https://www.example.com/ir" }
      ]
    }
  ]
}
```

### 3. Run the screen

```bash
python3 scripts/run_ipo_screen.py --spec my-spec.json
```

The script:

1. Resolves backend plan (`manifest_only` vs `notebooklm`) based on policy and readiness.
2. Collects materials (CNInfo fetch, local files, URLs).
3. Hands materials to the chosen backend.
4. Writes `run-summary.json` to the workspace.

### 4. Ask questions via NotebookLM

If `notebooklm` backend was used:

```bash
# List notebooks
notebooklm list --transport http

# Show details
notebooklm detail <notebook-id> --transport http

# Add more sources
python3 scripts/notebooklm_adapter.py add-file <notebook-id> ./extra-report.pdf
python3 scripts/notebooklm_adapter.py add-url <notebook-id> "https://example.com/page"
```

Read `references/question-adaptation.md` for how to rewrite the standard 8 question families issuer-specifically.

### 5. Produce the decision table

The final output shape is defined in `assets/decision-table-template.md`. It must include:

- One-paragraph issuer summary
- Segment-by-segment peer view
- Positive signals list
- Red flags list
- Participation verdict: `Participate`, `Watch`, or `Skip`
- Confidence note explaining weak or missing evidence

---

## Backend Policies

| Policy | Behavior |
|--------|----------|
| `forbid` | Stay on `manifest_only` always. |
| `auto` | Default. Upgrade to `notebooklm` only if client is capable and material scale warrants it. |
| `required` | Must use `notebooklm`; fail early if client is unavailable. |

Auto-upgrade conditions (`auto`):

- Two or more notebooks
- Ten or more total sources
- Three or more peer `cninfo_reports` sources
- Explicit objective mentioning `NotebookLM`, `source-ids`, token saving, or multi-round analysis — but only when material set is already moderately large

---

## Project Structure

```
ipo-notebooklm-screen/
├── SKILL.md                          # Skill definition for Codex / Hermes
├── README.md                         # This file
├── README.zh.md                      # Chinese version
├── requirements.txt                  # Python dependencies
├── assets/
│   ├── decision-table-template.md    # Final output shape
│   ├── question-template.md          # Standard 8 question families
│   ├── ipo-workflow-spec.example.json # Example spec
│   └── ipo_analyst_prompt.txt        # Default persona prompt
├── references/
│   ├── source-playbook.md            # Source priority and market rules
│   └── question-adaptation.md        # How to rewrite questions
└── scripts/
    ├── preflight.py                  # Environment check
    ├── notebooklm_adapter.py         # Client adapter with auto-clone
    ├── notebooklm_create.mjs         # Helper for notebook creation
    ├── cninfo_fetch.py               # 巨潮 report fetcher
    ├── backends.py                   # Backend abstraction layer
    └── run_ipo_screen.py             # Orchestrator
```

---

## Dependencies

**Python:**

- `httpx` — CNInfo fetching and HTTP transport

**Node.js:**

- `notebooklm-client` — Auto-cloned from [icebear0828/notebooklm-client](https://github.com/icebear0828/notebooklm-client) if not present locally.

**System:**

- `git`, `npm`, `node`, `python3`

---

## Auto-Clone Behavior

If no local `notebooklm-client` build is found, the skill auto-clones it to `~/.codex/skills/notebooklm-client` and runs `npm install && npm run build`.

Override locations with environment variables if needed:

```bash
export NOTEBOOKLM_CLIENT_ROOT=/path/to/notebooklm-client   # optional override
export NOTEBOOKLM_CLIENT_ENTRY=/path/to/notebooklm-client/dist/cli.js  # optional override
export NOTEBOOKLM_CLIENT_INDEX=/path/to/notebooklm-client/dist/index.js  # optional override
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `No compatible NotebookLM client found` | Missing `notebooklm-client` and auto-clone failed | Ensure `git` and `npm` are installed; or manually clone the repo |
| `Selected NotebookLM client cannot create notebooks` | Local build missing helper or `create` unsupported | Check `scripts/notebooklm_create.mjs` exists; or provide `notebook_id` in spec |
| `NotebookLM command failed` | Network restriction in sandbox | Run outside sandbox, or switch to `manifest_only` |
| `httpx not found` | Python deps missing | `pip install -r requirements.txt` |

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

**中文文档** → [README.zh.md](./README.zh.md)
