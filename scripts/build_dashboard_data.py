"""
Turn the large raw CSVs into the small parquet files the dashboard ships with.

    python scripts/build_dashboard_data.py

Why this step exists
--------------------
The raw daily ports table is several hundred MB - too big for a GitHub repo
(100 MB per-file limit) and far too slow for Streamlit Community Cloud, which
runs on ~1 GB of RAM. So the app never touches the raw data. It reads
pre-aggregated parquet files built here, which are a few MB and load instantly.

Mention this in your presentation: it is a real engineering decision, and the
kind of thing that separates a dashboard that works from one that times out.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import data as D  # noqa: E402

OUT = D.PROCESSED
OUT.mkdir(parents=True, exist_ok=True)


def save(df: pd.DataFrame, name: str) -> None:
    path = OUT / f"{name}.parquet"
    df.to_parquet(path, index=False, compression="zstd")
    print(f"  wrote {name}.parquet  {len(df):>9,} rows  "
          f"{path.stat().st_size/1e6:>6.1f} MB")


def main() -> int:
    print("Building dashboard aggregates\n")

    # ---------------------------------------------------------------- ports
    print("ports")
    keep = (["date", "portid", "portname", "country", "ISO3", "portcalls",
             "import", "export"] + D.cargo_columns("portcalls"))
    ports = D.load_ports_daily(usecols=keep)
    ref = D.load_ports_reference()

    # Weekly per port - the app's workhorse table.
    ports["week"] = ports["date"].dt.to_period("W").dt.start_time
    num = [c for c in ports.columns
           if c.startswith(("portcalls", "import", "export"))]
    weekly = (ports.groupby(["week", "portid", "portname", "country", "ISO3"],
                            as_index=False)[num].sum())

    # Attach coordinates + systemic class where the reference table has them
    join_cols = [c for c in ["portid", "latitude", "longitude"] if c in ref.columns]
    extra = [c for c in ref.columns
             if c.lower() in ("portclass", "port_class", "systemic", "type",
                              "importance", "region", "continent")]
    if "portid" in ref.columns:
        weekly = weekly.merge(ref[join_cols + extra].drop_duplicates("portid"),
                              on="portid", how="left")
    save(weekly, "ports_weekly")

    # Country-month rollup for the choropleth and country comparisons
    ports["month"] = ports["date"].dt.to_period("M").dt.start_time
    country = (ports.groupby(["month", "country", "ISO3"], as_index=False)[num].sum())
    save(country, "country_monthly")

    # Top-200 ports, kept daily for the detailed explorer view
    top = (ports.groupby("portid")["portcalls"].sum()
           .nlargest(200).index)
    daily_top = ports[ports["portid"].isin(top)].drop(columns=["week", "month"])
    save(daily_top, "top_ports_daily")

    # ---------------------------------------------------------- chokepoints
    print("\nchokepoints")
    cp = D.load_chokepoints_daily()
    save(cp, "chokepoints_daily")  # only 28 x ~2,500 rows - keep it all

    cpref = D.load_chokepoints_reference()
    if not cpref.empty:
        save(cpref, "chokepoints_reference")

    print("\nDone. The Streamlit app reads only from data/processed/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
