#!/usr/bin/env python3
"""
Build a Zhejiang+Yale-only CSRankings dataset.

This script:
1. Keeps only faculty rows affiliated with Zhejiang University or Yale University.
2. Ensures Yilun Zhao 0001 (Zhejiang) exists in the dataset.
3. Rewrites csrankings-*.csv shards, csrankings.csv, and split helper CSVs.
4. Filters institutions.csv to only required institutions.
5. Optionally trims dblp-aliases.csv to rows relevant to kept faculty.
"""

from __future__ import annotations

import argparse
import csv
import string
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


TARGET_INSTITUTIONS = {"Zhejiang University", "Yale University"}

YILUN_ENTRY = {
    "name": "Yilun Zhao 0001",
    "affiliation": "Zhejiang University",
    "homepage": "https://yilunzhao.com",
    "scholarid": "NOSCHOLARPAGE",
    "orcid": "0000-0000-0000-0000",
}


def read_csv_rows(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as infile:
        reader = csv.DictReader(infile)
        if not reader.fieldnames:
            raise ValueError(f"{path} has no header")
        rows = [{k: (v or "").strip() for k, v in row.items()} for row in reader]
        return list(reader.fieldnames), rows


def write_csv_rows(path: Path, fieldnames: Sequence[str], rows: Iterable[Dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def normalize_row(row: Dict[str, str], fieldnames: Sequence[str]) -> Dict[str, str]:
    return {field: (row.get(field, "") or "").strip() for field in fieldnames}


def key_for_row(row: Dict[str, str], fieldnames: Sequence[str]) -> Tuple[str, ...]:
    return tuple((row.get(field, "") or "").strip() for field in fieldnames)


def dedupe_rows(rows: Iterable[Dict[str, str]], fieldnames: Sequence[str]) -> List[Dict[str, str]]:
    seen = set()
    output: List[Dict[str, str]] = []
    for row in rows:
        key = key_for_row(row, fieldnames)
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def shard_for_name(name: str) -> str:
    for ch in name.strip().lower():
        if "a" <= ch <= "z":
            return ch
    return "a"


def is_yilun_variant(name: str) -> bool:
    return name.strip().startswith("Yilun Zhao")


def filter_and_rebuild_subset(filter_aliases: bool) -> None:
    fieldnames, source_rows = read_csv_rows(Path("csrankings.csv"))
    all_rows: List[Dict[str, str]] = []
    for row in source_rows:
        if row.get("affiliation", "") in TARGET_INSTITUTIONS:
            # Keep only the explicitly selected Yilun identity, including affiliation.
            if is_yilun_variant(row.get("name", "")):
                if (
                    row.get("name", "") != YILUN_ENTRY["name"]
                    or row.get("affiliation", "") != YILUN_ENTRY["affiliation"]
                ):
                    continue
            all_rows.append(normalize_row(row, fieldnames))

    yilun_name = YILUN_ENTRY["name"]
    yilun_present = any(
        row.get("name") == yilun_name and row.get("affiliation") == YILUN_ENTRY["affiliation"]
        for row in all_rows
    )
    if not yilun_present:
        all_rows.append(normalize_row(YILUN_ENTRY, fieldnames))

    all_rows = dedupe_rows(all_rows, fieldnames)
    all_rows.sort(
        key=lambda row: (
            row.get("name", "").lower(),
            row.get("affiliation", "").lower(),
            row.get("homepage", "").lower(),
            row.get("scholarid", "").lower(),
        )
    )

    by_shard: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in all_rows:
        by_shard[shard_for_name(row.get("name", ""))].append(row)

    for ch in string.ascii_lowercase:
        write_csv_rows(Path(f"csrankings-{ch}.csv"), fieldnames, by_shard.get(ch, []))

    write_csv_rows(Path("csrankings.csv"), fieldnames, all_rows)

    write_csv_rows(
        Path("faculty-affiliations.csv"),
        ["name", "affiliation"],
        [{"name": r["name"], "affiliation": r["affiliation"]} for r in all_rows],
    )
    write_csv_rows(
        Path("homepages.csv"),
        ["name", "homepage"],
        [{"name": r["name"], "homepage": r["homepage"]} for r in all_rows],
    )
    write_csv_rows(
        Path("scholar.csv"),
        ["name", "scholarid"],
        [{"name": r["name"], "scholarid": r["scholarid"]} for r in all_rows],
    )

    inst_fields, inst_rows = read_csv_rows(Path("institutions.csv"))
    kept_inst = [r for r in inst_rows if r.get("institution", "") in TARGET_INSTITUTIONS]
    missing_inst = TARGET_INSTITUTIONS - {r.get("institution", "") for r in kept_inst}
    if missing_inst:
        raise RuntimeError(f"Missing institutions in institutions.csv: {sorted(missing_inst)}")
    write_csv_rows(Path("institutions.csv"), inst_fields, kept_inst)

    if filter_aliases and Path("dblp-aliases.csv").exists():
        alias_fields, alias_rows = read_csv_rows(Path("dblp-aliases.csv"))
        if alias_fields != ["alias", "name"]:
            raise RuntimeError("Unexpected header for dblp-aliases.csv")
        faculty_names = {r["name"] for r in all_rows}
        kept_aliases = [
            row
            for row in alias_rows
            if row.get("name", "") in faculty_names or row.get("alias", "") in faculty_names
        ]
        kept_aliases = dedupe_rows(kept_aliases, alias_fields)
        kept_aliases.sort(key=lambda row: (row.get("alias", "").lower(), row.get("name", "").lower()))
        write_csv_rows(Path("dblp-aliases.csv"), alias_fields, kept_aliases)

    counts = Counter(row["affiliation"] for row in all_rows)
    print(f"Kept faculty rows: {len(all_rows)}")
    for inst in sorted(TARGET_INSTITUTIONS):
        print(f"  {inst}: {counts.get(inst, 0)}")
    print(f"Yilun present: {'yes' if any(r['name'] == yilun_name for r in all_rows) else 'no'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Zhejiang+Yale-only CSRankings data files.")
    parser.add_argument(
        "--no-filter-aliases",
        action="store_true",
        help="Do not trim dblp-aliases.csv.",
    )
    args = parser.parse_args()
    filter_and_rebuild_subset(filter_aliases=not args.no_filter_aliases)


if __name__ == "__main__":
    main()
