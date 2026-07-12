#!/usr/bin/env python3
"""
40_tax_rates.py  --  Consolidated property-tax rates per tax code area, for the
three counties Portland spans. Sources (all public assessor publications):

  Multnomah   "Table of Consolidated Tax Rates for Levy Code Areas" (PDF, 2 pp).
              Row layout: the levy code opens the line and repeats at the end;
              the figure immediately before the trailing code is TOTAL ALL RATES.
  Clackamas   SAL Table 6a (xlsx): TCA header rows carry the code; district rows
              carry TAX_RATE. Consolidated rate = sum of district rates per TCA.
  Washington  "Summary of Assessment & Tax Roll" rate detail (PDF): blocks per
              code area ending in a "Total Tax Rate" line whose last figure is
              the consolidated total.

Rates are $ per $1,000 of Measure-50 assessed value.

Run:  conda run -n vpa python src/40_tax_rates.py
Output: data/processed/tax_rates_by_code.csv   (county, taxcode, total_rate)
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

import pandas as pd
from pypdf import PdfReader

AT = Path("Background Info/County A&T Data")
OUT = Path("data/processed/tax_rates_by_code.csv")

MULT_PDF = AT / "Multnomah 2025-2026-Levy-Code-Rates.pdf"
CLACK_XLSX = AT / "table6a2025.xlsx"
WASH_PDF = AT / "Summary A&T_Tax Year 2025-2026.pdf"


def multnomah() -> list[tuple[str, str, float]]:
    rows = []
    r = PdfReader(str(MULT_PDF))
    pat = re.compile(r"^\s*(\d{3})\s+(.*?)(\d+\.\d+)\s+\1\s*$")
    for page in r.pages:
        for line in (page.extract_text() or "").splitlines():
            m = pat.match(line.strip())
            if m:
                rows.append(("M", m.group(1), float(m.group(3))))
    return rows


def clackamas() -> list[tuple[str, str, float]]:
    df = pd.read_excel(CLACK_XLSX, sheet_name="Table 6a", header=None,
                       names=["dor", "tca", "value", "levy", "rate"])
    rows = []
    tca = None
    total = 0.0
    for _, rec in df.iterrows():
        if pd.notna(rec["tca"]) and re.fullmatch(r"[\d-]+", str(rec["tca"]).strip()):
            if tca is not None:
                rows.append(("C", tca, round(total, 4)))
            tca, total = str(rec["tca"]).strip(), 0.0
        elif tca is not None and pd.notna(rec["rate"]):
            try:
                total += float(rec["rate"])
            except (TypeError, ValueError):
                pass
    if tca is not None:
        rows.append(("C", tca, round(total, 4)))
    return rows


def washington() -> list[tuple[str, str, float]]:
    rows = []
    r = PdfReader(str(WASH_PDF))
    code_re = re.compile(r"^(\d{3}\.\d{2})\b")
    current = None
    for page in r.pages:
        text = page.extract_text() or ""
        if "Tax Rate Detail" not in text and current is None:
            continue
        for line in text.splitlines():
            line = line.strip()
            m = code_re.match(line)
            if m:
                current = m.group(1)
            elif current and line.startswith("Total Tax Rate"):
                nums = re.findall(r"\d+\.\d+", line)
                if nums:
                    rows.append(("W", current, float(nums[-1])))
                current = None
    return rows


def main():
    rows = multnomah() + clackamas() + washington()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    seen = {}
    for county, code, rate in rows:
        seen.setdefault((county, code), rate)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["county", "taxcode", "total_rate"])
        for (county, code), rate in sorted(seen.items()):
            w.writerow([county, code, rate])
    by = {}
    for county, _ in seen:
        by[county] = by.get(county, 0) + 1
    print(f"code areas: {by}  -> {OUT}")
    # spot checks
    for key in [("M", "001"), ("M", "201"), ("W", "051.50")]:
        if key in seen:
            print(f"  {key[0]} {key[1]}: {seen[key]}")


if __name__ == "__main__":
    main()
