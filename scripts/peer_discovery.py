#!/usr/bin/env python3
"""Heuristic peer discovery for IPO issuers.

Design note: CNInfo search API only returns results for exact stock names/codes,
not fuzzy keyword matches. Therefore this module uses:

1. Prospectus explicit comparable extraction (regex)
2. LLM / knowledge-base candidate generation (via external prompt)
3. Exact-name org_id resolution

The caller is expected to provide candidate names from whichever source
(prospectus, LLM, industry knowledge), and this module resolves them to
tradeable A-share codes + org_ids.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from orgid_resolver import resolve


@dataclass
class PeerCandidate:
    code: str
    org_id: str
    market: str
    name: str
    source: str  # prospectus | llm_suggestion | user_provided | industry_kb
    confidence: str  # high | medium | low
    rationale: str


def extract_prospectus_comparables(text: str) -> list[tuple[str, str]]:
    """Extract explicit comparable company mentions from prospectus text.

    Returns list of (name, context_snippet).
    """
    found: list[tuple[str, str]] = []
    seen: set[str] = set()

    # Pattern 1: "同行业可比公司为 X、Y、Z"
    pat1 = re.compile(
        r"同行业可比公司[为是][:：]\s*([^\n。；]+)[。；\n]",
        re.MULTILINE,
    )
    for m in pat1.finditer(text):
        segment = m.group(1)
        for name in _split_names(segment):
            if name not in seen:
                seen.add(name)
                found.append((name, segment[:80]))

    # Pattern 2: "选取 X、Y 作为可比公司" or "发行人选取 X、Y 及 Z 作为同行业可比公司"
    pat2 = re.compile(
        r"选取[:：]?\s*(.{2,60})\s*作为(?:同行业)?可比公司",
        re.DOTALL,
    )
    for m in pat2.finditer(text):
        segment = m.group(1)
        for name in _split_names(segment):
            if name not in seen:
                seen.add(name)
                found.append((name, segment[:80]))

    # Pattern 3: "与 X 相比" near "同行业" or "可比"
    pat3 = re.compile(
        r"与([^\n。；]{2,20})[:：]\s*同行业",
        re.MULTILINE,
    )
    for m in pat3.finditer(text):
        name = m.group(1).strip()
        if name not in seen:
            seen.add(name)
            found.append((name, m.group(0)[:80]))

    # Pattern 4: Table headers like "公司名称" followed by known peers
    # This is weak; we skip unless explicitly matched above.

    return found


def _split_names(segment: str) -> Iterable[str]:
    """Split a Chinese enumeration into individual company names."""
    # Remove common noise words
    segment = re.sub(r"等[^\w]*公司", "", segment)
    segment = re.sub(r"公司", "", segment)
    # Split on Chinese/English delimiters
    parts = re.split(r"[,，、;；/\\s]+", segment)
    for p in parts:
        p = p.strip()
        if len(p) >= 2 and len(p) <= 20:
            yield p


def resolve_candidates(
    names: list[str],
    source_tag: str,
    confidence: str,
    rationale_template: str,
) -> list[PeerCandidate]:
    """Resolve a list of candidate names to PeerCandidate objects."""
    results: list[PeerCandidate] = []
    seen_codes: set[str] = set()

    for name in names:
        resolved = resolve(name)
        if not resolved or not resolved.get("code"):
            continue
        code = resolved["code"]
        if code in seen_codes:
            continue
        seen_codes.add(code)
        results.append(PeerCandidate(
            code=code,
            org_id=resolved["org_id"],
            market=resolved["market"],
            name=resolved["zwjc"],
            source=source_tag,
            confidence=confidence,
            rationale=rationale_template.format(name=name),
        ))
    return results


def discover_peers(
    prospectus_text: str | None = None,
    llm_candidates: list[str] | None = None,
    user_candidates: list[str] | None = None,
    max_results: int = 10,
) -> list[PeerCandidate]:
    """Run discovery heuristics and return deduplicated, ranked peers."""

    all_candidates: list[PeerCandidate] = []

    # Source 1: Prospectus explicit comparables
    if prospectus_text:
        prospectus_names = [n for n, _ in extract_prospectus_comparables(prospectus_text)]
        all_candidates.extend(resolve_candidates(
            prospectus_names,
            source_tag="prospectus",
            confidence="high",
            rationale_template="招股书中明确提到的同行业可比公司: {name}",
        ))

    # Source 2: LLM / knowledge-base suggestions
    if llm_candidates:
        all_candidates.extend(resolve_candidates(
            llm_candidates,
            source_tag="llm_suggestion",
            confidence="medium",
            rationale_template="LLM/知识库推荐的同行候选: {name}",
        ))

    # Source 3: User-provided overrides
    if user_candidates:
        all_candidates.extend(resolve_candidates(
            user_candidates,
            source_tag="user_provided",
            confidence="high",
            rationale_template="用户指定的同行公司: {name}",
        ))

    # Deduplicate by code
    seen: dict[str, PeerCandidate] = {}
    for c in all_candidates:
        if c.code in seen:
            existing = seen[c.code]
            # Keep higher confidence
            order = {"high": 3, "medium": 2, "low": 1}
            if order.get(c.confidence, 0) > order.get(existing.confidence, 0):
                seen[c.code] = c
        else:
            seen[c.code] = c

    unique = list(seen.values())

    # Sort by confidence
    order = {"high": 3, "medium": 2, "low": 1}
    unique.sort(key=lambda x: order.get(x.confidence, 0), reverse=True)

    return unique[:max_results]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Heuristic peer discovery for IPO issuers")
    parser.add_argument("--prospectus-text", help="Path to prospectus plain-text file")
    parser.add_argument("--llm-candidates", nargs="*", default=[], help="LLM-suggested peer names")
    parser.add_argument("--user-candidates", nargs="*", default=[], help="User-provided peer names")
    parser.add_argument("--max-results", type=int, default=10)
    parser.add_argument("--output", help="Output JSON file path")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    prospectus_text = None
    if args.prospectus_text:
        prospectus_text = Path(args.prospectus_text).read_text(encoding="utf-8")

    peers = discover_peers(
        prospectus_text=prospectus_text,
        llm_candidates=args.llm_candidates or None,
        user_candidates=args.user_candidates or None,
        max_results=args.max_results,
    )

    result = {
        "peers": [
            {
                "code": p.code,
                "org_id": p.org_id,
                "market": p.market,
                "name": p.name,
                "source": p.source,
                "confidence": p.confidence,
                "rationale": p.rationale,
            }
            for p in peers
        ],
    }

    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
