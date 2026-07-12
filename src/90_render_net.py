#!/usr/bin/env python3
"""
90_render_net.py  --  "Revenues & Costs Per Acre" render, Portland OR
(Urban3/Annapolis style), from the Frame A cost allocation.

Default view: A2 coverage net (city property tax minus allocated share of the
full GF+FPDR pool) on the DEMAND basis. Height = |net $ per acre| aggregated to
a 350 ft grid (value-faithful denominator: sum(net)/sum(parcel acres));
color = black ramp for net-positive, orange/red ramp for net-negative; inset
pie = share of land area net-positive vs net-negative.

Run:  conda run -n vpa python src/90_render_net.py [column]
      column defaults to net_a2_demand; e.g. net_a2_network for the
      network-basis variant.
Output: outputs/figures/revenues_costs_3d.png (or _<column>.png for variants)
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

SRC = "data/processed/net_city.geojson"
ROADS = "data/interim/freeways.geojson"
CITY = "data/interim/city_limits_lines.geojson"
EPSG = 2913
CELL = 350.0
MAX_HEIGHT = 9000.0
CLIP_Q = 0.975


def hex2rgb(h):
    return np.array([int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)])


def ramp(c0, c1, t):
    a, b = hex2rgb(c0), hex2rgb(c1)
    return tuple(a + (b - a) * t)


def main():
    col = sys.argv[1] if len(sys.argv) > 1 else "net_a2_demand"
    out = Path("outputs/figures/revenues_costs_3d.png" if col == "net_a2_demand"
               else f"outputs/figures/revenues_costs_3d_{col}.png")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from mpl_toolkits.mplot3d.art3d import Line3DCollection

    g = gpd.read_file(SRC).to_crs(EPSG)
    g["net"] = pd.to_numeric(g[col], errors="coerce").fillna(0)
    g["acres"] = pd.to_numeric(g["acres"], errors="coerce").fillna(0)
    g = g[g.geometry.notna() & ~g.geometry.is_empty]
    cen = g.geometry.centroid
    x, y = cen.x.to_numpy(), cen.y.to_numpy()
    xmin, xmax, ymin, ymax = x.min(), x.max(), y.min(), y.max()
    nx = int((xmax - xmin) / CELL) + 1
    ny = int((ymax - ymin) / CELL) + 1
    rng = [[xmin, xmax], [ymin, ymax]]
    Hnet, _, _ = np.histogram2d(x, y, bins=[nx, ny], range=rng,
                                weights=g["net"].to_numpy())
    Hac, _, _ = np.histogram2d(x, y, bins=[nx, ny], range=rng,
                               weights=g["acres"].to_numpy())
    with np.errstate(divide="ignore", invalid="ignore"):
        npa = np.where(Hac > 0.01, Hnet / Hac, 0)

    nz = np.abs(npa[npa != 0])
    cap = float(np.quantile(nz, CLIP_Q)) if len(nz) else 1.0
    xi, yi = np.nonzero(npa != 0)
    vals = npa[xi, yi]
    t = np.clip(np.abs(vals) / cap, 0.06, 1.0)
    heights = t * MAX_HEIGHT
    colors = [ramp("#d9d9d9", "#141414", tt) if v > 0
              else ramp("#fdd0a2", "#8c2d04", tt) for v, tt in zip(vals, t)]
    xpos = xmin + xi * CELL
    ypos = ymin + yi * CELL
    order = np.argsort(heights)

    fig = plt.figure(figsize=(14, 10))
    ax = fig.add_subplot(111, projection="3d", computed_zorder=False)
    fig.patch.set_facecolor("white")
    for path, color, lw in ((CITY, "#9aa39a", 0.7), (ROADS, "#c4c8c4", 1.1)):
        try:
            lyr = gpd.read_file(path).to_crs(EPSG)
            segs = []
            for geom in lyr.geometry:
                lines = geom.geoms if geom.geom_type == "MultiLineString" else [geom]
                for ln in lines:
                    cc = np.asarray(ln.coords)
                    if len(cc) >= 2:
                        segs.append([(p[0], p[1], 0) for p in cc])
            ax.add_collection3d(Line3DCollection(segs, colors=color, linewidths=lw))
        except Exception as e:
            print(f"ground layer {path} skipped:", e)

    ax.bar3d(xpos[order], ypos[order], np.zeros(len(order)), CELL, CELL,
             heights[order], color=[colors[i] for i in order],
             shade=True, linewidth=0)
    ax.set_xlim(xmin, xmax); ax.set_ylim(ymin, ymax); ax.set_zlim(0, MAX_HEIGHT)
    ax.set_box_aspect((1, (ymax - ymin) / (xmax - xmin), 0.45))
    ax.view_init(elev=40, azim=-60)
    ax.set_axis_off()

    basis = "demand basis (units + non-res sqft)" if "demand" in col \
        else "network basis (city infrastructure feet)"
    frame = "A2 coverage" if "a2" in col else "A1 redistribution"
    fig.text(0.06, 0.94, "Revenues & Costs Per Acre", fontsize=20,
             weight="bold", color="#222")
    fig.text(0.06, 0.905, f"Portland, OR — city property tax vs tax-supported "
             f"services · {frame}, {basis}", fontsize=11, color="#555")

    pos_a = float(g.loc[(g["net"] > 0) & (g["acres"] > 0), "acres"].sum())
    neg_a = float(g.loc[(g["net"] <= 0) & (g["acres"] > 0), "acres"].sum())
    pax = fig.add_axes([0.055, 0.45, 0.16, 0.16])
    pax.pie([neg_a, pos_a], colors=["#e8703a", "#3a3a3a"],
            labels=[f"{100*neg_a/(neg_a+pos_a):.0f}%",
                    f"{100*pos_a/(neg_a+pos_a):.0f}%"],
            textprops={"fontsize": 10}, startangle=90)
    pax.set_title("Land area", fontsize=10, color="#333")

    handles = [Patch(facecolor="#141414", label="Net positive / acre — most"),
               Patch(facecolor="#b8b8b8", label="Net positive / acre — least"),
               Patch(facecolor="#fdd0a2", label="Net negative / acre — least"),
               Patch(facecolor="#8c2d04", label="Net negative / acre — most")]
    leg = ax.legend(handles=handles, loc="upper left",
                    bbox_to_anchor=(0.0, 0.40), fontsize=8.5, frameon=True)
    leg.get_frame().set_edgecolor("#cccccc")
    fig.text(0.93, 0.03, "height = |net $ per acre| · Data: Metro RLIS (ODbL), "
             "FY2025-26 Adopted Budget, county assessors",
             fontsize=8, color="#888", ha="right")

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=170, bbox_inches="tight", facecolor="white")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
