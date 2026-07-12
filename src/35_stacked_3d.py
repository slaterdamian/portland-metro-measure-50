#!/usr/bin/env python3
"""
35_stacked_3d.py  --  Interactive stacked AV/RMV map, Portland OR.

Every parcel's ACTUAL FOOTPRINT is extruded twice on a shared $-per-meter scale:

  * SOLID column   = Measure-50 assessed value per acre (the taxed base),
                     Urban3 classed color.
  * GHOST top      = real market value per acre -- the half-transparent
                     (alpha 120) extension above the solid bar is the value
                     Measure 50 leaves untaxed.

Output is a hand-rolled deck.gl page (not pydeck): the parcel GeoJSON is written
ONCE as an external file and shared by both layers (pydeck inlines the data per
layer, which ballooned to 400 MB for 192k parcels). Z-fighting between the
coincident walls is handled with a polygon offset on the ghost layer instead of
buffered duplicate geometry. Basemap: OpenStreetMap raster tiles via TileLayer
((c) OpenStreetMap contributors). Needs internet for tiles + deck.gl CDN.

Run:  conda run -n vpa python src/35_stacked_3d.py
Outputs:
  outputs/figures/value_stack_3d.html      open in a browser (serve the folder)
  outputs/figures/value_stack_data.geojson data payload fetched by the page
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

SRC = Path("data/processed/taxlots_value_per_acre.geojson")
OUT_HTML = Path("outputs/figures/value_stack_3d.html")
OUT_DATA = Path("outputs/figures/value_stack_data.geojson")

MIN_ACRES = 0.01
CLIP_Q = 0.995
MAX_M = 4200.0
GHOST_ALPHA = 120     # half-transparent untaxed top (per review feedback)
SIMPLIFY_FT = 6.0

BREAKS = [0, 250e3, 500e3, 1e6, 1.5e6, 2e6, 2.5e6, 5e6, 7.5e6, 10e6, 15e6, 20e6, np.inf]
HEX = ["#9e9e9e", "#1b5e20", "#388e3c", "#4caf50", "#8bc34a", "#c5e1a5",
       "#ffffbf", "#fdae61", "#f46d43", "#d7301f", "#b30000", "#7f0000", "#54278f"]
RGB = [[int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)] for h in HEX]

TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Portland — taxed vs untaxed value per acre</title>
<script src="https://unpkg.com/deck.gl@9.0.34/dist.min.js"></script>
<style>html,body{margin:0;height:100%}#app{width:100%;height:100%;position:relative}
#legend{position:absolute;bottom:14px;left:14px;background:rgba(255,255,255,.92);
padding:10px 12px;font:12px sans-serif;border-radius:6px;z-index:1;max-width:270px}
</style></head><body><div id="app"></div>
<div id="legend"><b>Taxable value per acre</b> — solid bar = Measure-50 assessed
(taxed) value; faded top = real market value left untaxed. Color = assessed $/acre
(Urban3 classes, green low &rarr; red/purple high).<br/>
<i>Data: Metro RLIS (ODbL); basemap &copy; OpenStreetMap contributors</i></div>
<script>
const deckgl = new deck.DeckGL({
  container: 'app',
  initialViewState: {latitude: __LAT__, longitude: __LON__, zoom: 11.6, pitch: 55, bearing: -15},
  controller: true,
  getTooltip: ({object}) => object && {html:
    `Assessed (taxed): <b>${object.properties.v}</b><br/>` +
    `Market: <b>${object.properties.w}</b><br/>` +
    `Taxed share: <b>${object.properties.p}%</b>`},
  layers: []
});
const osm = new deck.TileLayer({
  id: 'osm', data: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
  minZoom: 0, maxZoom: 19, tileSize: 256,
  renderSubLayers: p => new deck.BitmapLayer(p, {
    data: null, image: p.data,
    bounds: [p.tile.boundingBox[0][0], p.tile.boundingBox[0][1],
             p.tile.boundingBox[1][0], p.tile.boundingBox[1][1]]})
});
fetch('value_stack_data.geojson').then(r => r.json()).then(data => {
  const solid = new deck.GeoJsonLayer({
    id: 'solid', data, extruded: true, pickable: true, wireframe: false,
    getElevation: f => f.properties.a,
    getFillColor: f => [f.properties.r, f.properties.g, f.properties.b, 255],
    getLineColor: [0, 0, 0, 0]});
  const ghost = new deck.GeoJsonLayer({
    id: 'ghost', data, extruded: true, pickable: false, wireframe: false,
    getElevation: f => f.properties.m,
    getFillColor: f => [f.properties.r, f.properties.g, f.properties.b, __GA__],
    getLineColor: [0, 0, 0, 0],
    parameters: {depthMask: false},
    getPolygonOffset: () => [0, -600]});
  deckgl.setProps({layers: [osm, solid, ghost]});
});
</script></body></html>
"""


def main():
    g = gpd.read_file(SRC).to_crs(2913)
    for c in ("av", "rmv", "acres", "assessed_value_per_acre", "rmv_per_acre"):
        g[c] = pd.to_numeric(g[c], errors="coerce")
    g = g[(g["assessed_value_per_acre"] > 0) & (g["acres"] >= MIN_ACRES)]
    g = g[g.geometry.notna() & ~g.geometry.is_empty].copy()
    g["geometry"] = g.geometry.make_valid().simplify(SIMPLIFY_FT)

    g["rmvpa"] = np.maximum(g["rmv_per_acre"].fillna(0), g["assessed_value_per_acre"])
    cap = float(np.quantile(g["rmvpa"], CLIP_Q))
    scale = MAX_M / cap
    g["a"] = (np.minimum(g["assessed_value_per_acre"], cap) * scale).round(0).astype(int)
    g["m"] = (np.minimum(g["rmvpa"], cap) * scale).round(0).astype(int)
    g["p"] = (100 * g["assessed_value_per_acre"] / g["rmvpa"]).round(0).astype(int)
    cls = np.digitize(g["assessed_value_per_acre"].to_numpy(), BREAKS[1:-1], right=True)
    g["r"] = [RGB[k][0] for k in cls]
    g["g"] = [RGB[k][1] for k in cls]
    g["b"] = [RGB[k][2] for k in cls]
    g["v"] = (g["assessed_value_per_acre"] / 1000).round(0).map("${:,.0f}k/ac".format)
    g["w"] = (g["rmvpa"] / 1000).round(0).map("${:,.0f}k/ac".format)
    print(f"parcels: {len(g):,}  clip ${cap:,.0f}/ac  "
          f"median taxed share {g['p'].median():.0f}%")

    out = g[["a", "m", "p", "r", "g", "b", "v", "w", "geometry"]].to_crs(4326)
    out["geometry"] = shapely.set_precision(out.geometry.values, 1e-6)
    out = out[~out.geometry.is_empty]
    cen = out.geometry.union_all().centroid

    OUT_DATA.parent.mkdir(parents=True, exist_ok=True)
    fc = json.loads(out.to_json())
    json.dump(fc, open(OUT_DATA, "w", encoding="utf-8"), separators=(",", ":"))

    html = (TEMPLATE.replace("__LAT__", f"{cen.y:.5f}")
            .replace("__LON__", f"{cen.x:.5f}")
            .replace("__GA__", str(GHOST_ALPHA)))
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"wrote {OUT_HTML} + data {OUT_DATA.stat().st_size/1e6:.0f} MB")


if __name__ == "__main__":
    main()
