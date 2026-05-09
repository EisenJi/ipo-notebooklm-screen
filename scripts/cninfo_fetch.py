#!/usr/bin/env python3
"""Download A-share or Hong Kong periodic reports from CNInfo and write a manifest."""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import httpx


QUERY_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
DOWNLOAD_ROOT = "https://static.cninfo.com.cn/"


def _default_headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:110.0) "
            "Gecko/20100101 Firefox/110.0"
        ),
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Origin": "https://www.cninfo.com.cn",
        "Referer": (
            "https://www.cninfo.com.cn/new/commonUrl/pageOfSearch"
            "?url=disclosure/list/search&lastPage=index"
        ),
    }


@dataclass
class ReportRequest:
    code: str
    org_id: str
    market: str
    label: str
    role: str
    scope: str


class CninfoFetcher:
    def __init__(self) -> None:
        self.client = httpx.Client(headers=_default_headers(), timeout=httpx.Timeout(60.0))

    def build_payload(self, request: ReportRequest, *, category: str, searchkey: str, se_date: str) -> dict[str, object]:
        # CNInfo uses 'sse' for Shanghai, 'szse' for Shenzhen, 'hke' for Hong Kong
        column = request.market
        if column == "shj":
            column = "sse"
        return {
            "pageNum": 0,
            "pageSize": 30,
            "column": column,
            "tabName": "fulltext",
            "plate": "",
            "stock": f"{request.code},{request.org_id}",
            "searchkey": "" if column == "hke" else searchkey,
            "secid": "",
            "category": "" if column == "hke" else category,
            "trade": "",
            "seDate": se_date,
            "sortName": "",
            "sortType": "",
            "isHLtitle": False,
        }

    def query(self, payload: dict[str, object]) -> list[dict[str, object]]:
        announcements: list[dict[str, object]] = []
        page_num = 0
        while True:
            payload["pageNum"] = page_num
            response = self.client.post(QUERY_URL, data=payload)
            response.raise_for_status()
            body = response.json()
            announcements.extend(body.get("announcements") or [])
            if not body.get("hasMore"):
                break
            page_num += 1
        return announcements

    def download(self, announcement: dict[str, object], output_dir: Path) -> Path | None:
        if announcement.get("adjunctType") != "PDF":
            return None
        title = sanitize_filename(str(announcement["announcementTitle"]))
        sec_code = str(announcement["secCode"])
        sec_name = sanitize_filename(str(announcement["secName"]))
        announcement_id = str(announcement["announcementId"])
        target = output_dir / f"{sec_code}_{sec_name}_{title}_{announcement_id}.pdf"
        if target.exists():
            return target
        url = DOWNLOAD_ROOT + str(announcement["adjunctUrl"])
        response = self.client.get(url)
        response.raise_for_status()
        target.write_bytes(response.content)
        time.sleep(random.uniform(0.4, 1.2))
        return target

    def fetch_latest_reports(self, request: ReportRequest, output_root: Path, reporting_year: int) -> dict[str, object]:
        output_dir = output_root / request.role / request.label
        output_dir.mkdir(parents=True, exist_ok=True)

        configs = report_configs(request.market, reporting_year, request.scope)
        downloaded: list[dict[str, object]] = []

        for config in configs:
            payload = self.build_payload(
                request,
                category=config["category"],
                searchkey=config["searchkey"],
                se_date=config["se_date"],
            )
            announcements = self.query(payload)
            picked = pick_announcement(announcements, config["matcher"], request.market)
            if not picked:
                continue
            path = self.download(picked, output_dir)
            if not path:
                continue
            downloaded.append(
                {
                    "label": request.label,
                    "role": request.role,
                    "scope": request.scope,
                    "report_kind": config["kind"],
                    "title": picked["announcementTitle"],
                    "path": str(path.resolve()),
                    "source_url": DOWNLOAD_ROOT + str(picked["adjunctUrl"]),
                    "announcement_id": picked["announcementId"],
                }
            )

        manifest = {
            "request": {
                "code": request.code,
                "org_id": request.org_id,
                "market": request.market,
                "label": request.label,
                "role": request.role,
                "scope": request.scope,
                "reporting_year": reporting_year,
            },
            "downloaded": downloaded,
        }
        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest["manifest_path"] = str(manifest_path.resolve())
        return manifest


