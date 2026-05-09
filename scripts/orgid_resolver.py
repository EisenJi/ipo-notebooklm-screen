#!/usr/bin/env python3
"""Resolve stock code to CNInfo org_id via the public search API."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

SEARCH_URL = "https://www.cninfo.com.cn/new/information/topSearch/query"


def _default_headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:110.0) "
            "Gecko/20100101 Firefox/110.0"
        ),
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://www.cninfo.com.cn",
        "Referer": "https://www.cninfo.com.cn/new/commonUrl/pageOfSearch",
    }


def resolve(code_or_name: str) -> dict[str, str] | None:
    """Query CNInfo search API and return the first A-share match.

    Returns a dict with keys: code, org_id, market, zwjc (short name).
    """
    client = httpx.Client(headers=_default_headers(), timeout=httpx.Timeout(30.0))
    try:
        resp = client.post(SEARCH_URL, data={"keyWord": code_or_name})
        resp.raise_for_status()
        body = resp.json()
        if not body:
            return None
        # body is a list of candidates
        for item in body:
            if item.get("category") == "A股" and item.get("delisted") == "false":
                return {
                    "code": str(item.get("code", "")),
                    "org_id": str(item.get("orgId", "")),
                    "market": str(item.get("type", "")),
                    "zwjc": str(item.get("zwjc", "")),
                }
        # Fallback: return first item regardless
        if body:
            first = body[0]
            return {
                "code": str(first.get("code", "")),
                "org_id": str(first.get("orgId", "")),
                "market": str(first.get("type", "")),
                "zwjc": str(first.get("zwjc", "")),
            }
        return None
    except Exception:
        return None
    finally:
        client.close()


def resolve_batch(codes: list[str]) -> dict[str, dict[str, str] | None]:
    """Resolve multiple codes/names, returning a mapping."""
    results: dict[str, dict[str, str] | None] = {}
    for c in codes:
        results[c] = resolve(c)
    return results


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python3 orgid_resolver.py <stock_code_or_name>", file=sys.stderr)
        return 1
    query = sys.argv[1]
    result = resolve(query)
    if result is None:
        print(json.dumps({"error": f"No match for {query}"}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
