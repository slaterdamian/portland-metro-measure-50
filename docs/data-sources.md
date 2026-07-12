# Data Sources

Every input is public open data from Metro, the City of Portland, or the county
assessors. Raw downloads live under `Background Info/` (git-ignored, not
redistributed). The machine-readable registry is
[config/sources.yml](../config/sources.yml); this file is the narrative record.

Snapshot of record: **Tax year 2025–26**; RLIS downloads July 2026.

## Metro RLIS Discovery — licensed under ODbL

> **Attribution:** *Contains information from Metro RLIS (Oregon Metro),
> licensed under the Open Database License (ODbL).* Derived databases are
> shared alike under the project's open license.

| Dataset | Used for | Key fields |
|---|---|---|
| **Taxlots (Public)** | Parcel geometry + assessed values (the revenue base). 646,591 tri-county parcels; 233,143 in Portland. **Ownership excluded by Metro** — no PII handling needed. | `TLID`, `TAXCODE`, `ASSESSVAL` (Measure-50 AV), `TOTALVAL` (RMV), `A_T_ACRES`, `JURIS_CITY`, `PROP_CODE`, `LANDUSE`, `PUBLIC_OWN`, `OWNERTYPE`, `HAS_MANY` |
| Taxlot Additional Records (Public) | Stacked/condo account supplement (joins on `TLID`) | account-level AV/RMV |
| Zoning | District geometry, regional standardized | `ZONE`, `ZONE_CLASS`, `ZONEGEN_CL`, `CITY` |
| Housing | Dwelling units per parcel (per-capita/per-unit cost basis) | `TLID`, `UNITS`, `UNIT_TYPE` |
| Urban Growth Boundary | Regional scope mask | — |
| City Limits (line), Freeways | Cartographic context | — |
| Streets, Sidewalks | Phase 2 network cost basis | jurisdiction fields TBD |

Portal: https://rlisdiscovery.oregonmetro.gov — prefer the **GeoJSON** exports
(KML exports proved truncated for large layers: the taxlot KML capped at ~26k of
646k features).

## City of Portland

| Dataset | Used for | Notes |
|---|---|---|
| **BES Collection System Lines** (open data portal / [PortlandMaps REST](https://www.portlandmaps.com/arcgis/rest/services/Public/Utilities_Sewer/MapServer)) | Sewer + stormwater network for cost allocation. 360,194 lines. | `OWNRSHIP` is plain text (`BES` = City of Portland; `TBD`, `ODOT`, `PRIV`, `PARK`, `PORT`), `SYSTEM` = SEWER/STORM/INLET, `PIPESIZE`, `MATERIAL`, `SERVSTAT` |
| **Title 33 Planning & Zoning Code** (eff. 2026-07-01) | Phase 3 dimensional standards | 1,855 pp, clean text layer. Base zones: 33.110 single-dwelling, 33.120 multi-dwelling, 33.130 commercial/mixed-use, 33.140 employment/industrial |
| FY2024-25 CIP Volume 2 | Capital cost side | |
| City Budget Office publications | Operating cost side | https://www.portland.gov/budget |

## County assessors

| Document | Used for | Status |
|---|---|---|
| Multnomah **Summary of Assessments & Taxes 2025-26** | District-level levies, rates, Measure-5 compression | ✅ in hand (2 pp district table) |
| Multnomah **tax-code-area consolidated rate table** | AV → tax dollars per parcel (62 Portland code areas) | ⚠️ **pending** — separate publication, multco.us/info/reports-and-data |
| Washington County Summary of A&T 2025-26 | Rates for the 383 Portland parcels in Washington County | ✅ in hand (code-area rates pp. 124–257) |
| Clackamas equivalent | 327 Portland parcels | pending (minor) |

## Known data caveats

- **Sliver/condo artifacts:** ~12k Portland parcels have tiny or zero
  `A_T_ACRES` (condo master lots, slivers), producing absurd value-per-acre
  outliers (max $6.3B/acre). Handled by acreage filters in rendering; proper
  treatment is allocating stacked-account value via Taxlot Additional Records.
- **Tri-county spillover:** Portland spans three counties (232,433 M / 383 W /
  327 C parcels). Rate joins must be county-aware — the counties use different
  `TAXCODE` formats (Multnomah `201`, Washington `051.50`).
- **The taxed share is ~40% citywide** (AV $76.2B / RMV $192.6B): Measure 50
  suppresses Portland's taxable base more than the suburbs (Beaverton measured
  ~54% in the archived pilot). State every result as AV- or RMV-based.
