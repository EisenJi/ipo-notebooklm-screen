---
name: ipo-notebooklm-screen
description: Collect and analyze IPO diligence materials for a specific A-share issuer. Use when the agent (Codex, Hermes, or other) needs to gather prospectuses, issuance/placement notices, peer financials, policy documents, management interviews, and historical financing clues; adapt a standard set of IPO diligence questions to the issuer; optionally hand materials to a NotebookLM backend; and produce a markdown participate-or-skip subscription decision table. Currently A-share only; Hong Kong IPO support is not yet implemented.
---

# IPO NotebookLM Screen

Use this skill to turn a named IPO candidate into a repeatable diligence package and a final markdown decision table.

**Inspired by:** [Min Li's X post on NotebookLM IPO screening](https://x.com/MinLiBuilds/status/2046002143937941988) — adapted into an agent-executable, backend-decoupled workflow.

Default assumption:

- The user already has one issuer in mind.
- The output is a practical participation decision, not an academic summary.
- The freshest official materials matter most.

## Workflow

### 1. Fix the scope first

Determine:

- Issuer name
- Listing market: A-share only for now. Infer from ticker (6xxxxx / 0xxxxx / 3xxxxx), exchange, or filing venue
- Current stage: filed, hearing passed, bookbuilding, pricing, or listed
- Main business lines
- Peer set, split by business line if the issuer is multi-segment

If the issuer spans two distinct businesses, split the analysis into separate peer clusters. Do not mix zirconium peers and specialty-nylon peers in one comparison block.

Hard rule:

- If business line A and business line B require different peer sets, create separate notebooks for them.
- Do not ask cross-segment comparison questions inside one notebook.

### 2. Gather the minimum decision set

Collect the newest official or primary-source materials you can get.

Read [references/source-playbook.md](./references/source-playbook.md) for source priority and market-specific rules.

For the issuer, gather:

- Full prospectus / hearing-posted document / 招股书 / 招股意向书
- Issuance arrangement, pricing, allocation, risk, strategic placement, or lockup notices
- Latest management discussion or IR transcript if available
- Historical financing and shareholder changes disclosed in filings
- Relevant policy or regulatory documents affecting the issuer's ceiling

For each peer, gather:

- Latest quarterly report if already out for the current cycle
- Otherwise the latest annual or interim report
- Any useful IR or management Q&A note that clarifies margin, capex, customers, or strategy

Priority rule:

- Prefer `2026 Q1` over `2025 annual` when the current quarter is already disclosed.
- Prefer exchange, company IR, or regulator sites over media summaries.
- Use media only as a locator or fallback.

### 3. Build a clean materials folder

Create a folder named after the issuer under a working directory, then group files by role:

```text
issuer-name/
  00_issuer_core/
  10_peer_segment_a/
  20_peer_segment_b/
  30_policy/
  40_interviews/
  50_notes/
```

Keep a short manifest of each file's purpose and source URL.

When peer reports come from CNInfo, prefer using the local fetcher:

```bash
python3 scripts/cninfo_fetch.py \
  --stock "000333,9900005965,szse,美的集团,10_peer_segment_a,latest" \
  --output-root /tmp/issuer-name \
  --reporting-year 2026
```

Auto-resolve `org_id` (no manual lookup needed):

```bash
python3 scripts/cninfo_fetch.py \
  --stock "铜峰电子,铜峰电子,10_peer_segment_a,latest" \
  --output-root /tmp/issuer-name \
  --reporting-year 2026
```

Practical rule for this script:

- **4-part mode** (recommended): `code,name,role,scope` — `org_id` and `market` are auto-resolved via `orgid_resolver.py`.
- **6-part mode** (legacy): `code,org_id,market,name,role,scope` — use only when auto-resolution fails.
- It writes one `manifest.json` per peer folder.

**Peer discovery** (find comparables without manual research):

```bash
python3 scripts/peer_discovery.py \
  --prospectus-text /path/to/prospectus.txt \
  --llm-candidates "东材科技" "铜峰电子" "大东南" \
  --user-candidates "法拉电子" \
  --max-results 10 \
  --output /tmp/peers.json
```

Sources (in priority order):
1. Prospectus explicit comparable companies (regex extraction)
2. **Agent knowledge-base candidate generation** — the agent itself uses its own reasoning to suggest peers based on the issuer's business description, then passes them via `--llm-candidates`
3. User-provided overrides

The module resolves candidate names to tradeable A-share codes + `org_id`s via `orgid_resolver.py`.

**How the agent generates Layer-2 candidates:**

The agent reads the issuer's business description from the prospectus (or asks NotebookLM to summarize it), then uses its own knowledge to suggest 5-10 A-share peers. Example reasoning chain:

- Keywords from prospectus: "BOPP电工膜", "薄膜电容器", "电容膜"
- Agent knowledge: 东材科技 (601208) 是电子材料龙头，有电容膜业务；铜峰电子 (600237) 是老牌薄膜电容器材料企业；大东南 (002263) 有 BOPP 薄膜产能
- Pass these names to `--llm-candidates` for resolution and validation

No external LLM API call is needed — the agent itself is the LLM.

If a source is HTML-only, either:

- Feed the URL directly to NotebookLM, or
- Convert it to `md` or `txt` before local file upload

Preference order for NotebookLM ingestion:

1. Official PDF
2. Official exchange or IR URL
3. Media URL only when no better primary source is available

### 4. Hand materials to a backend

Do not hardwire the workflow to NotebookLM.

Use a backend boundary:

- `manifest_only`: default and most stable
- `notebooklm`: optional and more fragile

Rule:

- First finish collection and manifest generation.
- Then decide whether to pass the materials to `notebooklm`.
- If the NotebookLM client looks unstable, stop at `manifest_only`.

Backend policy:

- `required`: use NotebookLM if the environment permits it
- `auto`: let the runner decide based on scale and objective
- `forbid`: stay local and do not use NotebookLM

Auto-upgrade conditions in the current runner:

- two or more notebooks
- ten or more total sources
- three or more peer `cninfo_reports` sources
- explicit objective mentioning `NotebookLM`, `source-ids`, token saving, or multi-round analysis, but only when the material set is already moderately large

Auto-upgrade safety gate:

- do not switch to `notebooklm` unless a file-capable client exists
- if every notebook already has `notebook_id`, reuse them
- otherwise require a file-capable client that also supports create
- if these conditions are not met, stay on `manifest_only` and record why

Known practical rule from this environment:

- Global `notebooklm-client 0.2.0` exposes `--url`, `--text`, `--topic`
- A local source build (auto-discovered or auto-cloned) exposes `source add --file`
- The local source build does not expose `create` in CLI help, but this skill provides a helper-backed create path via the local library API
- `configure` is still not confirmed in this environment
- The skill auto-clones `https://github.com/icebear0828/notebooklm-client.git` to `~/.codex/skills/notebooklm-client` if no local build is found

Sandbox caveat:

- these checks are capability-oriented
- later runtime failure may still come from sandboxed network restrictions, not from missing NotebookLM features

Before using the `notebooklm` backend, run:

```bash
python3 scripts/preflight.py
python3 scripts/notebooklm_adapter.py inspect --needs-file
```

Typical commands:

```bash
notebooklm list --transport http
```

For local file upload with the source build:

```bash
node "$(python3 -c 'from notebooklm_adapter import _find_client_repo; r=_find_client_repo(); print(r/"dist/cli.js" if r else "")')" analyze --transport http --file /abs/path/to/file.pdf --question "What is this file?"
```

For adding more files to an existing notebook:

```bash
node "$(python3 -c 'from notebooklm_adapter import _find_client_repo; r=_find_client_repo(); print(r/"dist/cli.js" if r else "")')" source add <notebook-id> --transport http --file /abs/path/to/file.pdf
node "$(python3 -c 'from notebooklm_adapter import _find_client_repo; r=_find_client_repo(); print(r/"dist/cli.js" if r else "")')" source add <notebook-id> --transport http --url "https://example.com/page"
```

If the current client does not support notebook creation:

- Reuse an existing notebook id, or
- Stop after material collection and manifest generation

This is not a failure. The stable path is to keep the workflow successful with local manifests only.

Hard rule:

- If policy is `required`, do not skip NotebookLM based on subjective judgment.
- If policy is `auto` and the auto-upgrade conditions fire, do not silently stay on `manifest_only`.
- In both cases, verify the environment first; only then may you fall back if the backend is truly unavailable.
- `required` should fail early during planning if NotebookLM is not safely executable.

Notebook construction rules:

- Use one notebook per business line when peer sets differ materially.
- Put issuer core materials in every notebook that needs them.
- Add policy documents only when they affect valuation, approval, demand, pricing, reimbursement, export control, environmental burden, or capacity expansion.
- Prefer feeding issuer core documents as local PDFs instead of HTML pages.
- Prefer feeding peer reports as PDFs when available; use URLs only when PDFs are missing or hard to access.

### 5. Rewrite the standard questions for the issuer

Do not ask the raw eight questions unchanged. Rewrite each one with:

- Issuer name
- Market structure
- Correct peer names
- Correct business lines
- Current reporting period

Read [references/question-adaptation.md](./references/question-adaptation.md) before asking NotebookLM.

Critical rule:

- Hong Kong IPOs are not yet supported (no automated fetcher for hkexnews.hk).
- For A-share IPOs, replace that with `strategic placement investors`, `offline inquiry / bookbuilding structure`, and `lockup arrangements`.

Question design rules:

- Ask one compact question at a time.
- Ask for directional conclusions first, then ask for detailed support only if needed.
- Avoid asking for a full report in one prompt.
- Avoid mixing issuer fundamentals, peer comparison, issuance structure, and forensic accounting in the same question.

### 6. Ask NotebookLM in a deliberate order

Use this sequence:

1. Business and revenue structure
2. Peer comparison by segment
3. Issuance structure and dilution
4. Risk factor split: common vs issuer-specific
5. Financing history and valuation jump
6. Earnings quality and cash conversion
7. Related-party exposure and customer cleanliness
8. Final synthesis: reasons to participate vs reasons to skip

Ask short, high-signal questions. Avoid combining unrelated asks into one prompt.

Operational rule:

- Before asking questions in a large notebook, run `detail` and record the source IDs.
- Use `--source-ids` to limit each question to the smallest relevant source set, usually 2-4 sources.

### 7. Produce the final markdown decision table

Use [assets/decision-table-template.md](./assets/decision-table-template.md) as the final output shape.

The end product must include:

- A one-paragraph issuer summary
- A segment-by-segment peer view
- A clean list of positive signals
- A clean list of red flags
- A participation verdict: `Participate`, `Watch`, or `Skip`
- A confidence note explaining what evidence is weak or missing

## Question set

Use the following as the canonical question families, but rewrite them issuer-specifically before sending them to NotebookLM.

1. Core products and revenue structure
2. Peer comparison on margin, growth, and R&D intensity
3. Cornerstone or strategic placement structure
4. Proceeds allocation and post-IPO dilution
5. Common industry risks vs issuer-specific risks
6. Historical financing valuation jump
7. Earnings quality and operating cash conversion
8. Related-party transactions and customer cleanliness

Use [assets/question-template.md](./assets/question-template.md) to draft the issuer-specific prompts.

## Output standards

Prefer a decision memo, not a chronology.

Every conclusion in the final markdown should be traceable to one of:

- Prospectus / offer document
- Official exchange or regulator filing
- Peer financial report
- Official policy document
- Explicitly labeled inference from the above

When evidence is missing:

- Say it is missing
- State the impact on confidence
- Do not silently fill the gap with narrative

## Fallbacks

### NotebookLM client instability

If `notebooklm-client` can create notebooks and add sources but does not reliably return long answers:

- Keep using the client for notebook creation and source ingestion.
- Use shorter questions.
- Restrict source scope with `--source-ids`.
- If the client still times out, switch to the NotebookLM web UI for reading the answer.
- Continue the workflow by summarizing those answers into the markdown decision table.

Treat this as a normal fallback path, not as a failure of the overall skill.

### Scripted runner

If the user wants a semi-automated run, use:

```bash
python3 scripts/run_ipo_screen.py --spec assets/ipo-workflow-spec.example.json
```

This defaults to `manifest_only`.

If you explicitly want NotebookLM:

```bash
python3 scripts/run_ipo_screen.py --spec assets/ipo-workflow-spec.example.json --backend notebooklm
```

If you want to force NotebookLM by policy:

```bash
python3 scripts/run_ipo_screen.py \
  --spec assets/ipo-workflow-spec.example.json \
  --backend-policy required
```

Auto-clone behavior:

- If no local notebooklm-client build is found, the skill auto-clones it to `~/.codex/skills/notebooklm-client` and runs `npm install && npm run build`
- Override locations with `NOTEBOOKLM_CLIENT_ROOT` or `NOTEBOOKLM_CLIENT_ENTRY` if needed

Current constraint:

- `notebooklm` is safe only when the chosen client supports file upload
- If notebook creation is unsupported, the spec must provide an existing `notebook_id`

### Historical financing valuation gaps

Do not force a numeric conclusion if the evidence is weak.

Try, in order:

- Prospectus equity history
- Capital increase / shareholder change disclosures
- Management interview references
- Reliable secondary databases if available

If the prior-round valuation jump cannot be reconstructed cleanly:

- Mark it as `insufficient evidence`
- Explain the missing input
- Reduce confidence in the final decision accordingly
