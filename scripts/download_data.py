"""
Download the raw IMF PortWatch data into data/raw/.

Run once from the repo root:

    python scripts/download_data.py

The two daily tables are large (the ports file is several hundred MB), so they
are written to data/raw/ which is gitignored. Run
scripts/build_dashboard_data.py afterwards to produce the small aggregates the
Streamlit app actually ships with.

Data source: IMF PortWatch (portwatch.imf.org), IMF, based on satellite AIS
signals from ~90,000 ships. Free to use with attribution.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd
import requests

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

HUB = "https://portwatch.imf.org/api/download/v1/items/{item}/csv?layers=0"
REST = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/{svc}/FeatureServer/0/query"

# Hub item ids for the two big daily tables (verified against the DCAT feed)
BIG_TABLES = {
    "daily_ports.csv": "83b1bbc7b3354c5fb1f40673bb8f852e",
    "daily_chokepoints.csv": "3da2b9ca97684916b75c4013f95d18ab",
}

# Small reference tables - pulled through the REST query API instead
REFERENCE = {
    "ports_reference.csv": "PortWatch_ports_database",
    "chokepoints_reference.csv": "PortWatch_chokepoints_database",
}

# Secondary sources used by Q7 and Q10 in the notebook
GSCPI_URL = "https://www.newyorkfed.org/medialibrary/research/interactives/gscpi/downloads/gscpi_data.xlsx"
LPI_INDICATOR_URL = (
    "https://api.worldbank.org/v2/country/all/indicator/LP.LPI.OVRL.XQ"
    "?format=json&per_page=2000&mrv=1"
)


def download_csv(url: str, dest: Path, chunk: int = 1 << 20) -> None:
    """Stream a CSV to disk with a simple progress readout."""
    if dest.exists():
        print(f"  skip   {dest.name} (already downloaded)")
        return
    print(f"  fetch  {dest.name} ...", flush=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with requests.get(url, stream=True, timeout=180) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        done = 0
        with open(tmp, "wb") as fh:
            for block in r.iter_content(chunk_size=chunk):
                fh.write(block)
                done += len(block)
                if total:
                    pct = 100 * done / total
                    print(f"\r         {done/1e6:,.0f} MB / {total/1e6:,.0f} MB "
                          f"({pct:4.1f}%)", end="", flush=True)
                else:
                    print(f"\r         {done/1e6:,.0f} MB", end="", flush=True)
    tmp.rename(dest)
    print(f"\r         done: {dest.stat().st_size/1e6:,.1f} MB{' ' * 20}")


def download_reference(service: str, dest: Path, page: int = 2000) -> None:
    """
    Page through an ArcGIS feature service and save all attributes as CSV.
    Used for the small port / chokepoint reference tables, which carry the
    coordinates and the systemic-importance classification.
    """
    if dest.exists():
        print(f"  skip   {dest.name} (already downloaded)")
        return
    print(f"  fetch  {dest.name} ...", flush=True)
    url = REST.format(svc=service)
    rows, offset = [], 0
    while True:
        params = {
            "where": "1=1",
            "outFields": "*",
            "returnGeometry": "true",
            "f": "json",
            "resultOffset": offset,
            "resultRecordCount": page,
        }
        resp = requests.get(url, params=params, timeout=120)
        resp.raise_for_status()
        payload = resp.json()
        if "error" in payload:
            raise RuntimeError(payload["error"])
        features = payload.get("features", [])
        if not features:
            break
        for f in features:
            rec = dict(f.get("attributes", {}))
            geom = f.get("geometry") or {}
            # Carry the point geometry through as explicit lat/lon columns
            if "x" in geom and "y" in geom:
                rec.setdefault("longitude", geom["x"])
                rec.setdefault("latitude", geom["y"])
            rows.append(rec)
        offset += len(features)
        print(f"\r         {offset:,} rows", end="", flush=True)
        if not payload.get("exceededTransferLimit"):
            break
        time.sleep(0.2)
    pd.DataFrame(rows).to_csv(dest, index=False)
    print(f"\r         done: {len(rows):,} rows{' ' * 20}")


def download_gscpi(dest: Path) -> None:
    """NY Fed Global Supply Chain Pressure Index - used by Q10."""
    if dest.exists():
        print(f"  skip   {dest.name} (already downloaded)")
        return
    print(f"  fetch  {dest.name} ...", flush=True)
    r = requests.get(GSCPI_URL, timeout=60)
    r.raise_for_status()
    dest.write_bytes(r.content)
    print(f"         done: {dest.stat().st_size/1e6:,.1f} MB")


def download_lpi(dest: Path) -> None:
    """World Bank Logistics Performance Index (overall score) - used by Q7."""
    if dest.exists():
        print(f"  skip   {dest.name} (already downloaded)")
        return
    print(f"  fetch  {dest.name} ...", flush=True)
    r = requests.get(LPI_INDICATOR_URL, timeout=60)
    r.raise_for_status()
    rows = r.json()[1]
    df = pd.DataFrame([
        {"ISO3": d["countryiso3code"], "Country": d["country"]["value"],
         "LPI Score": d["value"], "Year": d["date"]}
        for d in rows if d["value"] is not None
    ])
    df.to_csv(dest, index=False)
    print(f"         done: {len(df):,} countries")


def main() -> int:
    print("IMF PortWatch - raw data download")
    print(f"target: {RAW}\n")

    print("Reference tables")
    for name, service in REFERENCE.items():
        try:
            download_reference(service, RAW / name)
        except Exception as exc:  # noqa: BLE001
            print(f"\n  !! {name} failed: {exc}")

    print("\nDaily tables (large - this is the slow part)")
    for name, item in BIG_TABLES.items():
        try:
            download_csv(HUB.format(item=item), RAW / name)
        except Exception as exc:  # noqa: BLE001
            print(f"\n  !! {name} failed: {exc}")
            print("     If this keeps failing, download it by hand from")
            print("     https://portwatch.imf.org/pages/data-and-methodology")
            print(f"     and save it as {RAW / name}")

    print("\nSecondary sources (Q7, Q10)")
    try:
        download_lpi(RAW / "lpi.csv")
    except Exception as exc:  # noqa: BLE001
        print(f"\n  !! lpi.csv failed: {exc}")
        print("     Download by hand from https://lpi.worldbank.org/")
    try:
        download_gscpi(RAW / "gscpi_data.xlsx")
    except Exception as exc:  # noqa: BLE001
        print(f"\n  !! gscpi_data.xlsx failed: {exc}")
        print("     Download by hand from https://www.newyorkfed.org/research/policy/gscpi")

    print("\nNext: python scripts/build_dashboard_data.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
