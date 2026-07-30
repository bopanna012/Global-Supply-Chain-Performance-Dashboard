"""
Data loading and shared analytical helpers.

Deliberately free of any Streamlit import so the same functions serve both the
Jupyter notebook and the dashboard.

Column reference (verified against the live PortWatch feature services)
----------------------------------------------------------------------
daily_ports.csv
    date, year, month, day, portid, portname, country, ISO3,
    portcalls_container, portcalls_dry_bulk, portcalls_general_cargo,
    portcalls_roro, portcalls_tanker, portcalls_cargo, portcalls,
    import_container, import_dry_bulk, import_general_cargo, import_roro,
    import_tanker, import_cargo, import,
    export_container, export_dry_bulk, export_general_cargo, export_roro,
    export_tanker, export_cargo, export

daily_chokepoints.csv
    date, year, month, day, portid, portname,
    n_container, n_dry_bulk, n_general_cargo, n_roro, n_tanker, n_cargo,
    n_total,
    capacity_container, capacity_dry_bulk, capacity_general_cargo,
    capacity_roro, capacity_tanker, capacity_cargo, capacity
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

CARGO_TYPES = ["container", "dry_bulk", "general_cargo", "roro", "tanker"]

CARGO_LABELS = {
    "container": "Container",
    "dry_bulk": "Dry bulk",
    "general_cargo": "General cargo",
    "roro": "Ro-Ro (vehicles)",
    "tanker": "Tanker",
}

# Events used to annotate the time series. Dates are the widely reported
# start points; cite them in the notebook rather than treating them as data.
EVENTS = {
    "covid": ("2020-03-11", "2020-06-30", "COVID-19 onset"),
    "ever_given": ("2021-03-23", "2021-03-29", "Ever Given blocks Suez"),
    "panama_drought": ("2023-07-01", "2024-06-30", "Panama Canal drought restrictions"),
    "red_sea": ("2023-12-15", "2024-12-31", "Red Sea crisis / Cape re-routing"),
}


# --------------------------------------------------------------------------
# Loaders
# --------------------------------------------------------------------------
def _read(path: Path, **kw) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"{path.name} not found in {path.parent}.\n"
            "Run:  python scripts/download_data.py"
        )
    if path.suffix == ".parquet":
        return pd.read_parquet(path, **kw)
    return pd.read_csv(path, **kw)


def load_ports_daily(usecols: list[str] | None = None) -> pd.DataFrame:
    """Daily port-call and trade estimates for ~2,065 ports."""
    df = _read(RAW / "daily_ports.csv", usecols=usecols, parse_dates=["date"])
    return _tidy(df)


def load_chokepoints_daily() -> pd.DataFrame:
    """Daily transit calls and capacity for the 28 major chokepoints."""
    df = _read(RAW / "daily_chokepoints.csv", parse_dates=["date"])
    df = _tidy(df)
    # In this table portname is the chokepoint name - rename for readability
    return df.rename(columns={"portname": "chokepoint", "portid": "chokepoint_id"})


def load_ports_reference() -> pd.DataFrame:
    """Port metadata: coordinates, country, systemic-importance classification."""
    df = _read(RAW / "ports_reference.csv")
    df.columns = [c.strip() for c in df.columns]
    return _add_latlon(df)


def load_chokepoints_reference() -> pd.DataFrame:
    df = _read(RAW / "chokepoints_reference.csv")
    df.columns = [c.strip() for c in df.columns]
    return _add_latlon(df)


def load_processed(name: str) -> pd.DataFrame:
    """Load one of the small aggregates built for the dashboard."""
    return _read(PROCESSED / f"{name}.parquet")


def _tidy(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip() for c in df.columns]
    if "date" in df.columns and not np.issubdtype(df["date"].dtype, np.datetime64):
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.drop(columns=[c for c in ("ObjectId",) if c in df.columns])
    return df


def _add_latlon(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise whatever the reference table calls its coordinate columns."""
    lat_names = ["latitude", "lat", "LAT", "Latitude", "y", "Y"]
    lon_names = ["longitude", "lon", "lng", "LON", "Longitude", "x", "X"]
    for target, candidates in (("latitude", lat_names), ("longitude", lon_names)):
        if target not in df.columns:
            for c in candidates:
                if c in df.columns:
                    df[target] = pd.to_numeric(df[c], errors="coerce")
                    break
    return df


