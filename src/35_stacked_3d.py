#!/usr/bin/env python3
"""
35_stacked_3d.py  --  Interactive parcel map, Portland OR: three views, one page.

  1 VALUE (default)  stacked AV/RMV: solid column = Measure-50 assessed value
                     per acre (Urban3 classed color); outlined faded top = real
                     market value left untaxed.
  2 NET              Revenues & Costs per acre (Frame A2 demand basis, stage 80).
  3 SHARE-ADJUSTED   the same net graded on the citywide 54.1% funding mix
                     (A1 redistribution): orange = relative freeloaders.

CONDO/TOWNHOME TREATMENT: unit parcels (e.g. "... ST UNIT #49") carry their own
values but only a building-footprint sliver of land (A_T_ACRES=0, GIS_ACRES ~
0.01), which exploded their per-acre bars. Units sharing a base address are
grouped into a regime; zero-value common-area parcels at the same base address
are absorbed into the regime's land and dropped from rendering; each unit's
per-acre denominator becomes (regime land / units). Values stay per-unit.

APPEARANCE: bars fade with distance from the view center (full strength in the
middle, lightest at the edges; recomputed on pan/zoom), ghost tops at alpha 56
with ALWAYS-opaque black wireframe edges. Click locks a selection (others fade
further); search matches parcel addresses locally, then OSM Nominatim.

Architecture: hand-rolled deck.gl page; ONE external GeoJSON payload shared by
all layers; ghost z-fighting via polygon offset. Basemap (c) OpenStreetMap;
search (c) Nominatim/OSM. Serve the folder locally or via GitHub Pages.

Run:  conda run -n vpa python src/35_stacked_3d.py
Outputs:
  outputs/figures/value_stack_3d.html
  outputs/figures/value_stack_data.geojson
"""
from __future__ import annotations

import json
import re
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
GHOST_ALPHA = 56      # untaxed top opacity (raised from 24 for legibility)
SIMPLIFY_FT = 6.0
UNIT_RE = r"\s+(?:UNIT|APT|STE|SPC|SP|CONDO|#)\b.*$"

BREAKS = [0, 250e3, 500e3, 1e6, 1.5e6, 2e6, 2.5e6, 5e6, 7.5e6, 10e6, 15e6, 20e6, np.inf]
HEX = ["#9e9e9e", "#1b5e20", "#388e3c", "#4caf50", "#8bc34a", "#c5e1a5",
       "#ffffbf", "#fdae61", "#f46d43", "#d7301f", "#b30000", "#7f0000", "#54278f"]
RGB = [[int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)] for h in HEX]

TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Portland Metro &amp; Measure 50</title>
<script src="https://unpkg.com/deck.gl@9.0.34/dist.min.js"></script>
<style>html,body{margin:0;height:100%}#app{width:100%;height:100%;position:relative}
#legend{position:absolute;bottom:14px;left:14px;background:rgba(255,255,255,.95);
padding:11px 13px;font:12px/1.45 sans-serif;border-radius:6px;z-index:1;max-width:330px;
box-shadow:0 1px 6px rgba(0,0,0,.25)}
#legend small{color:#666}
#toggle{position:absolute;top:14px;right:14px;z-index:1;font:13px sans-serif;
background:#fff;border:1px solid #999;border-radius:6px;padding:8px 14px;
cursor:pointer;box-shadow:0 1px 4px rgba(0,0,0,.25)}
#toggle:hover{background:#f0f0f0}
#searchwrap{position:absolute;top:14px;left:14px;z-index:2}
#search{width:260px;font:13px sans-serif;padding:8px 10px;border:1px solid #999;
border-radius:6px;box-shadow:0 1px 4px rgba(0,0,0,.25)}
#panel{position:absolute;top:56px;left:14px;z-index:2;background:rgba(255,255,255,.97);
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
<div id="loading" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,.85);z-index:5;font:15px sans-serif;color:#333">Loading ~190,000 parcels (~20&nbsp;MB compressed)&hellip;</div>
<button id="toggle">Show: Revenues &amp; Costs</button>
<div id="legend"></div>
<script>
const FOOT = `<small>Bars fade toward the view edges &mdash; pan to bring an
area into focus. Click a bar to pin its details (the pin follows you across
views); click empty ground to clear. Condo, townhome &amp; apartment sites
that the assessor splits across many unit lots are combined into a single bar
per site (total value over the site's land), so they compare directly with
rental buildings on one lot.<br/>
Data: Metro RLIS (ODbL) &middot; FY2025-26 Adopted Budget &middot; basemap
&copy; OpenStreetMap contributors &middot; search &copy; Nominatim/OSM</small>`;
const LEGEND_VALUE = `<b>1 &middot; What the land is worth &mdash; and what
Oregon actually taxes.</b><br/>
Each bar is one tax lot on its real footprint. The <b>solid bar</b> is its
assessed value per acre &mdash; the only value Oregon taxes (Measure 50). The
<b>outlined faded top</b> extends to its real market value: everything above
the solid bar is untaxed. Color = assessed $/acre, green (low) &rarr; red &rarr;
purple (high).<br/>
<b>How to read it:</b> tall, warm-colored bars are the land carrying the tax
base. The bigger a bar's faded top, the more of its market value Measure 50
shelters &mdash; citywide, the median lot is taxed on just <b>42%</b> of what
it's worth.<br/>` + FOOT;
const LEGEND_NET = `<b>2 &middot; Does each lot's city tax cover the city
services allocated to it?</b><br/>
Height = the gap, in $ per acre, between what the lot pays the City of Portland
in property tax and its allocated share of tax-supported services (FY2025-26
police, fire, parks, pension &amp; administration, allocated by dwellings and
building area). <b><span style="color:#141414">Black</span></b> = pays more
than its share of costs; <b><span style="color:#a63603">orange/red</span></b> =
pays less.<br/>
<b>How to read it:</b> the map runs mostly orange because property tax funds
only ~54% of these services citywide &mdash; business taxes and fees cover the
rest. So orange here is <i>not</i> automatically freeloading; view 3 corrects
for that.<br/>` + FOOT;
const LEGEND_CARRY = `<b>3 &middot; The fair freeloader test.</b><br/>
Same comparison as view 2, but graded on the curve of how Portland actually
funds itself: since property tax covers 54.1% of tax-supported services
citywide, a lot &quot;carries its share&quot; when its own tax covers at least
54.1% of its allocated cost. <b><span style="color:#141414">Black</span></b> =
carries more than its share (it subsidizes others);
<b><span style="color:#a63603">orange/red</span></b> = carries less (it is
subsidized). Height = the surplus or shortfall per acre.<br/>
<b>How to read it:</b> orange in THIS view means below-average contribution
even after accounting for the funding mix &mdash; the honest freeloader
signal.<br/>` + FOOT;

const NCAP = __NCAP__;
const NCAP2 = __NCAP2__;
const MODES = ['value', 'net', 'carry'];
const MODE_LABEL = {value: 'Taxable Value', net: 'Revenues & Costs',
                    carry: 'Share-Adjusted Net'};
let mode = 'value';
let selectedI = -1;
let selectedProps = null;
let DATA = null;
let vc = {x: __LON__, y: __LAT__, zoom: 11.6};
let vcTimer = null;

