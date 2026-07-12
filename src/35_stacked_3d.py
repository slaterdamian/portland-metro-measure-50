#!/usr/bin/env python3
"""
35_stacked_3d.py  --  Interactive parcel map, Portland OR: two modes in one page.

  VALUE mode (default)  stacked AV/RMV: solid column = Measure-50 assessed value
                        per acre (Urban3 classed color); ghost top = real market
                        value left untaxed (alpha 24, thin black wireframe edges
                        so the transparent portion reads).
  NET mode (toggle)     Annapolis-style "Revenues & Costs Per Acre": height =
                        |net $ per acre| (city property tax minus allocated
                        tax-supported services, Frame A2 demand basis, stage 80);
                        black ramp = net positive, orange/red = net negative.

A button in the top-right switches modes; the legend and tooltip follow.

Architecture: hand-rolled deck.gl page; ONE external GeoJSON payload shared by
all layers (pydeck's per-layer inlining hit 400 MB). Ghost z-fighting handled by
polygon offset. Basemap: OpenStreetMap raster tiles ((c) OpenStreetMap
contributors). Needs internet for tiles + deck.gl CDN; serve the folder locally.

Run:  conda run -n vpa python src/35_stacked_3d.py
Outputs:
  outputs/figures/value_stack_3d.html
  outputs/figures/value_stack_data.geojson
"""
from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

SRC = Path("data/processed/taxlots_value_per_acre.geojson")
NET = Path("data/processed/net_city.geojson")
OUT_HTML = Path("outputs/figures/value_stack_3d.html")
OUT_DATA = Path("outputs/figures/value_stack_data.geojson")

MIN_ACRES = 0.01
CLIP_Q = 0.995
MAX_M = 4200.0        # metres at the clipped RMV maximum (value mode)
MAX_M_NET = 3200.0    # metres at the clipped |net|/acre maximum (net mode)
NET_CLIP_Q = 0.975
GHOST_ALPHA = 24
SIMPLIFY_FT = 6.0

BREAKS = [0, 250e3, 500e3, 1e6, 1.5e6, 2e6, 2.5e6, 5e6, 7.5e6, 10e6, 15e6, 20e6, np.inf]
HEX = ["#9e9e9e", "#1b5e20", "#388e3c", "#4caf50", "#8bc34a", "#c5e1a5",
       "#ffffbf", "#fdae61", "#f46d43", "#d7301f", "#b30000", "#7f0000", "#54278f"]
RGB = [[int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)] for h in HEX]

TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Portland — value & fiscal net per acre</title>
<script src="https://unpkg.com/deck.gl@9.0.34/dist.min.js"></script>
<style>html,body{margin:0;height:100%}#app{width:100%;height:100%;position:relative}
#legend{position:absolute;bottom:14px;left:14px;background:rgba(255,255,255,.93);
padding:10px 12px;font:12px sans-serif;border-radius:6px;z-index:1;max-width:290px}
#toggle{position:absolute;top:14px;right:14px;z-index:1;font:13px sans-serif;
background:#fff;border:1px solid #999;border-radius:6px;padding:8px 14px;
cursor:pointer;box-shadow:0 1px 4px rgba(0,0,0,.25)}
#toggle:hover{background:#f0f0f0}
</style></head><body><div id="app"></div>
<button id="toggle">Show: Revenues &amp; Costs</button>
<div id="legend"></div>
<script>
const LEGEND_VALUE = `<b>Taxable value per acre</b> — solid bar = Measure-50
assessed (taxed) value; faded top (thin black edges) = real market value left
untaxed. Color = assessed $/acre (Urban3 classes, green low &rarr; red/purple
high). <b>Taxed share</b> = the percentage of a parcel's real market value (RMV)
that is actually taxed as Measure-50 assessed value (AV).<br/>
<i>Data: Metro RLIS (ODbL); basemap &copy; OpenStreetMap contributors</i>`;
const LEGEND_NET = `<b>Revenues &amp; costs per acre</b> — height = |net $ per
acre|: the parcel's City of Portland property tax minus its allocated share of
tax-supported city services (FY2025-26 General Fund + FPDR, demand basis).
<span style="color:#141414"><b>Black</b></span> = net positive,
<span style="color:#a63603"><b>orange/red</b></span> = net negative. Citywide,
property tax covers ~54% of these services — business taxes and fees fund the
rest, so net-negative land is not "freeloading."<br/>
<i>Data: Metro RLIS (ODbL), FY2025-26 Adopted Budget; basemap &copy;
OpenStreetMap contributors</i>`;

