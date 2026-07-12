#!/usr/bin/env python3
"""
70_budget.py  --  Parse the City of Portland FY 2025-26 Adopted Budget's
"Summary of Bureau Expenses by Fund" (Vol. 1) into machine-readable form.

This is the cost-side foundation: every bureau's expenses, by fund, split into
Personnel / External M&S / Internal M&S / Capital Outlay / Total. Fund-level
rows are validated arithmetically (the four categories must sum to the total),
so mis-parsed lines are dropped loudly rather than silently kept.

FY 2025-26 was chosen as the base year because it funds the same July 2025 -
June 2026 period as the tax-year-2025-26 levies on the revenue side.

Run:  conda run -n vpa python src/70_budget.py
Outputs:
  data/processed/budget_bureau_fund.csv    long form (bureau, fund, categories)
  data/processed/budget_bureaus.csv        bureau totals
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from pypdf import PdfReader

PDF = Path("Background Info/Budget/"
           "FY2025-26 Adopted Budget Vol 1 - City Summaries and Bureau Budgets.pdf")
OUT_LONG = Path("data/processed/budget_bureau_fund.csv")
OUT_BUR = Path("data/processed/budget_bureaus.csv")

NUM5 = re.compile(r"^(.*?)\s*((?:-?[\d,]+\s+){4}-?[\d,]+)\s*$")
HEADER_JUNK = re.compile(
    r"Adopted Budget|Financial Summar|Summary of Bureau|This table|Personnel$|"
    r"Services$|External Material|Internal Material|Total Bureau|Capital Outlay|"
    r"^\d+$|City of Por", re.IGNORECASE)


def to_int(s: str) -> int:
    return int(s.replace(",", ""))


def main():
    r = PdfReader(str(PDF))
    pages = [i for i in range(len(r.pages))
             if "Summary of Bureau Expenses by Fund" in (r.pages[i].extract_text() or "")]
    print(f"table pages: {[p+1 for p in pages]}")

    rows, bad = [], 0
    bureau = None
    for i in pages:
        for raw in (r.pages[i].extract_text() or "").splitlines():
            line = raw.strip()
            if not line or HEADER_JUNK.search(line):
                continue
            m = NUM5.match(line)
            if not m:
                # a plain text line = a bureau heading (possibly wrapped)
                if re.search(r"[A-Za-z]", line) and not re.search(r"\d", line):
                    bureau = line if not line.startswith("Subtotal") else bureau
                continue
            label = m.group(1).strip()
            nums = [to_int(x) for x in m.group(2).split()]
            p, e, iM, c, t = nums
            if p + e + iM + c != t:
                bad += 1
                continue
            if label.endswith("Subtotal") or label == "Subtotal":
                name = label[:-len("Subtotal")].strip() or bureau
                rows.append({"bureau": name, "fund": "__SUBTOTAL__",
                             "personnel": p, "external_ms": e, "internal_ms": iM,
                             "capital_outlay": c, "total": t})
                bureau = None
            else:
                if bureau is None:
                    bureau = "?"
                rows.append({"bureau": bureau, "fund": label,
                             "personnel": p, "external_ms": e, "internal_ms": iM,
                             "capital_outlay": c, "total": t})

    df = pd.DataFrame(rows)
    subs = df[df["fund"] == "__SUBTOTAL__"].copy()
    funds = df[df["fund"] != "__SUBTOTAL__"].copy()

    # attach fund rows to their bureau by the following subtotal name where
    # the heading line was lost to wrapping
    funds.loc[funds["bureau"] == "?", "bureau"] = None
    funds["bureau"] = funds["bureau"].bfill()

    OUT_LONG.parent.mkdir(parents=True, exist_ok=True)
    funds.to_csv(OUT_LONG, index=False)
    bur = subs.drop(columns=["fund"]).sort_values("total", ascending=False)
    bur.to_csv(OUT_BUR, index=False)

    print(f"fund rows: {len(funds)}  bureaus: {len(bur)}  "
          f"arithmetic-failed lines dropped: {bad}")
    print(f"citywide bureau expenses: ${bur['total'].sum()/1e9:.3f}B")
    print("\ntop bureaus:")
    print(bur.head(12)[["bureau", "total"]].to_string(index=False))


if __name__ == "__main__":
    main()
