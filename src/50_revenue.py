#!/usr/bin/env python3
"""
50_revenue.py  --  Property-tax revenue per parcel (all overlapping districts).

    tax = Measure-50 assessed value x consolidated rate / 1000

joined county-aware, since Portland spans three counties whose tax-code formats
differ (Multnomah '001', Washington '051.50', Clackamas '000-002').

Run:  conda run -n vpa python src/50_revenue.py
Outputs:
  data/processed/taxlots_value_per_acre.geojson   (adds tax_revenue columns)
  data/processed/revenue_summary.json
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

PARCELS = "data/processed/taxlots_value_per_acre.geojson"
RATES = "data/processed/tax_rates_by_code.csv"
OUT_SUM = Path("data/processed/revenue_summary.json")


def norm_code(county: str, code: str) -> str:
    code = str(code).strip()
    if county == "M":
        return code.split(".")[0].zfill(3)   # RLIS may carry '201' or '201.00'
    if county == "C":
        c = code.replace("-", "")
        return f"{c[:3]}-{c[3:]}" if len(c) == 6 else code  # RLIS '012019' -> 6a '012-019'
    return code


def main():
    g = gpd.read_file(PARCELS)
    rates = pd.read_csv(RATES, dtype={"taxcode": str})
    rates["key"] = rates["county"] + "|" + rates.apply(
        lambda r: norm_code(r["county"], r["taxcode"]), axis=1)
    lookup = dict(zip(rates["key"], rates["total_rate"]))

    g["key"] = g["COUNTY"].astype(str) + "|" + [
        norm_code(c, t) for c, t in zip(g["COUNTY"].astype(str), g["TAXCODE"].astype(str))]
    g["total_rate"] = g["key"].map(lookup)
    g["av"] = pd.to_numeric(g["av"], errors="coerce").fillna(0)
    g["acres"] = pd.to_numeric(g["acres"], errors="coerce").fillna(0)
    g["tax_revenue"] = g["av"] * g["total_rate"].fillna(0) / 1000.0
    g["tax_revenue_per_acre"] = np.where(g["acres"] > 0,
                                         g["tax_revenue"] / g["acres"], np.nan)

    matched = g["total_rate"].notna()
    unmatched = g.loc[~matched & (g["av"] > 0), ["COUNTY", "TAXCODE"]]
    g.drop(columns=["key"]).to_file(PARCELS, driver="GeoJSON")

    summary = {
        "parcels": int(len(g)),
        "parcels_rate_matched": int(matched.sum()),
        "match_rate_pct": round(100 * matched.mean(), 1),
        "total_tax_revenue_all_districts": round(float(g["tax_revenue"].sum())),
        "median_rate_per_1000": round(float(g.loc[matched, "total_rate"].median()), 4),
        "unmatched_codes": unmatched.value_counts().head(10).to_dict()
        if len(unmatched) else {},
    }
    summary["unmatched_codes"] = {f"{k[0]}|{k[1]}": v for k, v
                                  in summary["unmatched_codes"].items()}
    json.dump(summary, open(OUT_SUM, "w"), indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
