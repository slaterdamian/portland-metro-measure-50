# Portland Metro & Measure 50

*A fiscal analysis of land use in Portland, Oregon — modeling taxable value,
revenue, and municipal cost per acre in the tradition of
[Urban3](https://www.urbanthree.com/) and
[Strong Towns](https://www.strongtowns.org/) — built entirely from public open
data, and extending into a zoning-feasibility question: what density does land
*need* to pay for the services it consumes, and does the zoning code allow it?*

> ### 🌐 [Explore the interactive map →](https://slaterdamian.github.io/portland-metro-measure-50/)
> All 192,600 Portland parcels in 3D, three views in one page: **taxable value**
> (solid = taxed Measure-50 value, ghost top = untaxed market value),
> **revenues & costs** (Annapolis-style fiscal net), and **share-adjusted net**
> (relative freeloaders with the funding mix controlled for). Click a parcel to
> lock and compare it across views; search any address or landmark.
> *~20 MB download on first load.*

> **Status: rebuild in progress.** This project was restarted on exclusively
> public, redistributable sources (Metro RLIS Discovery, Portland open data,
> county assessor publications). Phase 1 (value per acre) is implemented;
> the cost/net and zoning-feasibility phases are being rebuilt on the same
> foundations. Critique welcome — every assumption is documented to be argued
> with.

## Data sources & licensing

All inputs are public open data; none are redistributed in this repository.
See [docs/data-sources.md](docs/data-sources.md) and
[config/sources.yml](config/sources.yml) for the full provenance registry.

- **Metro RLIS Discovery** (ODbL) — taxlots (ownership excluded by Metro),
  zoning, housing inventory, UGB, city limits, streets, freeways, sidewalks.
  *Contains information from Metro RLIS (Oregon Metro), licensed under the
  Open Database License (ODbL).*
- **City of Portland open data / PortlandMaps REST** — BES sewer & stormwater
  collection system (with plain-text ownership), budget & CIP documents,
  Title 33 Planning & Zoning Code.
- **County assessors** (Multnomah primary; Washington & Clackamas for the
  slivers of Portland in those counties) — assessment & taxation summaries.

## Pipeline

```
Background Info/   raw public downloads (git-ignored)
        │
        ▼  src/10_extract.py      Portland slices (GDAL/pyogrio; JURIS_CITY filter)
data/interim/
        ▼  src/20_value_per_acre.py   AV & RMV per acre, taxed share (Measure 50)
data/processed/
        ▼  src/30_render_3d.py    Urban3-style 3D render (value-faithful grid)
outputs/figures/
```

```bash
conda env create -f environment.yml && conda activate vpa   # one-time
conda run -n vpa python src/10_extract.py
conda run -n vpa python src/20_value_per_acre.py
conda run -n vpa python src/30_render_3d.py
```

## Oregon specifics (the two facts that shape everything)

1. **Taxes are levied on Measure-50 assessed value (AV), not market value.**
   RLIS carries both (`ASSESSVAL`, `TOTALVAL`), so the model computes both the
   taxable-base map and the market-value map — and their ratio, the **taxed
   share**, makes Measure 50's compression visible parcel by parcel.
2. **Revenue in dollars = AV × the consolidated rate of the parcel's tax code
   area.** The Multnomah County code-area rate table is a pending input; all
   value-per-acre results are rate-independent.

## Roadmap

- **Phase 1 — value per acre.** ✅ Assessed & market value per acre, taxed
  share; 3D render. (233k parcels.)
- **Phase 2 — cost & net per acre.** 🔜 District revenue (rate table pending),
  cost allocation over city-owned networks (BES collection system `OWNRSHIP`,
  RLIS streets), the surplus/deficit map, and cost-basis sensitivity.
- **Phase 3 — zoning feasibility.** 🔜 Extract dimensional standards from
  Title 33 (1,855 pp, text-parseable), derive the density each location needs
  to be fiscally solvent, compare against what the code permits.

## License

Code: MIT ([LICENSE](LICENSE)). Data: property of the respective public
agencies under their terms (RLIS under ODbL); not redistributed here.
