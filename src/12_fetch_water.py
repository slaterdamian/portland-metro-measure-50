#!/usr/bin/env python3
"""
12_fetch_water.py  --  Pull the Portland Water Bureau network from the public
PortlandMaps ArcGIS REST service (user-directed source; the BES collection
system GeoJSON covers sewer+storm but not water).

    Public/Utilities_Water/MapServer
      layer 8  Pressurized Mains          133k polylines (MATERIAL, MAINSIZE)
      layer 4  Regional Water Districts   53 polygons (service territory --
                                          the water-side ownership boundary)

Paginated query (2,000 records/page), GeoJSON out. Raw pulls land in
"Background Info/GIS data/fetched/" (the git-ignored raw zone); the mains are
also copied to data/interim/water_mains.geojson for the pipeline.

Pure standard library. Run:  python src/12_fetch_water.py
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://www.portlandmaps.com/arcgis/rest/services/Public/Utilities_Water/MapServer"
RAW = Path("Background Info/GIS data/fetched")
INTERIM = Path("data/interim")
PAGE = 2000


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.load(resp)


def pull_layer(layer_id: int, out_path: Path) -> int:
    features = []
    offset = 0
    while True:
        params = urllib.parse.urlencode({
            "where": "1=1", "outFields": "*", "outSR": 4326, "f": "geojson",
            "resultOffset": offset, "resultRecordCount": PAGE,
            "orderByFields": "OBJECTID",
        })
        data = fetch_json(f"{BASE}/{layer_id}/query?{params}")
        page = data.get("features", [])
        features.extend(page)
        if len(page) < PAGE:
            break
        offset += PAGE
        if offset % 20000 == 0:
            print(f"    ... {offset:,}")
        time.sleep(0.2)  # be polite to the public server
    out_path.parent.mkdir(parents=True, exist_ok=True)
    json.dump({"type": "FeatureCollection", "features": features},
              open(out_path, "w", encoding="utf-8"))
    return len(features)


def main():
    n = pull_layer(4, RAW / "PORTLAND_regional_water_districts.geojson")
    print(f"  regional water districts: {n:,} polygons")
    n = pull_layer(8, RAW / "PORTLAND_water_pressurized_mains.geojson")
    print(f"  pressurized mains: {n:,} segments")
    # pipeline copy
    src = RAW / "PORTLAND_water_pressurized_mains.geojson"
    (INTERIM / "water_mains.geojson").write_bytes(src.read_bytes())
    print(f"  -> {INTERIM/'water_mains.geojson'}")


if __name__ == "__main__":
    main()
