#!/usr/bin/env python3
"""
80_cost_allocation.py  --  Frame A city net map (approved methodology,
docs/cost-allocation.md).

Revenue side: each parcel's City-of-Portland property tax
    city_tax = AV x city rate of its code area / 1000   (stage-60 categories)

Cost side: FY2025-26 tax-supported city services (General Fund + FPDR),
allocated two ways (both reported -- the basis choice is a finding, not a
nuisance):

  DEMAND basis                                    NETWORK basis
    Police+Fire+FPDR  -> units + nonres sqft/1500   whole pool -> city network
    Parks+Housing     -> dwelling units              feet nearest each parcel
    all other GF      -> per parcel                  (BES pipes + water mains
                                                      + Portland streets)

Variants:
  A1 (redistribution): pool = city tax actually collected -> citywide net = 0.
  A2 (coverage):       pool = full GF+FPDR -> citywide net is negative by
                       construction (property tax funds ~54% of these services;
                       business taxes and fees fund the rest).

Run:  conda run -n vpa python src/80_cost_allocation.py
Outputs:
  data/processed/net_city.geojson
  data/processed/phase2_summary.json
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

PARCELS = "data/processed/taxlots_value_per_acre.geojson"
RATECAT = "data/processed/rate_categories_by_code.csv"
BUDGET = "data/processed/budget_bureau_fund.csv"
HOUSING = "data/interim/housing_portland.geojson"
NETWORKS = [  # path, filter(fn), label
    ("data/interim/collection_system.geojson",
     lambda d: d[(d["OWNRSHIP"] == "BES") & (d["SYSTEM"].isin(["SEWER", "STORM"]))],
     "BES pipes"),
    ("data/interim/water_mains.geojson", lambda d: d, "water mains"),
    ("data/interim/streets_portland.geojson", lambda d: d, "streets"),
]
OUT_GJ = Path("data/processed/net_city.geojson")
OUT_SUM = Path("data/processed/phase2_summary.json")

EPSG = 2913
SQFT_PER_UNIT_EQ = 1500.0   # non-residential sqft equated to one dwelling
NEAREST_MAX_FT = 150.0
NONRES_LANDUSE = {"COM", "IND"}


def num(s):
    return pd.to_numeric(s, errors="coerce").fillna(0.0)


def norm_code(county, code):
    code = str(code).strip()
    if county == "M":
        return code.split(".")[0].zfill(3)
    if county == "C":
        c = code.replace("-", "")
        return f"{c[:3]}-{c[3:]}" if len(c) == 6 else code
    return code


def norm_tlid(s):
    return s.astype(str).str.replace(" ", "", regex=False).str.upper()


def main():
    # ---- cost pools from the parsed budget -----------------------------------
    b = pd.read_csv(BUDGET)
    gf = b[b["fund"] == "General Fund"].set_index("bureau")["total"]
    fpdr = b[b["fund"].str.contains("Disability & Retirement", na=False)]["total"].sum()
    police = gf.get("Portland Police Bureau", 0)
    fire = gf.get("Portland Fire & Rescue", 0)
    parks = gf.get("Portland Parks & Recreation", 0)
    housing_b = gf.get("Portland Housing Bureau", 0)
    admin = gf.sum() - police - fire - parks - housing_b
    pool_intensity = float(police + fire + fpdr)     # units + nonres sqft
    pool_units = float(parks + housing_b)            # dwelling units
    pool_parcel = float(admin)                       # per parcel
    pool_a2 = pool_intensity + pool_units + pool_parcel
    print(f"pools: intensity ${pool_intensity/1e6:.1f}M  units ${pool_units/1e6:.1f}M  "
          f"parcel ${pool_parcel/1e6:.1f}M  -> A2 total ${pool_a2/1e6:.1f}M")

    # ---- parcels + city tax ---------------------------------------------------
    g = gpd.read_file(PARCELS).to_crs(EPSG)
    g["av"] = num(g["av"])
    g["acres"] = num(g["acres"])
    g["BLDGSQFT"] = num(g["BLDGSQFT"])
    g = g[g.geometry.notna() & ~g.geometry.is_empty].reset_index(drop=True)

    rc = pd.read_csv(RATECAT, dtype={"taxcode": str})
    rc["key"] = rc["county"] + "|" + [norm_code(c, t) for c, t
                                      in zip(rc["county"], rc["taxcode"])]
    city_rate = dict(zip(rc["key"], rc["city"]))
    g["key"] = g["COUNTY"].astype(str) + "|" + [
        norm_code(c, t) for c, t in zip(g["COUNTY"].astype(str), g["TAXCODE"].astype(str))]
    g["city_tax"] = g["av"] * g["key"].map(city_rate).fillna(0) / 1000.0
    pool_a1 = float(g["city_tax"].sum())
    print(f"city tax collected: ${pool_a1/1e6:.1f}M (A1 pool)")

    # ---- dwelling units (TLID join, spatial fallback) -------------------------
    h = gpd.read_file(HOUSING).to_crs(EPSG)
    h["UNITS"] = num(h["UNITS"])
    h["tl"] = norm_tlid(h["TLID"])
    g["tl"] = norm_tlid(g["TLID"])
    by_tl = h.groupby("tl")["UNITS"].sum()
    g["units"] = g["tl"].map(by_tl).fillna(0.0)
    matched_units = float(g["units"].sum())
    # spatial fallback for housing rows whose TLID didn't hit a parcel
    miss = h[~h["tl"].isin(set(g["tl"]))]
    if len(miss):
        pts = miss.copy()
        pts["geometry"] = miss.geometry.representative_point()
        j = gpd.sjoin(pts[["UNITS", "geometry"]], g[["geometry"]],
                      how="inner", predicate="within")
        add = j.groupby("index_right")["UNITS"].sum()
        g.loc[add.index, "units"] += add.values
    print(f"dwelling units: {g['units'].sum():,.0f} "
          f"(TLID-joined {matched_units:,.0f}; +spatial {g['units'].sum()-matched_units:,.0f})")

    g["nonres_sqft"] = np.where(g["LANDUSE"].isin(NONRES_LANDUSE), g["BLDGSQFT"], 0.0)
    g["units_eq"] = g["units"] + g["nonres_sqft"] / SQFT_PER_UNIT_EQ

    # ---- network feet nearest each parcel -------------------------------------
    g["infra_ft"] = 0.0
    for path, flt, label in NETWORKS:
        n = flt(gpd.read_file(path)).to_crs(EPSG)
        n = n[n.geometry.notna() & ~n.geometry.is_empty]
        n = gpd.GeoDataFrame({"seg_len": n.geometry.length},
                             geometry=n.geometry, crs=EPSG).reset_index(drop=True)
        j = gpd.sjoin_nearest(n, g[["geometry"]], how="inner",
                              max_distance=NEAREST_MAX_FT)
        add = j.groupby("index_right")["seg_len"].sum()
        g.loc[add.index, "infra_ft"] += add.values
        print(f"  {label}: {len(n):,} segs, {n['seg_len'].sum()/5280:,.0f} mi "
              f"-> {len(add):,} parcels")

    # ---- allocate --------------------------------------------------------------
    def share(col):
        v = g[col].to_numpy(float)
        return v / v.sum()

    alloc_demand = (pool_intensity * share("units_eq")
                    + pool_units * share("units")
                    + pool_parcel / len(g))
    alloc_network = pool_a2 * share("infra_ft")
    g["cost_a2_demand"] = alloc_demand
    g["cost_a2_network"] = alloc_network
    scale = pool_a1 / pool_a2
    for basis in ("demand", "network"):
        g[f"net_a2_{basis}"] = g["city_tax"] - g[f"cost_a2_{basis}"]
        g[f"net_a1_{basis}"] = g["city_tax"] - g[f"cost_a2_{basis}"] * scale
        g[f"net_a2_{basis}_acre"] = np.where(g["acres"] > 0,
                                             g[f"net_a2_{basis}"] / g["acres"], np.nan)

    keep = ["TLID", "SITEADDR", "TAXCODE", "COUNTY", "LANDUSE", "PUBLIC_OWN",
            "acres", "av", "city_tax", "units", "units_eq", "nonres_sqft",
            "infra_ft", "cost_a2_demand", "cost_a2_network",
            "net_a2_demand", "net_a2_network", "net_a1_demand", "net_a1_network",
            "net_a2_demand_acre", "net_a2_network_acre", "geometry"]
    OUT_GJ.parent.mkdir(parents=True, exist_ok=True)
    g[keep].to_crs(4326).to_file(OUT_GJ, driver="GeoJSON")

    taxable = g[g["av"] > 0]
    def stats(col):
        pos = g[col] > 0
        acres_pos = float(g.loc[pos & (g["acres"] > 0), "acres"].sum())
        acres_all = float(g.loc[g["acres"] > 0, "acres"].sum())
        return {"pct_parcels_net_positive": round(100 * float(pos.mean()), 1),
                "pct_taxable_parcels_net_positive":
                    round(100 * float((taxable[col] > 0).mean()), 1),
                "pct_land_area_net_positive": round(100 * acres_pos / acres_all, 1)}

    summary = {
        "pools": {"intensity_police_fire_fpdr": round(pool_intensity),
                  "units_parks_housing": round(pool_units),
                  "per_parcel_admin_other_gf": round(pool_parcel),
                  "A2_total_gf_plus_fpdr": round(pool_a2),
                  "A1_city_tax_collected": round(pool_a1),
                  "property_tax_coverage_of_services": round(pool_a1 / pool_a2, 3)},
        "reconciliation": {
            "alloc_demand_sum": round(float(alloc_demand.sum())),
            "alloc_network_sum": round(float(alloc_network.sum()))},
        "exempt_parcels_public_own": int((g["PUBLIC_OWN"] == 1).sum()),
        "A2_demand": stats("net_a2_demand"),
        "A2_network": stats("net_a2_network"),
        "A1_demand": stats("net_a1_demand"),
        "A1_network": stats("net_a1_network"),
        "citywide_net_A2": round(float(pool_a1 - pool_a2)),
    }
    json.dump(summary, open(OUT_SUM, "w"), indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
