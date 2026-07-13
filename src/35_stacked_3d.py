#!/usr/bin/env python3
"""
35_stacked_3d.py  --  Interactive parcel map, Portland OR: three modes, one page.

  VALUE (default)   stacked AV/RMV: solid column = Measure-50 assessed value per
                    acre (Urban3 classed color); ghost top = real market value
                    left untaxed (alpha 24, opaque black wireframe edges).
  NET               Annapolis-style Revenues & Costs per acre (Frame A2 demand
                    basis, stage 80): black = net positive, orange = negative.
  SHARE-ADJUSTED    controls for the citywide 54.1% property-tax funding mix
                    (A1 redistribution net): orange = relative freeloaders.

Interactions:
  * top-right button cycles the three modes
  * CLICK a bar to lock a selection -- all other bars fade, a detail panel shows
    the address and full value/tax/net figures; the lock persists across mode
    switches so one parcel can be compared in all three views. Click empty
    ground (or the panel's x) to clear.
  * SEARCH box (top-left): parcel addresses are matched locally first; anything
    else (landmarks, intersections) falls through to OSM Nominatim geocoding,
    bounded to the Portland area.

Architecture: hand-rolled deck.gl page; ONE external GeoJSON payload shared by
all layers. Ghost z-fighting handled by polygon offset. Basemap: OpenStreetMap
raster tiles ((c) OpenStreetMap contributors; search (c) Nominatim/OSM).
Needs internet for tiles + deck.gl CDN; serve the folder locally.

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
MAX_M = 4200.0
MAX_M_NET = 3200.0
NET_CLIP_Q = 0.975
GHOST_ALPHA = 24
SIMPLIFY_FT = 6.0

BREAKS = [0, 250e3, 500e3, 1e6, 1.5e6, 2e6, 2.5e6, 5e6, 7.5e6, 10e6, 15e6, 20e6, np.inf]
HEX = ["#9e9e9e", "#1b5e20", "#388e3c", "#4caf50", "#8bc34a", "#c5e1a5",
       "#ffffbf", "#fdae61", "#f46d43", "#d7301f", "#b30000", "#7f0000", "#54278f"]
RGB = [[int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)] for h in HEX]

TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Portland Metro &amp; Measure 50</title>
<script src="https://unpkg.com/deck.gl@9.0.34/dist.min.js"></script>
<style>html,body{margin:0;height:100%}#app{width:100%;height:100%;position:relative}
#legend{position:absolute;bottom:14px;left:14px;background:rgba(255,255,255,.93);
padding:10px 12px;font:12px sans-serif;border-radius:6px;z-index:1;max-width:290px}
#toggle{position:absolute;top:14px;right:14px;z-index:1;font:13px sans-serif;
background:#fff;border:1px solid #999;border-radius:6px;padding:8px 14px;
cursor:pointer;box-shadow:0 1px 4px rgba(0,0,0,.25)}
#toggle:hover{background:#f0f0f0}
#searchwrap{position:absolute;top:14px;left:14px;z-index:2}
#search{width:260px;font:13px sans-serif;padding:8px 10px;border:1px solid #999;
border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.25)}
#panel{position:absolute;top:56px;left:14px;z-index:2;background:rgba(255,255,255,.96);
border:1px solid #888;border-radius:6px;padding:10px 12px;font:12px sans-serif;
max-width:280px;display:none;box-shadow:0 1px 6px rgba(0,0,0,.3)}
#panel .x{float:right;cursor:pointer;font-weight:bold;padding:0 4px;color:#666}
#panel .x:hover{color:#000}
#panel h4{margin:0 22px 6px 0;font-size:13px}
#panel td{padding:1px 6px 1px 0;vertical-align:top}
</style></head><body><div id="app"></div>
<div id="searchwrap"><input id="search"
  placeholder="Search address or landmark&hellip;" /></div>
<div id="panel"></div>
<button id="toggle">Show: Revenues &amp; Costs</button>
<div id="legend"></div>
<script>
const LEGEND_VALUE = `<b>Taxable value per acre</b> — solid bar = Measure-50
assessed (taxed) value; faded top (black edges) = real market value left
untaxed. Color = assessed $/acre (Urban3 classes, green low &rarr; red/purple
high). <b>Taxed share</b> = the percentage of a parcel's real market value (RMV)
that is actually taxed as Measure-50 assessed value (AV).<br/>
<i>Data: Metro RLIS (ODbL); basemap &copy; OpenStreetMap contributors;
search &copy; Nominatim/OSM</i>`;
const LEGEND_NET = `<b>Revenues &amp; costs per acre</b> — height = |net $ per
acre|: the parcel's City of Portland property tax minus its allocated share of
tax-supported city services (FY2025-26 General Fund + FPDR, demand basis).
<span style="color:#141414"><b>Black</b></span> = net positive,
<span style="color:#a63603"><b>orange/red</b></span> = net negative. Citywide,
property tax covers ~54% of these services — business taxes and fees fund the
rest, so net-negative here is not automatically "freeloading" (see the
share-adjusted view).<br/>
<i>Data: Metro RLIS (ODbL), FY2025-26 Adopted Budget; basemap &copy;
OpenStreetMap contributors; search &copy; Nominatim/OSM</i>`;
const LEGEND_CARRY = `<b>Share-adjusted net per acre</b> &mdash; controls for the
citywide funding mix: property tax covers 54.1% of tax-supported city services
overall, so a parcel &quot;carries its share&quot; when its own tax covers at
least 54.1% of its allocated cost. <span style="color:#141414"><b>Black</b></span>
= carries MORE than its proportional share;
<span style="color:#a63603"><b>orange/red</b></span> = carries less &mdash; the
relative freeloaders, with the 54% gap controlled for. Height =
|share-adjusted net $ per acre|.<br/>
<i>Data: Metro RLIS (ODbL), FY2025-26 Adopted Budget; basemap &copy;
OpenStreetMap contributors; search &copy; Nominatim/OSM</i>`;

const NCAP = __NCAP__;
const NCAP2 = __NCAP2__;
const MODES = ['value', 'net', 'carry'];
const MODE_LABEL = {value: 'Taxable Value', net: 'Revenues & Costs',
                    carry: 'Share-Adjusted Net'};
let mode = 'value';
let selectedI = -1;
let selectedProps = null;
let DATA = null;

const deckgl = new deck.DeckGL({
  container: 'app',
  initialViewState: {latitude: __LAT__, longitude: __LON__, zoom: 11.6, pitch: 55, bearing: -15},
  controller: true,
  onClick: info => { info.object ? select(info.object.properties) : deselect(); },
  getTooltip: ({object}) => {
    if (!object) return null;
    const p = object.properties;
    if (mode === 'value') return {html:
      `<b>${p.s || 'no address'}</b><br/>` +
      `Assessed (taxed): <b>${p.t}</b> &middot; ${p.v}<br/>` +
      `Real market: <b>${p.u}</b> &middot; ${p.w}<br/>` +
      `Taxed share: <b>${p.p}%</b> of market value`};
    const tot = mode === 'net' ? p.nt : p.n2;
    const pa = mode === 'net' ? p.q : p.q2;
    const s = tot < 0 ? '&minus;' : '+';
    const sa = pa < 0 ? '&minus;' : '+';
    const label = mode === 'net' ? 'Net vs city services' : 'Share-adjusted net';
    return {html:
      `<b>${p.s || 'no address'}</b><br/>` +
      `Assessed (taxed): <b>${p.t}</b> &middot; Market: <b>${p.u}</b><br/>` +
      `City tax paid: <b>$${p.c.toLocaleString()}</b><br/>` +
      `${label}: <b>${s}$${Math.abs(tot).toLocaleString()}</b>` +
      ` &middot; ${sa}$${Math.abs(pa).toLocaleString()}/ac`};
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
function netColor(q, cap, alpha) {
  const t = Math.min(Math.abs(q) / cap, 1), f = Math.max(t, 0.08);
  const [c0, c1] = q > 0 ? [[217, 217, 217], [20, 20, 20]]
                         : [[253, 208, 162], [140, 45, 4]];
  const rgb = c0.map((v, i) => Math.round(v + (c1[i] - v) * f));
  return [rgb[0], rgb[1], rgb[2], alpha];
}
function fadeAlpha(f, full, dim) {
  return (selectedI < 0 || f.properties.i === selectedI) ? full : dim;
}
function layersFor(m) {
  const trig = {getFillColor: [selectedI, m], getLineColor: [selectedI, m]};
  if (m === 'value') return [osm,
    new deck.GeoJsonLayer({id: 'solid', data: DATA, extruded: true,
      pickable: true, wireframe: false,
      getElevation: f => f.properties.a,
      getFillColor: f => [f.properties.r, f.properties.g, f.properties.b,
                          fadeAlpha(f, 255, 60)],
      getLineColor: [0, 0, 0, 0], updateTriggers: trig}),
    new deck.GeoJsonLayer({id: 'ghost', data: DATA, extruded: true,
      pickable: false, wireframe: true,
      getElevation: f => f.properties.m,
      getFillColor: f => [f.properties.r, f.properties.g, f.properties.b,
                          fadeAlpha(f, __GA__, 5)],
      getLineColor: f => [0, 0, 0, fadeAlpha(f, 255, 35)],
      lineWidthMinPixels: 1,
      parameters: {depthMask: false},
      getPolygonOffset: () => [0, -600], updateTriggers: trig})];
  const field = m === 'net' ? 'q' : 'q2';
  const cap = m === 'net' ? NCAP : NCAP2;
  return [osm,
    new deck.GeoJsonLayer({id: 'net-' + m, data: DATA, extruded: true,
      pickable: true, wireframe: false,
      getElevation: f => Math.min(Math.abs(f.properties[field]) / cap, 1) * __MAXNET__,
      getFillColor: f => netColor(f.properties[field], cap, fadeAlpha(f, 255, 55)),
      getLineColor: [0, 0, 0, 0], updateTriggers: trig})];
}
function panel() {
  const el = document.getElementById('panel');
  if (!selectedProps) { el.style.display = 'none'; return; }
  const p = selectedProps;
  const sN = p.nt < 0 ? '&minus;' : '+', sQ = p.q < 0 ? '&minus;' : '+';
  const sN2 = p.n2 < 0 ? '&minus;' : '+', sQ2 = p.q2 < 0 ? '&minus;' : '+';
  el.innerHTML =
    `<span class="x" onclick="deselect()">&times;</span>` +
    `<h4>${p.s || '(no address on record)'}</h4><table>` +
    `<tr><td>Assessed (taxed)</td><td><b>${p.t}</b> &middot; ${p.v}</td></tr>` +
    `<tr><td>Real market</td><td><b>${p.u}</b> &middot; ${p.w}</td></tr>` +
    `<tr><td>Taxed share</td><td><b>${p.p}%</b> of market</td></tr>` +
    `<tr><td>City tax paid</td><td><b>$${p.c.toLocaleString()}</b>/yr</td></tr>` +
    `<tr><td>Net vs services</td><td><b>${sN}$${Math.abs(p.nt).toLocaleString()}</b>` +
    ` &middot; ${sQ}$${Math.abs(p.q).toLocaleString()}/ac</td></tr>` +
    `<tr><td>Share-adjusted</td><td><b>${sN2}$${Math.abs(p.n2).toLocaleString()}</b>` +
    ` &middot; ${sQ2}$${Math.abs(p.q2).toLocaleString()}/ac</td></tr></table>` +
    `<i style="color:#777">Selection locked — switch views to compare.</i>`;
  el.style.display = 'block';
}
function select(props) { selectedI = props.i; selectedProps = props; panel(); render(); }
function deselect() { selectedI = -1; selectedProps = null; panel(); render(); }
function flyTo(lon, lat, zoom) {
  deckgl.setProps({initialViewState: {longitude: lon, latitude: lat, zoom: zoom,
    pitch: 55, bearing: -15, transitionDuration: 900}});
}
function render() {
  const LEGENDS = {value: LEGEND_VALUE, net: LEGEND_NET, carry: LEGEND_CARRY};
  document.getElementById('legend').innerHTML = LEGENDS[mode];
  const next = MODES[(MODES.indexOf(mode) + 1) % MODES.length];
  document.getElementById('toggle').innerHTML = 'Show: ' + MODE_LABEL[next];
  deckgl.setProps({layers: layersFor(mode)});
}
document.getElementById('toggle').onclick = () => {
  mode = MODES[(MODES.indexOf(mode) + 1) % MODES.length];
  render();
};
document.getElementById('search').addEventListener('keydown', e => {
  if (e.key !== 'Enter') return;
  const q = e.target.value.trim();
  if (!q || !DATA) return;
  const qn = q.toUpperCase();
  const hit = DATA.features.find(f =>
    f.properties.s && f.properties.s.toUpperCase().startsWith(qn)) ||
    DATA.features.find(f =>
    f.properties.s && f.properties.s.toUpperCase().includes(qn));
  if (hit) {
    select(hit.properties);
    flyTo(hit.properties.x, hit.properties.y, 16);
    return;
  }
  fetch('https://nominatim.openstreetmap.org/search?format=json&limit=1' +
        '&viewbox=-122.85,45.66,-122.44,45.42&bounded=1&q=' +
        encodeURIComponent(q))
    .then(r => r.json()).then(res => {
      if (res.length) flyTo(parseFloat(res[0].lon), parseFloat(res[0].lat), 15.5);
      else e.target.style.borderColor = '#c0392b';
    }).catch(() => {});
});
document.getElementById('search').addEventListener('input',
  e => { e.target.style.borderColor = '#999'; });
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

    n = gpd.read_file(NET, ignore_geometry=True,
                      columns=["TLID", "city_tax", "net_a2_demand", "net_a1_demand"])
    n["tl"] = n["TLID"].astype(str).str.replace(" ", "", regex=False).str.upper()
    n = n.drop_duplicates("tl").set_index("tl")
    g["tl"] = g["TLID"].astype(str).str.replace(" ", "", regex=False).str.upper()
    g["city_tax"] = g["tl"].map(n["city_tax"]).fillna(0)
    g["net"] = g["tl"].map(n["net_a2_demand"]).fillna(0)
    g["net1"] = g["tl"].map(n["net_a1_demand"]).fillna(0)
    g["q"] = np.where(g["acres"] > 0, g["net"] / g["acres"], 0).round(0).astype(int)
    g["q2"] = np.where(g["acres"] > 0, g["net1"] / g["acres"], 0).round(0).astype(int)
    g["nt"] = g["net"].round(0).astype(int)
    g["n2"] = g["net1"].round(0).astype(int)
    g["c"] = g["city_tax"].round(0).astype(int)
    ncap = float(np.quantile(np.abs(g.loc[g["q"] != 0, "q"]), NET_CLIP_Q))
    ncap2 = float(np.quantile(np.abs(g.loc[g["q2"] != 0, "q2"]), NET_CLIP_Q))

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

    # selection / search fields
    g = g.reset_index(drop=True)
    g["i"] = g.index.astype(int)
    g["s"] = g["SITEADDR"].fillna("").astype(str).str.strip()
    cen4326 = g.geometry.centroid.to_crs(4326)
    g["x"] = cen4326.x.round(5)
    g["y"] = cen4326.y.round(5)

    print(f"parcels: {len(g):,}  value clip ${cap:,.0f}/ac  net clip ${ncap:,.0f}/ac  "
          f"median taxed share {g['p'].median():.0f}%")

    out = g[["i", "s", "x", "y", "a", "m", "p", "r", "g", "b", "v", "w", "t", "u",
             "q", "q2", "nt", "n2", "c", "geometry"]].to_crs(4326)
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
            .replace("__NCAP2__", f"{ncap2:.0f}")
            .replace("__MAXNET__", f"{MAX_M_NET:.0f}"))
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"wrote {OUT_HTML} + data {OUT_DATA.stat().st_size/1e6:.0f} MB")


if __name__ == "__main__":
    main()
