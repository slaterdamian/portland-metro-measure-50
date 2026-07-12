# Cost-Allocation Methodology — Draft for Review

**Status: proposal.** This document is the judgment layer of the analysis — which
costs are netted against which revenues, allocated by what rule. Approve or edit
it before anything is computed; every choice below can be argued with, and the
sensitivity section commits to showing how much the choices matter.

All dollars are FY 2025-26 Adopted Budget (chosen to fund the same July 2025 –
June 2026 period as the tax-year-2025-26 levies on the revenue side).

## 1. What the money actually looks like

**Revenue** (computed, stages 40–60): Portland parcels pay **$2.012B** in
property tax — education $770.8M (38.3%), **City of Portland $681.7M (33.9%)**,
other government $560.0M (27.8%).

**City costs** (parsed, stage 70): $4.418B of bureau expenses, but funding
matters more than totals:

| Funding class | $ | Funded by | In the tax frame? |
|---|---|---|---|
| General Fund bureaus (26) | $1,019.8M | property tax + business taxes + state shared + fees | **yes** |
| FPDR (police/fire pension) | $241.0M | its own property-tax levy | **yes** |
| Water Bureau funds | $850.5M | ratepayers | no — enterprise |
| BES sewer/storm funds | $482.2M | ratepayers | no — enterprise |
| PBOT transportation funds | $339.2M | gas tax, fees, parking | no — user-funded |
| Everything else (grants, internal service, TIF, debt) | balance | various | no |

The three biggest General Fund bureaus are Police ($304.4M), Fire ($195.1M), and
Parks ($175.2M) — two-thirds of the General Fund.

## 2. The frames

**Frame A — the city tax frame (primary net map).** Compare each parcel's
**City-of-Portland property tax** (its share of the $681.7M) against its
allocated share of **tax-supported city services** (General Fund + FPDR =
$1,260.8M). Two variants, both reported:

- **A1 — redistribution.** Cost pool = the $681.7M the city actually collects,
  allocated by service bases. Citywide net = 0 by construction; the map shows
  *who subsidizes whom* within the property-tax system. (Comparable to the
  archived pilot.)
- **A2 — coverage.** Cost pool = the full $1,260.8M of tax-supported services.
  Citywide net is **−$579M by construction** — property tax covers only ~54% of
  tax-supported services; business taxes, state shared revenue, and fees fill
  the rest. This is the Urban3/Annapolis style, with the honest caveat attached:
  a net-negative parcel is not a freeloader — its occupants may pay the business
  taxes that close the gap. A2 answers "does the *property tax on this land*
  carry the services the land consumes," nothing more.

**Frame B — enterprise supplement (not a net map).** Water ($850.5M) and BES
($482.2M) are ratepayer-funded: users already pay by the gallon, so netting them
against *taxes* would be a category error. Instead report **infrastructure
intensity**: city network feet adjacent to each parcel (2,226 mi of PWB mains;
BES `OWNRSHIP='BES'` pipes), and network feet per dwelling by density band — the
long-run maintenance-liability measure that proved decisive in the pilot (an 11×
per-dwelling difference between sparse and dense).

**Frame C — all-district context.** The education ($770.8M) and other-government
($560.0M) categories, allocated per dwelling unit, as a contextual layer — kept
separate from the headline city map because those districts' budgets and service
logic are not the city's.

## 3. Allocation bases (Frame A)

| Cost block | $ (GF+FPDR) | Basis | Rationale |
|---|---|---|---|
| Police | $304.4M | **developed intensity**: dwelling units + non-residential building sqft (RLIS `BLDGSQFT`) | service demand follows people *and* activity, not bare land |
| Fire & Rescue | $195.1M | same as Police | same logic; fire risk scales with structures |
| FPDR pension | $241.0M | follows the Police+Fire allocation | it is deferred compensation for those same services |
| Parks & Recreation | $175.2M | dwelling units | residents consume parks |
| Housing Bureau | $36.2M | dwelling units | |
| Streets-related GF transfers (if any surface in Vol.2) | TBD | street frontage (RLIS streets adjacent to parcel) | infrastructure scales with network |
| General government / admin (CFO, City Administrator, Council, Attorney, Auditor, HR, BPS, everything else GF) | ~$309M | per parcel | overhead; every account costs roughly the same to govern |

Notes: dwelling units come from RLIS Housing (172,523 Portland records,
spatially joined); population ≡ units × household size, so "per capita" and
"per dwelling" are the same allocation — we say *per dwelling* and mean both.
Non-residential intensity uses building square footage because Portland's
employment locations (jobs data) aren't in our sources yet.

## 4. The basis-sensitivity commitment

The pilot's central lesson: under a people-based allocation dense residential
looks subsidized; under a land/network-based allocation it flips to solvent.
**Neither is "correct" — they answer different questions.** So every Frame A map
ships in two versions:

1. **Demand basis** (the table above — units + sqft), and
2. **Network basis**: the same pools allocated by city network feet adjacent to
   each parcel (streets + BES pipes + water mains within 60 ft).

Zones or parcel classes whose verdict flips between the two get flagged
explicitly — that flip *is* a finding, not noise to hide.

## 5. Explicit exclusions & treatments

- **TIF/urban-renewal districts, debt service, internal-service and reserve
  funds**: excluded from allocation (financing mechanics, not service delivery).
  TIF's rate impact is already embedded in the revenue side's code-area rates.
- **PBOT**: excluded from the tax frame (gas-tax/fee-funded) but its street
  network still serves as an allocation basis and appears in Frame B intensity.
- **Exempt parcels** (`PUBLIC_OWN=1`, AV=0): receive allocated costs but pay no
  tax — they will show as pure deficit. Reported separately so government/parks
  land doesn't masquerade as a "failing neighborhood."
- **Condo/sliver parcels**: value stacked via Taxlot Additional Records where
  possible; per-acre metrics suppressed below 0.005 acres.

## 6. Validation plan

- Category totals must reconcile: allocated pool = source pool to the dollar
  (the stage-60 standard).
- Spot parcels: a downtown tower, a standard R5 house, a big-box store — hand-
  check their allocated costs for face validity.
- Land-area split (% of acres net-positive) reported alongside parcel counts.

## 7. Open decisions (your call)

1. **A2 (coverage) as the headline map**, with A1 as the internal check — or the
   reverse? (Recommendation: A2 headline; it's the honest Urban3 comparison.)
2. **Police/Fire basis blend**: units + non-res sqft as proposed, or pure
   per-dwelling? (The blend needs a sqft-to-unit equivalence factor — proposed:
   equate the median dwelling's ~1,500 sqft to one unit.)
3. **FPDR**: allocate with Police/Fire as proposed, or treat as citywide
   overhead (per parcel)? It is a legacy liability, not current service.
4. Anything in the exclusions list you'd pull back in?