const NCAP = __NCAP__;   // $/acre at full net height/intensity
let mode = 'value';
const deckgl = new deck.DeckGL({
  container: 'app',
  initialViewState: {latitude: __LAT__, longitude: __LON__, zoom: 11.6, pitch: 55, bearing: -15},
  controller: true,
  getTooltip: ({object}) => {
    if (!object) return null;
    const p = object.properties;
    if (mode === 'value') return {html:
      `Assessed (taxed): <b>${p.t}</b> &middot; ${p.v}<br/>` +
      `Real market: <b>${p.u}</b> &middot; ${p.w}<br/>` +
      `Taxed share: <b>${p.p}%</b> of market value`};
    const s = p.nt < 0 ? '&minus;' : '+';
    const sa = p.q < 0 ? '&minus;' : '+';
    return {html:
      `City tax paid: <b>$${p.c.toLocaleString()}</b><br/>` +
      `Net vs city services: <b>${s}$${Math.abs(p.nt).toLocaleString()}</b>` +
      ` &middot; ${sa}$${Math.abs(p.q).toLocaleString()}/ac`};
  },
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
function netColor(q) {
  const t = Math.min(Math.abs(q) / NCAP, 1), f = Math.max(t, 0.08);
  if (q > 0) {  // grey -> black
    const c0 = [217, 217, 217], c1 = [20, 20, 20];
    return c0.map((v, i) => Math.round(v + (c1[i] - v) * f));
  }             // light orange -> dark red-brown
  const c0 = [253, 208, 162], c1 = [140, 45, 4];
  return c0.map((v, i) => Math.round(v + (c1[i] - v) * f));
}
let DATA = null;
function layersFor(m) {
  if (m === 'value') return [osm,
    new deck.GeoJsonLayer({id: 'solid', data: DATA, extruded: true,
      pickable: true, wireframe: false,
      getElevation: f => f.properties.a,
      getFillColor: f => [f.properties.r, f.properties.g, f.properties.b, 255],
      getLineColor: [0, 0, 0, 0]}),
    new deck.GeoJsonLayer({id: 'ghost', data: DATA, extruded: true,
      pickable: false, wireframe: true,
      getElevation: f => f.properties.m,
      getFillColor: f => [f.properties.r, f.properties.g, f.properties.b, __GA__],
      getLineColor: [0, 0, 0, 90], lineWidthMinPixels: 1,
      parameters: {depthMask: false},
      getPolygonOffset: () => [0, -600]})];
  return [osm,
    new deck.GeoJsonLayer({id: 'net', data: DATA, extruded: true,
      pickable: true, wireframe: false,
      getElevation: f => Math.min(Math.abs(f.properties.q) / NCAP, 1) * __MAXNET__,
      getFillColor: f => netColor(f.properties.q),
      getLineColor: [0, 0, 0, 0]})];
}
function render() {
  document.getElementById('legend').innerHTML =
    mode === 'value' ? LEGEND_VALUE : LEGEND_NET;
  document.getElementById('toggle').innerHTML =
    mode === 'value' ? 'Show: Revenues &amp; Costs' : 'Show: Taxable Value';
  deckgl.setProps({layers: layersFor(mode)});
}
document.getElementById('toggle').onclick = () => {
  mode = mode === 'value' ? 'net' : 'value';
  render();
};
fetch('value_stack_data.geojson').then(r => r.json()).then(data => {
  DATA = data;
  render();
});
</script></body></html>
"""


def money(x):
    if x >= 1e9:
        return f"${x/1e9:.2f}B"
    if x >= 1e6:
        return f"${x/1e6:.2f}M"
    return f"${x/1e3:,.0f}k"


def main():
    g = gpd.read_file(SRC).to_crs(2913)
    for c in ("av", "rmv", "acres", "assessed_value_per_acre", "rmv_per_acre"):
        g[c] = pd.to_numeric(g[c], errors="coerce")
    g = g[(g["assessed_value_per_acre"] > 0) & (g["acres"] >= MIN_ACRES)]
    g = g[g.geometry.notna() & ~g.geometry.is_empty].copy()
    g["geometry"] = g.geometry.make_valid().simplify(SIMPLIFY_FT)

    # ---- net fields from the Frame A allocation (stage 80) --------------------
    n = gpd.read_file(NET, ignore_geometry=True,
                      columns=["TLID", "city_tax", "net_a2_demand"])
    n["tl"] = n["TLID"].astype(str).str.replace(" ", "", regex=False).str.upper()
    n = n.drop_duplicates("tl").set_index("tl")
    g["tl"] = g["TLID"].astype(str).str.replace(" ", "", regex=False).str.upper()
    g["city_tax"] = g["tl"].map(n["city_tax"]).fillna(0)
    g["net"] = g["tl"].map(n["net_a2_demand"]).fillna(0)
    g["q"] = np.where(g["acres"] > 0, g["net"] / g["acres"], 0).round(0).astype(int)
    g["nt"] = g["net"].round(0).astype(int)
    g["c"] = g["city_tax"].round(0).astype(int)
    ncap = float(np.quantile(np.abs(g.loc[g["q"] != 0, "q"]), NET_CLIP_Q))

    # ---- value-mode fields -----------------------------------------------------
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
    g["t"] = g["av"].map(money)
    g["u"] = np.maximum(g["rmv"].fillna(0), g["av"]).map(money)
    print(f"parcels: {len(g):,}  value clip ${cap:,.0f}/ac  net clip ${ncap:,.0f}/ac  "
          f"median taxed share {g['p'].median():.0f}%")

    out = g[["a", "m", "p", "r", "g", "b", "v", "w", "t", "u",
             "q", "nt", "c", "geometry"]].to_crs(4326)
    out["geometry"] = shapely.set_precision(out.geometry.values, 1e-6)
    out = out[~out.geometry.is_empty]
    cen = out.geometry.union_all().centroid

    OUT_DATA.parent.mkdir(parents=True, exist_ok=True)
    fc = json.loads(out.to_json())
    json.dump(fc, open(OUT_DATA, "w", encoding="utf-8"), separators=(",", ":"))

    html = (TEMPLATE.replace("__LAT__", f"{cen.y:.5f}")
            .replace("__LON__", f"{cen.x:.5f}")
            .replace("__GA__", str(GHOST_ALPHA))
            .replace("__NCAP__", f"{ncap:.0f}")
            .replace("__MAXNET__", f"{MAX_M_NET:.0f}"))
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"wrote {OUT_HTML} + data {OUT_DATA.stat().st_size/1e6:.0f} MB")


if __name__ == "__main__":
    main()
