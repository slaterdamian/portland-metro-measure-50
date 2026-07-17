#!/usr/bin/env python3
"""
96_feasibility.py  --  Phase 3: zoning feasibility, derived backwards from the
fiscal net (the project's thesis inverted onto Portland's FAR-based code).

Per zone (RLIS ZONE, joined by parcel centroid):

  solvency        = city tax paid / allocated tax-supported cost (stage 80).
                    Computed under BOTH bases -- demand (units + building
                    area) and network (city infrastructure feet).
  far_now         = built floor area / land  (RLIS BLDGSQFT over acres)
  required_far    = far_now x cost / tax  -- the built intensity at which the
                    zone's city tax would cover its allocated cost, assuming
                    value scales with floor area at the zone's current
                    assessed-$-per-built-sqft. (Linear-value assumption;
                    stated, not hidden.)
  du_ac_now / required_du_ac  -- same logic in dwelling units for residential.

Then the zoning verdict against Title 33 (stage 95): does the code ALLOW the
required intensity (base FAR / bonus FAR), and -- Portland's twist -- does the
code's MINIMUM density already mandate it?

Run:  conda run -n vpa python src/96_feasibility.py
Outputs:
  data/processed/zone_feasibility.csv
  outputs/figures/zone_feasibility.png
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

NET = "data/processed/net_city.geojson"
TAX = "data/processed/taxlots_value_per_acre.geojson"
ZONING = "data/interim/zoning_portland.geojson"
STD = "data/processed/zoning_standards.csv"
OUT_CSV = Path("data/processed/zone_feasibility.csv")
OUT_FIG = Path("outputs/figures/zone_feasibility.png")
EPSG = 2913
SKIP = {"OS", "RF", "RMP", "CI1", "CI2", "IR", "CR"}   # n/a or negligible


def num(s):
    return pd.to_numeric(s, errors="coerce").fillna(0)


def main():
    g = gpd.read_file(NET).to_crs(EPSG)
    for c in ("av", "acres", "city_tax", "cost_a2_demand", "cost_a2_network",
              "units"):
        g[c] = num(g[c])
    g = g[g.geometry.notna() & ~g.geometry.is_empty].copy()

    t = gpd.read_file(TAX, ignore_geometry=True, columns=["TLID", "BLDGSQFT"])
    t["tl"] = t["TLID"].astype(str).str.replace(" ", "", regex=False).str.upper()
    bs = t.drop_duplicates("tl").set_index("tl")["BLDGSQFT"]
    g["tl"] = g["TLID"].astype(str).str.replace(" ", "", regex=False).str.upper()
    g["bldgsqft"] = num(g["tl"].map(bs))

    z = gpd.read_file(ZONING).to_crs(EPSG)[["ZONE", "geometry"]]
    z["geometry"] = z.geometry.make_valid()
    cen = g.copy()
    cen["geometry"] = g.geometry.centroid
    j = gpd.sjoin(cen[["tl", "geometry"]], z, predicate="within", how="left")
    zmap = (j.dropna(subset=["ZONE"]).drop_duplicates("tl")
            .set_index("tl")["ZONE"])
    g["zone"] = g["tl"].map(zmap)

    agg = (g.dropna(subset=["zone"])
           .groupby("zone")
           .agg(parcels=("tl", "size"), acres=("acres", "sum"),
                av=("av", "sum"), tax=("city_tax", "sum"),
                cost_d=("cost_a2_demand", "sum"),
                cost_n=("cost_a2_network", "sum"),
                units=("units", "sum"), bsf=("bldgsqft", "sum"))
           .reset_index())
    agg = agg[(agg["acres"] > 0) & (agg["tax"] > 0)]

    agg["solvency_demand"] = (agg["tax"] / agg["cost_d"]).round(2)
    agg["solvency_network"] = (agg["tax"] / agg["cost_n"]).round(2)
    agg["far_now"] = (agg["bsf"] / (agg["acres"] * 43560)).round(2)
    agg["du_ac_now"] = (agg["units"] / agg["acres"]).round(1)
    with np.errstate(divide="ignore", invalid="ignore"):
        agg["required_far_demand"] = (agg["far_now"] * agg["cost_d"] / agg["tax"]).round(2)
        agg["required_far_network"] = (agg["far_now"] * agg["cost_n"] / agg["tax"]).round(2)
        agg["required_du_ac_demand"] = (agg["du_ac_now"] * agg["cost_d"] / agg["tax"]).round(1)

    std = pd.read_csv(STD)
    std["min_du_ac"] = (43560 / num(std["min_density_sqft_per_unit"])
                        ).replace(np.inf, np.nan).round(1)
    agg = agg.merge(std[["zone", "family", "far_base", "far_bonus",
                         "height_ft", "min_du_ac"]], on="zone", how="left")

    def verdict(r):
        if r["zone"] in SKIP:
            return "n/a"
        if r["solvency_demand"] >= 1:
            return "solvent now"
        if pd.isna(r["far_base"]):
            return "no FAR limit — market-bound, not code-bound"
        req = r["required_far_demand"]
        if req <= r["far_base"]:
            return "achievable under BASE zoning"
        if pd.notna(r["far_bonus"]) and req <= r["far_bonus"]:
            return "achievable only WITH bonus FAR"
        return "exceeds zoned capacity"
    agg["verdict_demand"] = agg.apply(verdict, axis=1)

    # Portland's minimum-density mandate vs the required density
    agg["min_density_covers_requirement"] = np.where(
        agg["min_du_ac"].notna() & (agg["min_du_ac"] >= agg["required_du_ac_demand"]),
        "yes", np.where(agg["min_du_ac"].notna(), "no", ""))

    agg = agg.sort_values("solvency_demand", ascending=False)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    agg.to_csv(OUT_CSV, index=False)
    show = agg[~agg["zone"].isin(SKIP)]
    print(show[["zone", "family", "parcels", "solvency_demand", "solvency_network",
                "far_now", "required_far_demand", "far_base", "far_bonus",
                "du_ac_now", "required_du_ac_demand", "min_du_ac",
                "verdict_demand"]].to_string(index=False))

    # ---- figure: required vs zoned FAR ---------------------------------------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    p = show[show["far_base"].notna() | show["far_now"].gt(0)].copy()
    p = p.sort_values("required_far_demand")
    y = np.arange(len(p))
    fig, ax = plt.subplots(figsize=(10, max(6, 0.42 * len(p))))
    ax.barh(y, p["far_now"], color="#9e9e9e", height=0.55, label="built FAR today")
    ax.scatter(p["required_far_demand"], y, color="#c0392b", zorder=3, s=55,
               label="FAR required for fiscal solvency (demand basis)")
    ax.scatter(p["required_far_network"], y, color="#e8974e", zorder=3, s=40,
               marker="D", label="FAR required (network basis)")
    for yy, (b, bo) in enumerate(zip(p["far_base"], p["far_bonus"])):
        if pd.notna(b):
            ax.plot([b, b], [yy - 0.35, yy + 0.35], color="#141414", lw=2)
        if pd.notna(bo):
            ax.plot([bo, bo], [yy - 0.35, yy + 0.35], color="#141414", lw=2,
                    ls=":")
    ax.plot([], [], color="#141414", lw=2, label="zoned max FAR (base)")
    ax.plot([], [], color="#141414", lw=2, ls=":", label="zoned max FAR (with bonus)")
    ax.set_yticks(y)
    ax.set_yticklabels(p["zone"])
    ax.set_xlabel("Floor Area Ratio")
    ax.set_xlim(0, min(10, max(6.5, p["required_far_demand"].max() * 1.05)))
    ax.set_title("Portland: built intensity vs the intensity fiscal solvency requires "
                 "vs what Title 33 allows", fontsize=12)
    ax.legend(loc="lower right", fontsize=9)
    fig.tight_layout()
    OUT_FIG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_FIG, dpi=170, bbox_inches="tight")
    print(f"\nwrote {OUT_CSV} and {OUT_FIG}")


if __name__ == "__main__":
    main()