def report_configs(market: str, year: int, scope: str) -> list[dict[str, object]]:
    latest_periods = [
        {
            "kind": "q1",
            "category": "category_yjdbg_szsh",
            "searchkey": "一季度报告",
            "se_date": f"{year}-04-01~{year}-05-31",
            "matcher": "q1",
        },
        {
            "kind": "semi",
            "category": "category_bndbg_szsh",
            "searchkey": "半年度报告",
            "se_date": f"{year}-08-01~{year}-09-30",
            "matcher": "semi",
        },
        {
            "kind": "q3",
            "category": "category_sjdbg_szsh",
            "searchkey": "三季度报告",
            "se_date": f"{year}-10-01~{year}-11-30",
            "matcher": "q3",
        },
    ]
    annual = [
        {
            "kind": "annual",
            "category": "category_ndbg_szsh",
            "searchkey": f"{year - 1}年年度报告",
            "se_date": annual_search_window(market, year - 1),
            "matcher": f"annual:{year - 1}",
        }
    ]
    if scope == "latest":
        return latest_periods + annual
    if scope == "annual_only":
        return annual
    return latest_periods


def annual_search_window(market: str, report_year: int) -> str:
    if market == "hke":
        return f"{report_year}-01-01~{report_year + 1}-06-30"
    return f"{report_year + 1}-03-01~{report_year + 1}-06-30"


def pick_announcement(
    announcements: Iterable[dict[str, object]],
    matcher: str,
    market: str,
) -> dict[str, object] | None:
    for announcement in announcements:
        title = str(announcement["announcementTitle"])
        if is_main_report(title, matcher, market):
            return announcement
    return None


def is_main_report(title: str, matcher: str, market: str) -> bool:
    lowered = title.lower()
    if "摘要" in title or "summary" in lowered or "英文" in title:
        return False
    if "更正" in title or "修订" in title:
        return False

    if matcher == "q1":
        return "一季度" in title or "第一季度" in title
    if matcher == "semi":
        return "半年度报告" in title or "中期报告" in title
    if matcher == "q3":
        return "三季度" in title or "第三季度" in title

    if matcher.startswith("annual:"):
        report_year = matcher.split(":", 1)[1]
        if market == "hke":
            return (
                report_year in title
                and (
                    "年度报告" in title
                    or "年度业绩公布" in title
                    or "年度业绩公告" in title
                    or "年报" in title
                )
            )
        return f"{report_year}年年度报告" in title or f"{report_year}年年报" in title
    return False


def sanitize_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in value)


def parse_request(raw: str) -> ReportRequest:
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) == 6:
        return ReportRequest(
            code=parts[0],
            org_id=parts[1],
            market=parts[2],
            label=parts[3],
            role=parts[4],
            scope=parts[5],
        )
    # Auto-resolve org_id if only code+label+role+scope provided (4 parts)
    if len(parts) == 4:
        from orgid_resolver import resolve
        resolved = resolve(parts[0])
        if not resolved or not resolved.get("org_id"):
            raise ValueError(
                f"Could not resolve org_id for {parts[0]}. "
                "Provide 6 parts (code,org_id,market,label,role,scope) "
                "or ensure the stock name/code is searchable on CNInfo."
            )
        return ReportRequest(
            code=resolved["code"],
            org_id=resolved["org_id"],
            market=resolved["market"],
            label=parts[1],
            role=parts[2],
            scope=parts[3],
        )
    raise ValueError(
        "--stock must be `code,org_id,market,label,role,scope` (6 parts) "
        "or `code,label,role,scope` (4 parts, auto-resolve org_id)"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch peer reports from CNInfo")
    parser.add_argument("--stock", action="append", required=True, help="code,org_id,market,label,role,scope")
    parser.add_argument("--output-root", required=True, help="Directory for downloaded materials")
    parser.add_argument("--reporting-year", type=int, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    requests = [parse_request(raw) for raw in args.stock]
    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    fetcher = CninfoFetcher()
    manifests = []
    try:
        for request in requests:
            manifests.append(fetcher.fetch_latest_reports(request, output_root, args.reporting_year))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps({"materials_root": str(output_root), "manifests": manifests}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
