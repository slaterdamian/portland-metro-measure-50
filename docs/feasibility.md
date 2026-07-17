# Zoning Feasibility — Deriving Required Density Backwards

*Phase 3. The project's thesis inverted onto Portland's FAR-based code: instead
of treating zoning standards as given, compute the built intensity each zone
NEEDS for fiscal solvency and ask whether Title 33 allows it.*

## Method (src/95_title33.py, src/96_feasibility.py)

**Standards** come from Title 33's summary tables, captured raw
(`data/processed/title33_tables/`) and transcribed to
`zoning_standards.csv`: Table 110-4 (single-dwelling FAR by unit count under
the Residential Infill Project), Table 120-4 (multi-dwelling FAR, height, and
**minimum density mandates**), Table 130-2 (commercial/mixed-use), Table 140-2
(employment/industrial).

**The model**, per zone (parcels joined to RLIS zoning by centroid):

- `solvency = city tax paid ÷ allocated tax-supported cost` (stage-80 Frame A2),
  under both the **demand basis** (costs follow dwellings + building area) and
  the **network basis** (costs follow city infrastructure feet).
- `required FAR = built FAR × cost ÷ tax` — the built intensity at which the
  zone's tax covers its cost, assuming value scales with floor area at the
  zone's current assessed-$-per-built-sqft (a stated linearity assumption).
- The same in dwelling units per acre for residential zones.
- Verdict against the code: solvent now / achievable under base FAR /
  achievable only with bonus FAR / exceeds zoned capacity / no FAR limit.

## Results (TY2025-26, demand basis unless noted)

**1. Nothing exceeds zoned capacity.** Every zone that isn't already solvent
can reach solvency *within Title 33 as written* — most under **base** FAR, with
only the densest zones (RX, RM3, RM4) needing their **bonus** FAR. The binding
constraint on fiscal performance in Portland is not the zoning code; it is
**underbuilding**: built FAR runs far below zoned FAR everywhere (CX has built
1.55 of an allowed 4.0; RM2 has 0.34 of 1.5; R5 has 0.27 of 0.8).

**2. The basis flip, on zones.** Under the demand basis the only "solvent now"
zones are large-lot single-dwelling (R20 1.31, R10 1.16) and low-intensity
employment (EG2 1.03) — few occupants, decent tax. Under the **network basis**
the picture inverts: the dense centers become the strong performers (RX 2.56,
CX 1.81, RM4 1.75, EX 1.72) while R20 falls to 0.41 — sparse land pays for its
occupants but not for its pavement. Neither basis is "correct"; the flip *is*
the finding.

**3. Portland's minimum-density mandates almost reach solvency.** CM2's
required density (26 du/ac) is *below* its mandated minimum (30 du/ac): a
development merely complying with the code's floor is fiscally solvent. In the
RM zones the minimums fall short of the requirement (RM2: mandated 30 vs
required 55 du/ac) — the code points in the right direction but does not go
far enough to make new development pay its own way under people-based costing.

**4. Magnitudes.** Required FAR for solvency: R5 0.45 (zoned 0.8), RM2 0.97
(zoned 1.5), CM2 0.97 (zoned 2.5), CX 2.93 (zoned 4.0), RX 4.17 (base 4.0,
bonus 6.0). In residential terms: R5 needs ~12 du/ac (has 7.3), RM1 needs ~36
(has 12.5).

## Caveats

- **Linearity**: required FAR assumes value per built sqft stays at the zone's
  current level as intensity rises — new construction usually appraises higher,
  which makes these requirements conservative (the true bar is lower).
- **A2 coverage frame**: solvency is measured against the full tax-supported
  cost pool, of which property tax funds ~54% citywide — so zone solvency < 1
  is the norm, and cross-zone comparison is the meaningful reading.
- **Extrapolation**: RX's "required 213 du/ac" projects far outside current
  form; treat the dense-zone requirements as directional.
- Bonus FARs summarized from 33.110.265 / 33.120.210 / Table 130-3 /
  33.140.205.C; CX inside the Central City plan district has higher limits than
  modeled. Centroid zone-join; OS/RF/RMP/CI/IR/CR excluded as n/a.
