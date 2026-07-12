#!/usr/bin/env python3
"""
10_extract.py  --  Extract analysis-ready Portland slices from the raw public
sources (Metro RLIS GeoJSON downloads + Portland BES collection system).

All inputs are public open data:
  * Metro RLIS Discovery (ODbL)      -- taxlots, zoning, housing, UGB, city
                                        limits, freeways
  * Portland open data / BES          -- sewer & stormwater collection system

The RLIS "Taxlots (Public)" product already excludes ownership information,
so no PII handling is required downstream.

Run:  conda run -n vpa python src/10_extract.py
Outputs -> data/interim/*.geojson
"""
from __future__ import annotations

from pathlib import Path

import pyogrio

RAW = Path("Background Info/GIS data")
OUT = Path("data/interim")

EXTRACTS = [
    # (source file, where filter, columns or None, output name)
    (RAW / "METRO_RLIS_Taxlots_(Public)_-1228633436999156818.geojson",
     "JURIS_CITY='PORTLAND'",
     ["TLID", "PRIMACCNUM", "SITEADDR", "A_T_ACRES", "GIS_ACRES", "PROP_CODE",
      "LANDUSE", "STATECLASS", "TAXCODE", "COUNTY", "YEARBUILT", "BLDGSQFT",
      "LANDVAL", "BLDGVAL", "TOTALVAL", "ASSESSVAL", "PUBLIC_OWN", "OWNERTYPE",
      "HAS_MANY"],
     "taxlots_portland.geojson"),
    (RAW / "METRO_RLIS_Zoning.geojson",
     "CITY='Portland'",
     ["ZONE", "ZONE_CLASS", "ZONEGEN_CL", "CITY"],
     "zoning_portland.geojson"),
    (RAW / "METRO_RLIS_Housing.geojson",
     "JURIS_CITY='PORTLAND'",
     ["TLID", "UNITS", "UNIT_TYPE", "UNIT_SUBTY", "YEARBUILT", "MIXED_USE",
      "CONDO", "CONFIDENCE"],
     "housing_portland.geojson"),
    (RAW / "PORTLAND_Collection_System_Lines.geojson",
     None,
     ["UNITTYPE", "OWNRSHIP", "SYSTEM", "SERVSTAT", "PIPESIZE", "MATERIAL",
      "Install_Date"],
     "collection_system.geojson"),
    (RAW / "METRO_RLIS_Urban_Growth_Boundary_UGB.geojson",
     None, None, "boundary_ugb.geojson"),
    (RAW / "METRO_RLIS_City_Limits_(line).geojson",
     None, None, "city_limits_lines.geojson"),
    (RAW / "METRO_RLIS_Freeways.geojson",
     None, None, "freeways.geojson"),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for src, where, cols, name in EXTRACTS:
        gdf = pyogrio.read_dataframe(str(src), where=where, columns=cols)
        dst = OUT / name
        pyogrio.write_dataframe(gdf, str(dst), driver="GeoJSON")
        print(f"  {name:32} {len(gdf):>8,} features   "
              f"(where: {where or 'all'})")


if __name__ == "__main__":
    main()
