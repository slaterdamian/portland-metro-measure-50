#!/usr/bin/env python3
"""
20_value_per_acre.py  --  Phase 1: taxable & market value per acre, Portland OR.

Computes per parcel, from the Portland slice of RLIS Taxlots (Public):
  * av / rmv                    Measure-50 assessed value & real market value
  * acres                       assessor acreage (A_T_ACRES; GIS_ACRES fallback)
  * assessed_value_per_acre     the Urban3 headline metric (the taxable base)
  * rmv_per_acre                market-value counterpart
  * taxed_share                 av / rmv -- Measure 50 compression per parcel

OREGON NOTE: property tax is levied on Measure-50 assessed value (ASSESSVAL),
not real market value (TOTALVAL). Revenue in dollars additionally needs the
Multnomah County tax-code-area consolidated rate table (pending input);
value-per-acre requires no rates.

Run:  conda run -n vpa python src/20_value_per_acre.py
Outputs:
  data/processed/taxlots_value_per_acre.geojson
  data/processed/phase1_summary.json
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

SRC = "data/interim/taxlots_portland.geojson"
OUT_GJ = Path("data/processed/taxlots_value_per_acre.geojson")
OUT_SUM = Path("data/processed/phase1_summary.json")


def num(s):
    return pd.to_numeric(s, errors="coerce").fillna(0.0)


def main():
    print("reading Portland taxlots ...")
    g = gpd.read_file(SRC)
    g["av"] = num(g["ASSESSVAL"])
    g["rmv"] = num(g["TOTALVAL"])
    at, gis = num(g["A_T_ACRES"]), num(g["GIS_ACRES"])
    g["acres"] = np.where(at > 0, at, gis)
    g["acres_source"] = np.where(at > 0, "A_T", "GIS")
    g = g[g.geometry.notna() & ~g.geometry.is_empty].copy()

    with np.errstate(divide="ignore", invalid="ignore"):
        g["assessed_value_per_acre"] = np.where(g["acres"] > 0, g["av"] / g["acres"], np.nan)
        g["rmv_per_acre"] = np.where(g["acres"] > 0, g["rmv"] / g["acres"], np.nan)
        g["taxed_share"] = np.where(g["rmv"] > 0, g["av"] / g["rmv"], np.nan)

    keep = ["TLID", "PRIMACCNUM", "SITEADDR", "TAXCODE", "COUNTY", "PROP_CODE",
            "LANDUSE", "STATECLASS", "YEARBUILT", "BLDGSQFT", "PUBLIC_OWN",
            "OWNERTYPE", "HAS_MANY", "acres", "acres_source", "av", "rmv",
            "assessed_value_per_acre", "rmv_per_acre", "taxed_share", "geometry"]
    OUT_GJ.parent.mkdir(parents=True, exist_ok=True)
    g[keep].to_file(OUT_GJ, driver="GeoJSON")

    val = g[(g["av"] > 0) & (g["acres"] > 0)]
    summary = {
        "jurisdiction": "City of Portland, OR (RLIS JURIS_CITY=PORTLAND)",
        "source": "Metro RLIS Taxlots (Public), ODbL; values from county assessors",
        "tax_year_snapshot": "2025-2026 roll (RLIS current)",
        "parcels": int(len(g)),
        "parcels_with_av": int((g["av"] > 0).sum()),
        "county_split": g["COUNTY"].value_counts().to_dict(),
        "total_assessed_value": round(float(g["av"].sum())),
        "total_real_market_value": round(float(g["rmv"].sum())),
        "citywide_taxed_share": round(float(g["av"].sum() / g["rmv"].sum()), 3),
        "median_av_per_acre": round(float(val["assessed_value_per_acre"].median())),
        "median_taxed_share": round(float(val["taxed_share"].median()), 3),
        "distinct_taxcodes": int(g["TAXCODE"].nunique()),
    }
    json.dump(summary, open(OUT_SUM, "w"), indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
