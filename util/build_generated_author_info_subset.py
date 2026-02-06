#!/usr/bin/env python3
"""
Build subset generated-author-info.csv for Yale+Zhejiang and inject Yilun rows.

This script preserves all existing Yale/Zhejiang rows from generated-author-info.csv
and adds/refreshes Yilun Zhao 0007 rows from yilun-papers.json.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple


TARGET_INSTITUTIONS = {"Yale University", "Zhejiang University"}
YILUN_NAME = "Yilun Zhao 0007"
YILUN_DEPT = "Yale University"


def read_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as infile:
        reader = csv.DictReader(infile)
        if not reader.fieldnames:
            raise RuntimeError(f"{path} has no header")
        rows = [{k: (v or "").strip() for k, v in row.items()} for row in reader]
        return list(reader.fieldnames), rows


def write_csv(path: Path, fieldnames: List[str], rows: List[Dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_yilun_rows(yilun_payload_path: Path) -> List[Dict[str, str]]:
    with yilun_payload_path.open("r", encoding="utf-8") as infile:
        payload = json.load(infile)

    totals: Dict[Tuple[str, int], Dict[str, float]] = defaultdict(lambda: {"count": 0.0, "adjusted": 0.0})
    for rec in payload.get("records", []):
        if not rec.get("included_by_csrankings"):
            continue
        area = rec.get("area", "")
        year = int(rec.get("year"))
        totals[(area, year)]["count"] += 1.0
        totals[(area, year)]["adjusted"] += 1.0 / float(rec.get("numauthors", 1))

    rows: List[Dict[str, str]] = []
    for (area, year), values in sorted(totals.items()):
        rows.append(
            {
                "name": YILUN_NAME,
                "dept": YILUN_DEPT,
                "area": area,
                "count": f"{values['count']:.1f}",
                "adjustedcount": f"{values['adjusted']:.5f}",
                "year": str(year),
            }
        )
    return rows


def main() -> None:
    fieldnames, rows = read_csv(Path("generated-author-info.csv"))
    filtered = [r for r in rows if r.get("dept") in TARGET_INSTITUTIONS and r.get("name") != YILUN_NAME]
    yilun_rows = build_yilun_rows(Path("yilun-papers.json"))
    merged = filtered + yilun_rows
    merged.sort(key=lambda r: (r["name"].lower(), r["area"], int(r["year"])))
    write_csv(Path("generated-author-info.csv"), fieldnames, merged)
    print(
        f"Wrote generated-author-info.csv with {len(merged)} rows "
        f"({len(yilun_rows)} rows for {YILUN_NAME})."
    )


if __name__ == "__main__":
    main()