# --------------------------------------------------------------------------
# Analytical helpers - these carry the reasoning, so keep them well documented
# --------------------------------------------------------------------------
def add_calendar(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    out = df.copy()
    d = out[date_col]
    out["week"] = d.dt.to_period("W").dt.start_time
    out["month_start"] = d.dt.to_period("M").dt.start_time
    out["dow"] = d.dt.dayofweek           # 0 = Monday
    out["dow_name"] = d.dt.day_name()
    return out


def smooth(s: pd.Series, window: int = 7) -> pd.Series:
    """
    Centred rolling mean. Daily maritime data has a strong weekly cycle; a
    7-day window removes it without shifting turning points the way a trailing
    mean would.
    """
    return s.rolling(window, center=True, min_periods=max(1, window // 2)).mean()


def index_to_baseline(df: pd.DataFrame, value_col: str, group_col: str,
                      date_col: str, baseline: tuple[str, str]) -> pd.DataFrame:
    """
    Rebase each group to 100 over a baseline window.

    Essential for comparing chokepoints of wildly different absolute size -
    Suez handles far more transits than the Bosporus, so raw lines hide the
    proportional shock. Indexing makes the shapes comparable.
    """
    out = df.copy()
    lo, hi = pd.Timestamp(baseline[0]), pd.Timestamp(baseline[1])
    mask = out[date_col].between(lo, hi)
    base = out[mask].groupby(group_col)[value_col].mean().rename("_base")
    out = out.merge(base, left_on=group_col, right_index=True, how="left")
    out[f"{value_col}_idx"] = 100 * out[value_col] / out["_base"]
    return out.drop(columns="_base")


def pct_change_between(df: pd.DataFrame, value_col: str, group_col: str,
                       date_col: str, before: tuple[str, str],
                       after: tuple[str, str], min_base: float = 1.0) -> pd.DataFrame:
    """
    Mean value in `after` versus mean in `before`, per group.

    Returns absolute levels plus the percentage change, filtered to groups with
    a meaningful baseline so tiny ports don't produce meaningless +900% swings.
    """
    def window(w):
        m = df[date_col].between(pd.Timestamp(w[0]), pd.Timestamp(w[1]))
        return df[m].groupby(group_col)[value_col].mean()

    b, a = window(before), window(after)
    out = pd.concat([b.rename("before"), a.rename("after")], axis=1).dropna()
    out = out[out["before"] >= min_base]
    out["abs_change"] = out["after"] - out["before"]
    out["pct_change"] = 100 * out["abs_change"] / out["before"]
    return out.sort_values("pct_change", ascending=False).reset_index()


def recovery_half_life(series: pd.Series, shock_date: str,
                       baseline: tuple[str, str], horizon_days: int = 400) -> float:
    """
    Days for a series to climb back to half of its pre-shock baseline gap.

    Returns NaN when the series never recovers within the horizon - which is
    itself a finding, so do not silently drop those rows.
    """
    s = series.sort_index()
    base = s.loc[baseline[0]:baseline[1]].mean()
    if not np.isfinite(base) or base == 0:
        return np.nan
    post = s.loc[pd.Timestamp(shock_date):]
    post = post.iloc[:horizon_days]
    if post.empty:
        return np.nan
    trough = post.min()
    if trough >= base:
        return 0.0
    target = trough + 0.5 * (base - trough)
    trough_pos = post.values.argmin()
    after = post.iloc[trough_pos:]
    hit = after[after >= target]
    if hit.empty:
        return np.nan
    return float((hit.index[0] - post.index[trough_pos]).days)


def herfindahl(shares: pd.Series) -> float:
    """
    HHI concentration index on shares that sum to 1. Higher = more concentrated.
    Used to ask whether global container traffic is consolidating into fewer ports.
    """
    p = shares / shares.sum()
    return float((p ** 2).sum())


def cargo_columns(prefix: str) -> list[str]:
    """e.g. cargo_columns('portcalls') -> ['portcalls_container', ...]"""
    return [f"{prefix}_{c}" for c in CARGO_TYPES]


def to_long_cargo(df: pd.DataFrame, prefix: str, id_vars: list[str]) -> pd.DataFrame:
    """Wide cargo columns -> long format with a tidy `cargo` label column."""
    cols = [c for c in cargo_columns(prefix) if c in df.columns]
    out = df.melt(id_vars=id_vars, value_vars=cols,
                  var_name="cargo", value_name="value")
    out["cargo"] = (out["cargo"].str.replace(f"{prefix}_", "", regex=False)
                    .map(CARGO_LABELS))
    return out