const deckgl = new deck.DeckGL({
  container: 'app',
  initialViewState: {latitude: __LAT__, longitude: __LON__, zoom: 11.6, pitch: 55, bearing: -15},
  controller: true,
  onViewStateChange: ({viewState}) => {
    clearTimeout(vcTimer);
    vcTimer = setTimeout(() => {
      // re-render the fade only for meaningful moves (attribute rebuild is heavy)
      const degPerPx = 360 / (512 * Math.pow(2, viewState.zoom));
      const moved = Math.hypot(viewState.longitude - vc.x, viewState.latitude - vc.y);
      if (moved < window.innerHeight * 0.12 * degPerPx &&
          Math.abs(viewState.zoom - vc.zoom) < 0.4) return;
      vc = {x: viewState.longitude, y: viewState.latitude, zoom: viewState.zoom};
      render();
    }, 300);
  },
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
function netColor(q, cap) {
  const t = Math.min(Math.abs(q) / cap, 1), f = Math.max(t, 0.08);
  const [c0, c1] = q > 0 ? [[217, 217, 217], [20, 20, 20]]
                         : [[253, 208, 162], [140, 45, 4]];
  return c0.map((v, i) => Math.round(v + (c1[i] - v) * f));
}
// radial focus: full strength near the view center, lightest at the edges
function radial(f) {
  const degPerPx = 360 / (512 * Math.pow(2, vc.zoom));
  const rFull = window.innerHeight * 0.28 * degPerPx;
  const rEdge = window.innerHeight * 0.85 * degPerPx;
  const dx = (f.properties.x - vc.x) * Math.cos(vc.y * Math.PI / 180);
  const dy = f.properties.y - vc.y;
  const d = Math.hypot(dx, dy);
  if (d <= rFull) return 1;
  if (d >= rEdge) return 0.22;
  return 1 - 0.78 * (d - rFull) / (rEdge - rFull);
}
function fadeF(f) {
  const s = (selectedI < 0 || f.properties.i === selectedI) ? 1 : 0.22;
  return Math.min(radial(f), s);
}
function trig() {
  return [selectedI, mode, vc.x.toFixed(3), vc.y.toFixed(3),
          Math.round(vc.zoom * 4)];
}
function layersFor(m) {
  const t = {getFillColor: trig(), getLineColor: trig()};
  if (m === 'value') return [osm,
    new deck.GeoJsonLayer({id: 'solid', data: DATA, extruded: true,
      pickable: true, wireframe: false,
      getElevation: f => f.properties.a,
      getFillColor: f => [f.properties.r, f.properties.g, f.properties.b,
                          Math.round(255 * fadeF(f))],
      getLineColor: [0, 0, 0, 0], updateTriggers: t}),
    new deck.GeoJsonLayer({id: 'ghost', data: DATA, extruded: true,
      pickable: false, wireframe: true,
      getElevation: f => f.properties.m,
      getFillColor: f => [f.properties.r, f.properties.g, f.properties.b,
                          Math.round(__GA__ * fadeF(f))],
      getLineColor: [0, 0, 0, 255],   // outline always fully opaque
      lineWidthMinPixels: 1,
      parameters: {depthMask: false},
      getPolygonOffset: () => [0, -600], updateTriggers: t})];
  const field = m === 'net' ? 'q' : 'q2';
  const cap = m === 'net' ? NCAP : NCAP2;
  return [osm,
    new deck.GeoJsonLayer({id: 'net-' + m, data: DATA, extruded: true,
      pickable: true, wireframe: false,
      getElevation: f => Math.min(Math.abs(f.properties[field]) / cap, 1) * __MAXNET__,
      getFillColor: f => netColor(f.properties[field], cap)
                          .concat(Math.round(255 * fadeF(f))),
      getLineColor: [0, 0, 0, 0], updateTriggers: t})];
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
  vc = {x: lon, y: lat, zoom: zoom};
  deckgl.setProps({initialViewState: {longitude: lon, latitude: lat, zoom: zoom,
    pitch: 55, bearing: -15, transitionDuration: 900}});
  clearTimeout(vcTimer);
  vcTimer = setTimeout(render, 1000);   // re-center the fade at the destination
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
    flyTo(hit.properties.x, hit.properties.y, 15);
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
  document.getElementById('loading').style.display = 'none';
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
    for c in ("av", "rmv", "acres"):
        g[c] = pd.to_numeric(g[c], errors="coerce").fillna(0)
    g = g[g.geometry.notna() & ~g.geometry.is_empty].copy()
    # simplify can re-invalidate polygons; snap precision + re-validate so the
    # regime dissolve (GEOS union) never hits topology conflicts
    gm = g.geometry.make_valid().simplify(SIMPLIFY_FT)
    gm = shapely.make_valid(shapely.set_precision(gm.values, 0.01))
    g["geometry"] = gm
    g = g[~g.geometry.is_empty].reset_index(drop=True)

    # ---- per-parcel net fields (joined BEFORE aggregation so sums carry) ------
    n = gpd.read_file(NET, ignore_geometry=True,
                      columns=["TLID", "city_tax", "net_a2_demand", "net_a1_demand"])
    n["tl"] = n["TLID"].astype(str).str.replace(" ", "", regex=False).str.upper()
    n = n.drop_duplicates("tl").set_index("tl")
    tl = g["TLID"].astype(str).str.replace(" ", "", regex=False).str.upper()
    g["city_tax"] = tl.map(n["city_tax"]).fillna(0)
    g["net"] = tl.map(n["net_a2_demand"]).fillna(0)
    g["net1"] = tl.map(n["net_a1_demand"]).fillna(0)

    # ---- regime identification -------------------------------------------------
    # Condo, townhome, and split-site apartment parcels are aggregated into ONE
    # bar per SITE (union footprint, summed values) so they display exactly like
    # an equivalent rental building on a single lot.
    g["rid"] = pd.NA

    # STAGE 1: Oregon condo-plat TLID convention -- unit lots numbered 70000+
    # in a thousand-block, with the plat's zero-value common tract in the same
    # block. Everything in a block that has at least one valued unit is a site.
    lot = pd.to_numeric(tl.str[-5:], errors="coerce").fillna(0).astype(int)
    blockkey = tl.str[:-3]
    in_series = (lot >= 70000).to_numpy()
    has_unit = (pd.DataFrame({"k": blockkey[in_series],
                              "av": g.loc[in_series, "av"]})
                .groupby("k")["av"].max() > 0)
    ok_blocks = set(has_unit[has_unit].index)
    m1 = in_series & blockkey.isin(ok_blocks).to_numpy()
    g.loc[m1, "rid"] = "B|" + blockkey[m1]

    # STAGE 2: spatial clustering for everything the TLID convention misses --
    # sliver lots (rowhouse plats on ordinary lot numbers), lots whose BUILDING
    # exceeds the lot (an assembled site's value concentrated on one footprint
    # lot), touching same-use valued siblings of those lots, and touching
    # private zero-value commons.
    free = g["rid"].isna().to_numpy()
    bsq = pd.to_numeric(g["BLDGSQFT"], errors="coerce").fillna(0)
    bldg_over = free & (g["av"] > 0).to_numpy() & \
        (bsq > 1.5 * g["acres"] * 43560).to_numpy() & (g["acres"] > 0).to_numpy()
    tiny = free & (g["av"] > 0).to_numpy() & (g["acres"] < 0.03).to_numpy()
    absorbable = free & (g["av"] <= 0).to_numpy() & \
        (g["PUBLIC_OWN"] != 1).to_numpy() & (g["acres"] <= 10).to_numpy()

    buf = g.geometry.buffer(3.0)
    lu = g["LANDUSE"].astype(str).to_numpy()
    av_arr = g["av"].to_numpy()
    bo = set(np.flatnonzero(bldg_over))
    sib = set()
    if bo:
        bo_gdf = gpd.GeoDataFrame({"ga": sorted(bo)},
                                  geometry=buf.to_numpy()[sorted(bo)], crs=g.crs)
        all_gdf = gpd.GeoDataFrame({"gb": np.arange(len(g))},
                                   geometry=g.geometry.values, crs=g.crs)
        p2 = gpd.sjoin(bo_gdf, all_gdf, predicate="intersects")
        for a, b in zip(p2["ga"].to_numpy(), p2["gb"].to_numpy()):
            if a != b and free[b] and av_arr[b] > 0 and lu[a] == lu[b]:
                sib.add(int(b))
    unit_set = set(np.flatnonzero(tiny)) | bo | sib
    absorb_set = set(np.flatnonzero(absorbable))
    live = unit_set | absorb_set
    live_idx = sorted(live)
    sub = gpd.GeoDataFrame({"gi": live_idx},
                           geometry=buf.to_numpy()[live_idx], crs=g.crs)
    pairs = gpd.sjoin(sub, sub, predicate="intersects")

    parent = {}
    def find(x):
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    for a, b in zip(pairs["gi_left"].to_numpy(), pairs["gi_right"].to_numpy()):
        if a != b:
            union(int(a), int(b))
    comp = {}
    for x in live:
        comp.setdefault(find(int(x)), []).append(int(x))
    rid_col = g["rid"].copy()
    n2c = 0
    for root, members in comp.items():
        if not any(m in unit_set for m in members):
            continue
        n2c += 1
        for m in members:
            rid_col.iat[m] = f"S|{root}"
    g["rid"] = rid_col

    # ---- aggregate regimes into one bar per site -------------------------------
    reg = g[g["rid"].notna()].copy()
    single = g[g["rid"].isna()].copy()
    base_addr = (reg["SITEADDR"].fillna("").astype(str).str.upper()
                 .str.replace(UNIT_RE, "", regex=True).str.strip())
    reg["_ab"] = base_addr
    agg = reg.dissolve(by="rid", aggfunc={"av": "sum", "rmv": "sum",
                                          "city_tax": "sum", "net": "sum",
                                          "net1": "sum"})
    grp = reg.groupby("rid")
    agg["n_units"] = grp["av"].apply(lambda s: int((s > 0).sum()))
    def pick_addr(s):
        s = s[s != ""]
        return s.mode().iat[0] if len(s) else ""
    agg["base"] = reg[reg["av"] > 0].groupby("rid")["_ab"].agg(pick_addr)
    first_addr = reg[reg["av"] > 0].groupby("rid")["SITEADDR"].first()
    agg["SITEADDR"] = np.where(
        agg["n_units"] > 1,
        agg["base"].fillna("") + " \u00b7 " + agg["n_units"].astype(str) + " units",
        first_addr.reindex(agg.index).fillna(""))
    agg["land"] = (agg.geometry.area / 43560).clip(lower=0.004)
    agg = agg[agg["av"] > 0]
    n_absorbed = int((reg["av"] <= 0).sum())
    print(f"regimes: {len(agg):,} sites from {len(reg):,} parcels "
          f"({int(agg['n_units'].sum()):,} valued units, {n_absorbed:,} commons "
          f"absorbed; TLID-blocks + {n2c:,} spatial clusters)")

    single["land"] = single["acres"]
    keep = ["SITEADDR", "av", "rmv", "land", "city_tax", "net", "net1", "geometry"]
    g = pd.concat([single[keep], agg.reset_index()[keep]], ignore_index=True)
    g = gpd.GeoDataFrame(g, geometry="geometry", crs=2913)
    g = g[(g["av"] > 0) & (g["land"] >= MIN_ACRES)].copy()

    # ---- derived display fields ------------------------------------------------
    g["q"] = (g["net"] / g["land"]).round(0).astype(int)
    g["q2"] = (g["net1"] / g["land"]).round(0).astype(int)
    g["nt"] = g["net"].round(0).astype(int)
    g["n2"] = g["net1"].round(0).astype(int)
    g["c"] = g["city_tax"].round(0).astype(int)
    ncap = float(np.quantile(np.abs(g.loc[g["q"] != 0, "q"]), NET_CLIP_Q))
    ncap2 = float(np.quantile(np.abs(g.loc[g["q2"] != 0, "q2"]), NET_CLIP_Q))

    g["avpa"] = g["av"] / g["land"]
    g["rmvpa"] = np.maximum(g["rmv"] / g["land"], g["avpa"])
    cap = float(np.quantile(g["rmvpa"], CLIP_Q))
    scale = MAX_M / cap
    g["a"] = (np.minimum(g["avpa"], cap) * scale).round(0).astype(int)
    g["m"] = (np.minimum(g["rmvpa"], cap) * scale).round(0).astype(int)
    g["p"] = (100 * g["avpa"] / g["rmvpa"]).round(0).astype(int)
    cls = np.digitize(g["avpa"].to_numpy(), BREAKS[1:-1], right=True)
    g["r"] = [RGB[k][0] for k in cls]
    g["g"] = [RGB[k][1] for k in cls]
    g["b"] = [RGB[k][2] for k in cls]
    g["v"] = (g["avpa"] / 1000).round(0).map("${:,.0f}k/ac".format)
    g["w"] = (g["rmvpa"] / 1000).round(0).map("${:,.0f}k/ac".format)
    g["t"] = g["av"].map(money)
    g["u"] = np.maximum(g["rmv"], g["av"]).map(money)

    g = g.reset_index(drop=True)
    g["i"] = g.index.astype(int)
    g["s"] = g["SITEADDR"].fillna("").astype(str).str.strip()
    cen4326 = g.geometry.centroid.to_crs(4326)
    g["x"] = cen4326.x.round(5)
    g["y"] = cen4326.y.round(5)

    print(f"bars: {len(g):,}  value clip ${cap:,.0f}/ac  net clip ${ncap:,.0f}/ac  "
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
