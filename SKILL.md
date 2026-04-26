---
name: ipo-notebooklm-screen
description: Collect and analyze IPO diligence materials for a specific issuer, especially A-share and Hong Kong IPOs. Use when Codex needs to gather prospectuses, issuance/placement notices, peer financials, policy documents, management interviews, and historical financing clues; adapt a standard set of IPO diligence questions to the issuer; feed the materials into NotebookLM through notebooklm-client; and produce a markdown participate-or-skip subscription decision table.
---

# IPO NotebookLM Screen

Use this skill to turn a named IPO candidate into a repeatable diligence package and a final markdown decision table.

Default assumption:

- The user already has one issuer in mind.
- The output is a practical participation decision, not an academic summary.
- The freshest official materials matter most.

## Workflow

### 1. Fix the scope first

Determine:

- Issuer name
- Listing market: A-share or Hong Kong by default; infer from ticker, exchange, filing venue, or wording
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

If a source is HTML-only, either:

- Feed the URL directly to NotebookLM, or
- Convert it to `md` or `txt` before local file upload

Preference order for NotebookLM ingestion:

1. Official PDF
2. Official exchange or IR URL
3. Media URL only when no better primary source is available

### 4. Feed materials into NotebookLM

Use the installed `notebooklm-client` when it exposes the needed commands. If the global CLI lacks `--file`, use the local source build that supports file upload.

Known practical rule from this environment:

- Global `notebooklm-client 0.2.0` exposes `--url`, `--text`, `--topic`
- The local source build at `/home/alice/codes/notebooklm-client` exposes `--file` and `source add --file`

Typical commands:

```bash
notebooklm list --transport http
```

For local file upload with the source build:

```bash
cd /home/alice/codes/notebooklm-client
node dist/cli.js analyze --transport http --file /abs/path/to/file.pdf --question "What is this file?"
```

For adding more files to an existing notebook:

```bash
cd /home/alice/codes/notebooklm-client
node dist/cli.js source add <notebook-id> --transport http --file /abs/path/to/file.pdf
node dist/cli.js source add <notebook-id> --transport http --url "https://example.com/page"
```

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

- For Hong Kong IPOs, ask about `cornerstone investors`.
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
