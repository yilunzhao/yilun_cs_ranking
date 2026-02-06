#!/usr/bin/env python3
"""
Generate Yilun paper details from filtered DBLP using CSRankings counting logic.
"""

from __future__ import annotations

import argparse
import json
import lzma
import re
from typing import Dict, List, Optional, Tuple

USING_LXML = True
try:
    from lxml import etree
except ImportError:
    import xml.etree.ElementTree as etree  # type: ignore
    USING_LXML = False

from csrankings import (
    Area,
    Conference,
    Title,
    CGF_EUROGRAPHICS_Volume,
    TOG_SIGGRAPH_Asia_Volume,
    TOG_SIGGRAPH_Volume,
    TVCG_Vis_Volume,
    TVCG_VR_Volume,
    confdict,
    countPaper,
    map_pacmmod_to_conference,
    pagecount,
    startpage,
)


def get_element_text(elem) -> str:
    return "".join(elem.itertext()).strip() if elem is not None else ""


def normalize_author_name(name: str) -> str:
    compact = re.sub(r"\s+", " ", name.strip())
    compact = re.sub(r"\s+\d{4}$", "", compact)
    return compact.lower()


def map_area_and_conf(
    confname: Conference, year: int, volume: str, number: str
) -> Tuple[Optional[Conference], Optional[Area], Optional[str], int]:
    if confname not in confdict:
        return None, None, "Venue not tracked by CSRankings.", year

    areaname = confdict[confname]

    if areaname == Area("pacmpl") or areaname == Area("pacmse"):
        mapped_conf = Conference(number)
        if mapped_conf not in confdict:
            return None, None, "PACM issue not mapped to a CSRankings venue.", year
        confname = mapped_conf
        areaname = confdict[confname]
    elif areaname == Area("pacmmod"):
        confname, year = map_pacmmod_to_conference(confname, year, number)
        areaname = confdict[confname]
    elif confname == Conference("ACM Trans. Graph."):
        if year in TOG_SIGGRAPH_Volume:
            vol, num = TOG_SIGGRAPH_Volume[year]
            if volume == str(vol) and number == str(num):
                confname = Conference("SIGGRAPH")
                areaname = confdict[confname]
        if year in TOG_SIGGRAPH_Asia_Volume:
            vol, num = TOG_SIGGRAPH_Asia_Volume[year]
            if volume == str(vol) and number == str(num):
                confname = Conference("SIGGRAPH Asia")
                areaname = confdict[confname]
    elif confname == Conference("Comput. Graph. Forum"):
        if year in CGF_EUROGRAPHICS_Volume:
            vol, num = CGF_EUROGRAPHICS_Volume[year]
            if volume == str(vol) and number == str(num):
                confname = Conference("EUROGRAPHICS")
                areaname = confdict[confname]
    elif confname == Conference("IEEE Trans. Vis. Comput. Graph."):
        if year in TVCG_Vis_Volume:
            vol, num = TVCG_Vis_Volume[year]
            if volume == str(vol) and number == str(num):
                areaname = Area("vis")
        if year in TVCG_VR_Volume:
            vol, num = TVCG_VR_Volume[year]
            if volume == str(vol) and number == str(num):
                confname = Conference("VR")
                areaname = Area("vr")

    return confname, areaname, None, year


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Yilun paper details JSON.")
    parser.add_argument("--dblp", default="dblp.xml.xz", help="Path to filtered DBLP xz file.")
    parser.add_argument("--output", default="yilun-papers.json", help="Output JSON path.")
    parser.add_argument("--canonical-name", default="Yilun Zhao 0007")
    parser.add_argument("--alias-name", default="Yilun Zhao")
    parser.add_argument("--display-start-year", type=int, default=2022)
    parser.add_argument("--display-end-year", type=int, default=2026)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    matched_names = {args.canonical_name, args.alias_name}
    matched_normalized = {normalize_author_name(name) for name in matched_names}
    records: List[Dict] = []

    with lzma.open(args.dblp, "rb") as xz:
        if USING_LXML:
            context = etree.iterparse(
                xz,
                events=("end",),
                tag=("inproceedings", "article"),
                load_dtd=True,
                resolve_entities=True,
                huge_tree=True,
            )
        else:
            context = etree.iterparse(
                xz,
                events=("end",),
            )

        for _, elem in context:
            if not USING_LXML and elem.tag not in ("inproceedings", "article"):
                continue
            author_elems = elem.findall("author")
            if not author_elems:
                elem.clear()
                continue

            author_list = [get_element_text(a) for a in author_elems]
            match_indices = [
                i for i, name in enumerate(author_list) if normalize_author_name(name) in matched_normalized
            ]
            if not match_indices:
                elem.clear()
                continue

            booktitle = get_element_text(elem.find("booktitle"))
            journal = get_element_text(elem.find("journal"))
            confname = Conference(booktitle if booktitle else journal)
            if not confname:
                elem.clear()
                continue

            volume = get_element_text(elem.find("volume")) or "0"
            number = get_element_text(elem.find("number")) or "0"
            year_text = get_element_text(elem.find("year"))
            if not year_text:
                elem.clear()
                continue
            year = int(year_text)
            pages = get_element_text(elem.find("pages"))
            title = Title(get_element_text(elem.find("title")))
            url = get_element_text(elem.find("url"))

            mapped_conf, mapped_area, venue_exclusion, mapped_year = map_area_and_conf(
                confname, year, volume, number
            )

            if pages:
                pcount = pagecount(pages)
                spage = startpage(pages)
            else:
                pcount = -1
                spage = -1

            included_by_csrankings = False
            exclusion_reason = ""
            area = ""
            venue = str(confname)

            if venue_exclusion:
                exclusion_reason = venue_exclusion
            else:
                assert mapped_conf is not None and mapped_area is not None
                venue = str(mapped_conf)
                area = str(mapped_area)
                included_by_csrankings = countPaper(
                    mapped_conf,
                    mapped_year,
                    volume,
                    number,
                    pages,
                    spage,
                    pcount,
                    url,
                    title,
                )
                if not included_by_csrankings:
                    exclusion_reason = "Excluded by CSRankings paper-count rules (pages/track exceptions)."

            idx = match_indices[0]
            matched_author = author_list[idx]
            is_first = idx == 0
            is_second = idx == 1
            is_last = idx == len(author_list) - 1

            in_display_range = args.display_start_year <= mapped_year <= args.display_end_year
            included_in_displayed_metrics = included_by_csrankings and in_display_range

            if included_by_csrankings and not in_display_range:
                exclusion_reason = (
                    f"Excluded from displayed metrics: year {mapped_year} is outside "
                    f"{args.display_start_year}-{args.display_end_year}."
                )

            records.append(
                {
                    "title": str(title),
                    "year": mapped_year,
                    "venue": venue,
                    "area": area,
                    "url": url,
                    "authors": author_list,
                    "numauthors": len(author_list),
                    "matched_author": matched_author,
                    "author_index": idx,
                    "is_first_author": is_first,
                    "is_second_author": is_second,
                    "is_last_author": is_last,
                    "included_by_csrankings": included_by_csrankings,
                    "included_in_displayed_metrics": included_in_displayed_metrics,
                    "exclusion_reason": exclusion_reason,
                }
            )

            elem.clear()
            if USING_LXML:
                while elem.getprevious() is not None:
                    del elem.getparent()[0]

    records.sort(key=lambda r: (-r["year"], r["venue"], r["title"]))
    payload = {
        "canonical_name": args.canonical_name,
        "matched_names": sorted(matched_names),
        "display_start_year": args.display_start_year,
        "display_end_year": args.display_end_year,
        "records": records,
    }
    with open(args.output, "w", encoding="utf-8") as outfile:
        json.dump(payload, outfile, indent=2)

    print(f"Wrote {args.output} with {len(records)} records.")


if __name__ == "__main__":
    main()
