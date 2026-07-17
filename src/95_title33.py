#!/usr/bin/env python3
"""
95_title33.py  --  Extract Portland zoning development standards from Title 33
(eff. 2026-07-01 compilation; base-zone chapters carry 1/1/25-3/1/25 pages).

Captures the four summary tables' RAW TEXT as ground truth and writes the
validated standards to CSV:

  Table 110-4  Single-dwelling zones   RF R20 R10 R7 R5 R2.5   (FAR by unit
               count under the Residential Infill Project; height)
  Table 120-4  Multi-dwelling zones    RM1-RM4 RX RMP          (FAR, height,
               MINIMUM density -- Portland mandates a floor)
  Table 130-2  Commercial/Mixed Use    CR CM1 CM2 CM3 CE CX    (FAR, height,
               minimum density in CM2/CM3)
  Table 140-2  Employment/Industrial   EG1 EG2 EX IG1 IG2 IH   (FAR, height)

The numeric constants below were transcribed from those captures (footnotes and
location-dependent variants resolved conservatively; see notes column).
Bonus FARs via 33.110.210/265, 33.120.210, Table 130-3, 33.140.205.C.

Run:  conda run -n vpa python src/95_title33.py
Outputs:
  data/processed/title33_tables/*.txt      raw captures
  data/processed/zoning_standards.csv
"""
from __future__ import annotations

import csv
from pathlib import Path

from pypdf import PdfReader

PDF = Path("Background Info/Title 33, Planning & Zoning Code (effective July 1, 2026).PDF")
TABLES = Path("data/processed/title33_tables")
OUT = Path("data/processed/zoning_standards.csv")

CAPTURES = {  # chapter -> (0-based page range)
    "110_single_dwelling": range(42, 47),
    "120_multi_dwelling": range(95, 104),
    "130_commercial_mixed_use": range(163, 174),
    "140_employment_industrial": range(220, 225),
}

# zone, family, far_base, far_bonus, height_ft, min_density_sqft_per_unit, notes
# far values are the BASE maximum FAR; far_bonus the maximum with bonuses.
# Single-dwelling: base = the 4+-unit FAR (RIP); bonus = 4+-unit bonus FAR.
# None = the code sets no limit (or the standard does not apply).
STANDARDS = [
    ("RF",   "single", None, None, 30, None, "no FAR limit (Table 110-4)"),
    ("R20",  "single", 0.7, 0.8, 30, None, "FAR for 4+ units; 0.4 for 1 unit"),
    ("R10",  "single", 0.7, 0.8, 30, None, "FAR for 4+ units; 0.4 for 1 unit"),
    ("R7",   "single", 0.7, 0.8, 30, None, "FAR for 4+ units; 0.4 for 1 unit"),
    ("R5",   "single", 0.8, 0.9, 30, None, "FAR for 4+ units; 0.5 for 1 unit"),
    ("R2.5", "single", 1.0, 1.1, 35, None, "FAR for 4+ units; 0.7 for 1 unit"),
    ("RM1",  "multi",  1.0, 1.5, 35, 2500, "min density 1u/2500sf (~17 du/ac)"),
    ("RM2",  "multi",  1.5, 2.25, 45, 1450, "min density 1u/1450sf (~30 du/ac)"),
    ("RM3",  "multi",  2.0, 3.0, 65, 1000, "min density 1u/1000sf (~44 du/ac)"),
    ("RM4",  "multi",  3.0, 4.0, 75, 1000, "Table: '4:1 or 3:1' by location; base 3, high 4"),
    ("RX",   "multi",  4.0, 6.0, 100, 500, "min density 1u/500sf (~87 du/ac)"),
    ("RMP",  "multi",  None, None, 35, None, "mobile home park; density max 1u/1500sf"),
    ("CR",   "commercial", 1.0, None, 30, None, ""),
    ("CM1",  "commercial", 1.5, 2.5, 35, None, "bonus via Table 130-3"),
    ("CM2",  "commercial", 2.5, 4.0, 45, 1450, "min density 1u/1450sf; bonus 130-3"),
    ("CM3",  "commercial", 3.0, 5.0, 65, 1000, "min density 1u/1000sf; bonus 130-3"),
    ("CE",   "commercial", 2.5, 4.0, 45, None, "bonus via Table 130-3"),
    ("CX",   "commercial", 4.0, 6.0, 75, None, "Central City plan district sets higher"),
    ("EG1",  "employment", 3.0, None, 45, None, ""),
    ("EG2",  "employment", 3.0, None, None, None, "no height limit"),
    ("EX",   "employment", 3.0, 5.0, 65, None, "5:1 with inclusionary housing bonus"),
    ("IG1",  "industrial", None, None, None, None, "no FAR/height limit"),
    ("IG2",  "industrial", None, None, None, None, "no FAR/height limit"),
    ("IH",   "industrial", None, None, None, None, "no FAR/height limit"),
    ("OS",   "open_space", None, None, None, None, "open space; standards n/a"),
    ("CI1",  "institutional", None, None, None, None, "campus institutional (ch. 33.150)"),
    ("CI2",  "institutional", None, None, None, None, "campus institutional (ch. 33.150)"),
    ("IR",   "institutional", None, None, None, None, "institutional residential"),
]


def main():
    r = PdfReader(str(PDF))
    TABLES.mkdir(parents=True, exist_ok=True)
    for name, rng in CAPTURES.items():
        text = "\n".join((r.pages[i].extract_text() or "") for i in rng)
        (TABLES / f"{name}.txt").write_text(text, encoding="utf-8")
        print(f"  captured {name}: pp.{rng.start+1}-{rng.stop} "
              f"({len(text):,} chars)")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["zone", "family", "far_base", "far_bonus", "height_ft",
                    "min_density_sqft_per_unit", "notes"])
        w.writerows(STANDARDS)
    print(f"wrote {OUT} ({len(STANDARDS)} zones)")


if __name__ == "__main__":
    main()
