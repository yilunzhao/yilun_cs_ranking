#!/usr/bin/env python3
"""
Verify Zhejiang+Yale subset integrity and Yilun data consistency.
"""

from __future__ import annotations

import argparse
import csv
import json
import string
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


TARGET_INSTITUTIONS = {"Zhejiang University", "Yale University"}
YILUN_NAME = "Yilun Zhao 0007"
DISPLAY_START_YEAR = 2022
DISPLAY_END_YEAR = 2026


def read_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as infile:
        reader = csv.DictReader(infile)
        if not reader.fieldnames:
            raise RuntimeError(f"{path} has no CSV header.")
        rows = [{k: (v or "").strip() for k, v in row.items()} for row in reader]
        return list(reader.fieldnames), rows


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    raise SystemExit(1)


def check_affiliations(rows: Iterable[Dict[str, str]], column: str, source: str) -> None:
    bad = sorted({row.get(column, "") for row in rows if row.get(column, "") not in TARGET_INSTITUTIONS})
    if bad:
        fail(f"{source} has non-target affiliations: {bad[:5]}")


def tuple_key(row: Dict[str, str], fields: Sequence[str]) -> Tuple[str, ...]:
    return tuple(row.get(field, "") for field in fields)


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify Zhejiang+Yale subset data.")
    parser.add_argument("--baseline-csrankings", help="Optional baseline csrankings.csv for parity checks.")
    parser.add_argument(
        "--baseline-author-info",
        help="Optional baseline generated-author-info.csv for parity checks (excluding Yilun).",
    )
    args = parser.parse_args()

    _, cs_rows = read_csv(Path("csrankings.csv"))
    check_affiliations(cs_rows, "affiliation", "csrankings.csv")
    if not any(r.get("name") == YILUN_NAME and r.get("affiliation") == "Yale University" for r in cs_rows):
        fail(f"{YILUN_NAME} missing from csrankings.csv")

    _, inst_rows = read_csv(Path("institutions.csv"))
    inst_names = {r.get("institution", "") for r in inst_rows}
    if inst_names != TARGET_INSTITUTIONS:
        fail(f"institutions.csv must contain exactly {sorted(TARGET_INSTITUTIONS)}, found {sorted(inst_names)}")

    _, author_rows = read_csv(Path("generated-author-info.csv"))
    check_affiliations(author_rows, "dept", "generated-author-info.csv")
    yilun_rows = [r for r in author_rows if r.get("name") == YILUN_NAME]
    if not yilun_rows:
        fail(f"{YILUN_NAME} has no rows in generated-author-info.csv")

    # Verify shard files only contain target institutions.
    for ch in string.ascii_lowercase:
        _, shard_rows = read_csv(Path(f"csrankings-{ch}.csv"))
        check_affiliations(shard_rows, "affiliation", f"csrankings-{ch}.csv")

    # Validate Yilun details file consistency with generated-author-info rows.
    payload_path = Path("yilun-papers.json")
    if not payload_path.exists():
        fail("yilun-papers.json is missing")
    with payload_path.open("r", encoding="utf-8") as infile:
        payload = json.load(infile)

    records = payload.get("records", [])
    if not records:
        fail("yilun-papers.json has no records")

    if payload.get("canonical_name") != YILUN_NAME:
        fail("yilun-papers.json canonical_name mismatch")

    # Cross-check counted paper totals by area/year against generated-author-info.csv for Yilun.
    counted: Dict[Tuple[str, int], int] = {}
    for rec in records:
        if rec.get("included_by_csrankings"):
            key = (rec.get("area", ""), int(rec.get("year")))
            counted[key] = counted.get(key, 0) + 1

    info_counts: Dict[Tuple[str, int], int] = {}
    for row in yilun_rows:
        key = (row.get("area", ""), int(row.get("year", "0")))
        info_counts[key] = int(float(row.get("count", "0")))

    if counted != info_counts:
        missing = sorted(set(info_counts) - set(counted))[:5]
        extra = sorted(set(counted) - set(info_counts))[:5]
        fail(f"yilun-papers.json count mismatch vs generated-author-info.csv (missing={missing}, extra={extra})")

    displayed = [
        rec
        for rec in records
        if rec.get("included_by_csrankings")
        and DISPLAY_START_YEAR <= int(rec.get("year")) <= DISPLAY_END_YEAR
    ]
    if not displayed:
        fail(f"No counted Yilun papers in {DISPLAY_START_YEAR}-{DISPLAY_END_YEAR}")

    # Optional parity checks vs baseline files (excluding Yilun).
    if args.baseline_csrankings:
        fields, baseline_rows = read_csv(Path(args.baseline_csrankings))
        baseline_filtered = [
            r
            for r in baseline_rows
            if r.get("affiliation") in TARGET_INSTITUTIONS and r.get("name") != YILUN_NAME
        ]
        _, current_rows = read_csv(Path("csrankings.csv"))
        current_filtered = [r for r in current_rows if r.get("name") != YILUN_NAME]
        if {tuple_key(r, fields) for r in baseline_filtered} != {tuple_key(r, fields) for r in current_filtered}:
            fail("csrankings.csv rows for existing Yale/Zhejiang faculty changed unexpectedly vs baseline")

    if args.baseline_author_info:
        fields, baseline_rows = read_csv(Path(args.baseline_author_info))
        baseline_filtered = [
            r
            for r in baseline_rows
            if r.get("dept") in TARGET_INSTITUTIONS and r.get("name") != YILUN_NAME
        ]
        _, current_rows = read_csv(Path("generated-author-info.csv"))
        current_filtered = [r for r in current_rows if r.get("name") != YILUN_NAME]
        if {tuple_key(r, fields) for r in baseline_filtered} != {tuple_key(r, fields) for r in current_filtered}:
            fail("generated-author-info.csv rows changed unexpectedly for existing Yale/Zhejiang faculty")

    print("Verification passed:")
    print(f"- csrankings.csv rows: {len(cs_rows)}")
    print(f"- generated-author-info.csv rows: {len(author_rows)}")
    print(f"- {YILUN_NAME} rows in generated-author-info.csv: {len(yilun_rows)}")
    print(f"- Yilun records in yilun-papers.json: {len(records)}")


if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as exc:
        fail(f"Missing file: {exc.filename}")
