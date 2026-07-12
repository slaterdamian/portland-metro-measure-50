#!/usr/bin/env python3
"""
30_render_3d.py  --  Urban3-style 3D "Taxable Value Per Acre" render, Portland OR.

Portland has ~186k renderable parcels -- too many for per-parcel matplotlib
extrusion -- so parcels are aggregated to a fine grid with the value-faithful
denominator:  cell value-per-acre = sum(AV) / sum(parcel acres in cell)
(350 ft cells; dividing by full cell area would dilute the peaks).

Height and color both encode assessed value per acre on the Urban3
green->yellow->orange->red->purple classification, over a light basemap
(city-limit lines + freeways).

Run:  conda run -n vpa python src/30_render_3d.py
Output: outputs/figures/value_per_acre_3d_render.png
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

SRC = "data/processed/taxlots_value_per_acre.geojson"
ROADS = "data/interim/freeways.geojson"
CITY = "data/interim/city_limits_lines.geojson"
OUT = Path("outputs/figures/value_per_acre_3d_render.png")
EPSG = 2913            # Oregon State Plane North, ft
CELL = 350.0           # ft
MAX_HEIGHT = 16000.0   # ft at the clipped maximum
MIN_ACRES = 0.005      # drop extreme sliver artifacts pre-aggregation
CLIP_Q = 0.995         # display clip for the sliver/supertall tail

BREAKS = [0, 250e3, 500e3, 1e6, 1.5e6, 2e6, 2.5e6, 5e6, 7.5e6, 10e6, 15e6, 20e6, np.inf]
COLORS = ["#9e9e9e", "#1b5e20", "#388e3c", "#4caf50", "#8bc34a", "#c5e1a5",
          "#ffffbf", "#fdae61", "#f46d43", "#d7301f", "#b30000", "#7f0000", "#54278f"]
LABELS = ["0", "< 250,000", "250,001 - 500,000", "500,001 - 1,000,000",
          "1,000,001 - 1,500,000", "1,500,001 - 2,000,000", "2,000,001 - 2,500,000",
          "2,500,001 - 5,000,000", "5,000,001 - 7,500,000", "7,500,001 - 10,000,000",
          "10,000,001 - 15,000,000", "15,000,001 - 20,000,000", "> 20,000,000"]


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    from mpl_toolkits.mplot3d.art3d import Line3DCollection

    g = gpd.read_file(SRC).to_crs(EPSG)
    g["av"] = pd.to_numeric(g["av"], errors="coerce").fillna(0)
    g["acres"] = pd.to_numeric(g["acres"], errors="coerce").fillna(0)
    g = g[(g["av"] > 0) & (g["acres"] >= MIN_ACRES)]
    g = g[g.geometry.notna() & ~g.geometry.is_empty]
    cen = g.geometry.centroid
    x, y = cen.x.to_numpy(), cen.y.to_numpy()
    xmin, xmax, ymin, ymax = x.min(), x.max(), y.min(), y.max()

    nx = int((xmax - xmin) / CELL) + 1
    ny = int((ymax - ymin) / CELL) + 1
    rng = [[xmin, xmax], [ymin, ymax]]
    Hav, _, _ = np.histogram2d(x, y, bins=[nx, ny], range=rng,
                               weights=g["av"].to_numpy())
    Hac, _, _ = np.histogram2d(x, y, bins=[nx, ny], range=rng,
                               weights=g["acres"].to_numpy())
    with np.errstate(divide="ignore", invalid="ignore"):
        vpa = np.where(Hac > 0.01, Hav / Hac, 0)

    vals = vpa[vpa > 0]
    cap = float(np.quantile(vals, CLIP_Q))
    print(f"cells: {len(vals):,}  max ${vals.max():,.0f}/ac  clip ${cap:,.0f}")
    xi, yi = np.nonzero(vpa > 0)
    v = vpa[xi, yi]
    heights = np.minimum(v, cap) / cap * MAX_HEIGHT
    cls = np.digitize(v, BREAKS[1:-1], right=True)
    cols = np.array(COLORS)[cls]
    xpos = xmin + xi * CELL
    ypos = ymin + yi * CELL
    order = np.argsort(heights)

    fig = plt.figure(figsize=(14, 10))
    ax = fig.add_subplot(111, projection="3d", computed_zorder=False)
    fig.patch.set_facecolor("white")

    for path, color, lw in ((CITY, "#9aa39a", 0.7), (ROADS, "#b8bdb8", 1.1)):
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
             heights[order], color=cols[order], shade=True, linewidth=0)
    ax.set_xlim(xmin, xmax); ax.set_ylim(ymin, ymax); ax.set_zlim(0, MAX_HEIGHT)
    ax.set_box_aspect((1, (ymax - ymin) / (xmax - xmin), 0.5))
    ax.view_init(elev=40, azim=-60)
    ax.set_axis_off()

    fig.text(0.06, 0.94, "Taxable Value Per Acre", fontsize=20, weight="bold",
             color="#222")
    fig.text(0.06, 0.905, "Portland, OR — Measure 50 assessed value",
             fontsize=12, color="#555")
    handles = [Patch(facecolor=COLORS[i], label=LABELS[i])
               for i in range(len(LABELS) - 1, -1, -1)]
    leg = ax.legend(handles=handles, title="Taxable Value\nPer Acre ($)",
                    loc="upper left", bbox_to_anchor=(0.0, 0.85),
                    fontsize=7.5, title_fontsize=9, frameon=True, borderpad=0.8)
    leg.get_frame().set_edgecolor("#cccccc")
    fig.text(0.93, 0.03,
             "Source: Metro RLIS Discovery (ODbL); values from county assessors",
             fontsize=8, color="#888", ha="right")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=170, bbox_inches="tight", facecolor="white")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
