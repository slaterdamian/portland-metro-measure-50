#!/usr/bin/env python3
"""
60_district_revenue.py  --  Who receives Portland's property tax?

Splits each tax code area's consolidated rate into three categories --
  education            school districts, ESDs, community colleges
  city_of_portland     City of Portland levies (incl. FPDR pension, bonds)
  other_government     county, Metro, Port, TriMet, soil & water, urban renewal,
                       fire/water districts, etc.
-- then applies each parcel's Measure-50 AV to get dollars per category.

Per-county methods (formats differ):
  Multnomah   Levy-Code-Rates rows end "... govt_lim govt_bond TOTAL code".
              education = TOTAL - (govt_lim + govt_bond); the City pair is the
              float pair after the LAST 'PORTLAND' token in the government
              section. Both identities validated per row (edu >= 0, city <= govt).
  Washington  Summary rate-detail blocks list every district with a 4-number
              row (edu, govt, bond, total); classified by district name.
  Clackamas   SAL Table 6a district rows classified by LEVY_NAME.

Run:  conda run -n vpa python src/60_district_revenue.py
Outputs:
  data/processed/rate_categories_by_code.csv
  data/processed/district_revenue_summary.json
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from pypdf import PdfReader

AT = Path("Background Info/County A&T Data")
PARCELS = "data/processed/taxlots_value_per_acre.geojson"
OUT_CSV = Path("data/processed/rate_categories_by_code.csv")
OUT_SUM = Path("data/processed/district_revenue_summary.json")

EDU_PAT = re.compile(r"SCH|SCHOOL|ESD|EDUCATION|COM COLL|COMMUNITY COLLEGE|COLLEGE",
                     re.IGNORECASE)
CITY_PAT = re.compile(r"CITY (OF )?PORTLAND|PORTLAND CITY", re.IGNORECASE)
FLOAT = re.compile(r"\d+\.\d+")


def multnomah() -> dict[str, dict]:
    """code -> {edu, city, other, total}; edu derived, city by last-PORTLAND pair."""
    out = {}
    r = PdfReader(str(AT / "Multnomah 2025-2026-Levy-Code-Rates.pdf"))
    row_re = re.compile(r"^\s*(\d{3})\s+(.*?)\s+\1\s*$")
    for page in r.pages:
        for line in (page.extract_text() or "").splitlines():
            m = row_re.match(line.strip())
            if not m:
                continue
            code, body = m.group(1), m.group(2)
            nums = [float(x) for x in FLOAT.findall(body)]
            if len(nums) < 4:
                continue
            total = nums[-1]
            govt = nums[-3] + nums[-2]
            edu = round(total - govt, 4)
            # city: float pair immediately after the LAST 'PORTLAND' token that
            # is followed by numbers (city column sits in the government section)
            city = 0.0
            for tk in re.finditer(r"PORTLAND\s+((?:\d+\.\d+\s*){1,2})", body):
                vals = [float(x) for x in FLOAT.findall(tk.group(1))]
                cand = sum(vals)
                if cand <= govt + 1e-6:
                    city = cand           # keep the last plausible occurrence
            if edu < -0.01 or city > govt + 0.01:
                continue                  # failed validation; leave code out
            out[code] = {"edu": max(edu, 0.0), "city": city,
                         "other": round(govt - city, 4), "total": total}
    return out


def washington() -> dict[str, dict]:
    out = {}
    r = PdfReader(str(AT / "Summary A&T_Tax Year 2025-2026.pdf"))
    code_re = re.compile(r"^(\d{3}\.\d{2})\b(.*)$")
    current = None

    def add(code, name, rate):
        d = out.setdefault(code, {"edu": 0.0, "city": 0.0, "other": 0.0, "total": 0.0})
        if CITY_PAT.search(name):
            d["city"] += rate
        elif EDU_PAT.search(name):
            d["edu"] += rate
        else:
            d["other"] += rate

    for page in r.pages:
        text = page.extract_text() or ""
        if "Tax Rate Detail" not in text and current is None:
            continue
        for raw in text.splitlines():
            line = raw.strip()
            m = code_re.match(line)
            if m:
                current = m.group(1)
                line = m.group(2).strip()
            if current is None or not line:
                continue
            if line.startswith("Total Tax Rate"):
                nums = FLOAT.findall(line)
                if nums:
                    out.setdefault(current, {"edu": 0, "city": 0, "other": 0,
                                             "total": 0})["total"] = float(nums[-1])
                current = None
                continue
            if line.startswith("Assessed Value"):
                continue
            nums = FLOAT.findall(line)
            if nums:
                name = line[:line.find(nums[0])]
                add(current, name, float(nums[-1]))
    return out


def clackamas() -> dict[str, dict]:
    df = pd.read_excel(AT / "table6a2025.xlsx", sheet_name="Table 6a", header=None,
                       names=["dor", "tca", "value", "levy", "rate"])
    out = {}
    tca = None
    for _, rec in df.iterrows():
        if pd.notna(rec["tca"]) and re.fullmatch(r"[\d-]+", str(rec["tca"]).strip()):
            tca = str(rec["tca"]).strip()
            out[tca] = {"edu": 0.0, "city": 0.0, "other": 0.0, "total": 0.0}
        elif tca and pd.notna(rec["rate"]) and pd.notna(rec["levy"]):
            try:
                rate = float(rec["rate"])
            except (TypeError, ValueError):
                continue
            name = str(rec["levy"])
            key = ("city" if CITY_PAT.search(name)
                   else "edu" if EDU_PAT.search(name) else "other")
            out[tca][key] += rate
            out[tca]["total"] += rate
    return out


def norm_code(county, code):
    code = str(code).strip()
    if county == "M":
        return code.split(".")[0].zfill(3)
    if county == "C":
        c = code.replace("-", "")
        return f"{c[:3]}-{c[3:]}" if len(c) == 6 else code
    return code


def main():
    cats = {("M", k): v for k, v in multnomah().items()}
    cats.update({("W", k): v for k, v in washington().items()})
    cats.update({("C", k): v for k, v in clackamas().items()})

    rows = [{"county": c, "taxcode": k, **v} for (c, k), v in sorted(cats.items())]
    pd.DataFrame(rows).to_csv(OUT_CSV, index=False)

    g = gpd.read_file(PARCELS, ignore_geometry=True,
                      columns=["COUNTY", "TAXCODE", "av"])
    g["av"] = pd.to_numeric(g["av"], errors="coerce").fillna(0)
    g["key"] = list(zip(g["COUNTY"].astype(str),
                        [norm_code(c, t) for c, t in
                         zip(g["COUNTY"].astype(str), g["TAXCODE"].astype(str))]))

    dollars = {"education": 0.0, "city_of_portland": 0.0, "other_government": 0.0}
    matched_av = 0.0
    for key, av in zip(g["key"], g["av"]):
        d = cats.get(key)
        if d is None or av <= 0:
            continue
        matched_av += av
        dollars["education"] += av * d["edu"] / 1000
        dollars["city_of_portland"] += av * d["city"] / 1000
        dollars["other_government"] += av * d["other"] / 1000

    total = sum(dollars.values())
    summary = {
        "method": "per-code rate categories x parcel AV; see script docstring",
        "codes_with_categories": {c: sum(1 for (cc, _) in cats if cc == c)
                                  for c in ("M", "W", "C")},
        "matched_av": round(matched_av),
        "total_dollars": round(total),
        "by_category": {k: round(v) for k, v in dollars.items()},
        "shares_pct": {k: round(100 * v / total, 1) for k, v in dollars.items()},
    }
    json.dump(summary, open(OUT_SUM, "w"), indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
