"""
Global Supply Chain Performance - interactive dashboard.

Run locally:
    streamlit run app.py

Reads only from data/processed/*.parquet (built by scripts/build_dashboard_data.py),
never from the raw CSVs - that is what keeps it fast enough for Community Cloud.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src import data as D
from src import theme as T

st.set_page_config(
    page_title="Global Supply Chain Performance",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Keep the app's chrome consistent with the figure palette
st.markdown(
    f"""
    <style>
      .block-container {{padding-top: 2.2rem; padding-bottom: 2rem;}}
      h1, h2, h3 {{color: {T.INK}; font-weight: 700;}}
      [data-testid="stMetricValue"] {{font-size: 1.7rem; color: {T.INK};}}
      [data-testid="stMetricLabel"] {{color: {T.INK_SOFT};}}
      .caption {{color: {T.INK_SOFT}; font-size: 0.86rem;}}
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading data ...")
def get(name: str) -> pd.DataFrame:
    return D.load_processed(name)


def available(name: str) -> bool:
    return (D.PROCESSED / f"{name}.parquet").exists()


if not available("chokepoints_daily"):
    st.title("Global Supply Chain Performance")
    st.error(
        "Processed data not found.\n\n"
        "Run these two commands from the repo root first:\n\n"
        "```\npython scripts/download_data.py\npython scripts/build_dashboard_data.py\n```"
    )
    st.stop()

cp = get("chokepoints_daily")
ports_weekly = get("ports_weekly") if available("ports_weekly") else pd.DataFrame()
country_monthly = get("country_monthly") if available("country_monthly") else pd.DataFrame()


# --------------------------------------------------------------------------
# Sidebar controls
# --------------------------------------------------------------------------
st.sidebar.title("Filters")
st.sidebar.caption("Every view below responds to these controls.")

dmin, dmax = cp["date"].min().date(), cp["date"].max().date()
date_range = st.sidebar.slider(
    "Date range",
    min_value=dmin,
    max_value=dmax,
    value=(max(dmin, pd.Timestamp("2022-01-01").date()), dmax),
    format="MMM YYYY",
)

cargo_label = st.sidebar.selectbox(
    "Cargo type",
    ["All cargo"] + list(D.CARGO_LABELS.values()),
    help="Container traffic reacts fastest to disruption; tankers are stickier.",
)
cargo_key = next((k for k, v in D.CARGO_LABELS.items() if v == cargo_label), None)

smoothing = st.sidebar.select_slider(
    "Smoothing window",
    options=[1, 7, 14, 30],
    value=7,
    help="Daily maritime data has a strong weekly cycle. 7 days removes it.",
)

show_events = st.sidebar.checkbox("Mark known disruption events", value=True)

st.sidebar.markdown("---")
st.sidebar.caption(
    "Source: IMF PortWatch — daily AIS-derived estimates for 2,065 ports "
    "and 28 chokepoints."
)


def in_range(df: pd.DataFrame, col: str = "date") -> pd.DataFrame:
    lo, hi = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
    return df[df[col].between(lo, hi)]


def cp_value_col() -> str:
    return f"n_{cargo_key}" if cargo_key and f"n_{cargo_key}" in cp.columns else "n_total"


def port_value_col() -> str:
    col = f"portcalls_{cargo_key}" if cargo_key else "portcalls"
    return col if col in ports_weekly.columns else "portcalls"


def apply_events(fig: go.Figure) -> go.Figure:
    if not show_events:
        return fig
    lo, hi = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1])
    for key, (start, end, label) in D.EVENTS.items():
        s, e = pd.Timestamp(start), pd.Timestamp(end)
        if e >= lo and s <= hi:
            T.event_band(fig, max(s, lo), min(e, hi), label)
    return fig


# --------------------------------------------------------------------------
# Header + headline metrics
# --------------------------------------------------------------------------
st.title("Global Supply Chain Performance")
st.markdown(
    "<p class='caption'>How the world's shipping network absorbed the "
    "2023–24 chokepoint crises — traced through satellite signals from "
    "~90,000 ships.</p>",
    unsafe_allow_html=True,
)

cp_f = in_range(cp)
vcol = cp_value_col()

recent = cp_f[cp_f["date"] >= cp_f["date"].max() - pd.Timedelta(days=30)]
prior = cp_f[(cp_f["date"] < cp_f["date"].max() - pd.Timedelta(days=30))
             & (cp_f["date"] >= cp_f["date"].max() - pd.Timedelta(days=60))]

m1, m2, m3, m4 = st.columns(4)
with m1:
    st.metric("Chokepoints tracked", f"{cp['chokepoint'].nunique()}")
with m2:
    cur = recent[vcol].sum() / 30 if len(recent) else 0
    prev = prior[vcol].sum() / 30 if len(prior) else 0
    delta = (100 * (cur - prev) / prev) if prev else None
    st.metric("Daily transits (30-day avg)", f"{cur:,.0f}",
              f"{delta:+.1f}% vs prior month" if delta is not None else None)
with m3:
    if not ports_weekly.empty:
        st.metric("Ports covered", f"{ports_weekly['portid'].nunique():,}")
with m4:
    st.metric("Data through", f"{cp['date'].max():%d %b %Y}")

st.markdown("---")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Global pulse", "Chokepoints", "Ports", "Resilience", "Method & sources"]
)


# --------------------------------------------------------------------------
# Tab 1 - Global pulse
# --------------------------------------------------------------------------
with tab1:
    st.subheader("Where the world's ships are calling")

    if not ports_weekly.empty and {"latitude", "longitude"}.issubset(ports_weekly.columns):
        pw = in_range(ports_weekly, "week")
        pcol = port_value_col()
        agg = (pw.groupby(["portid", "portname", "country", "latitude", "longitude"],
                          as_index=False)[pcol].mean())
        agg = agg[agg[pcol] > 0].nlargest(600, pcol)

        fig = px.scatter_geo(
            agg,
            lat="latitude",
            lon="longitude",
            size=pcol,
            hover_name="portname",
            hover_data={"country": True, pcol: ":.0f",
                        "latitude": False, "longitude": False},
            size_max=26,
            projection="natural earth",
        )
        fig.update_traces(marker=dict(color=T.HIGHLIGHT_2, opacity=0.62,
                                      line=dict(width=0)))
        T.titled(
            fig,
            "Global port activity concentrates in a handful of corridors",
            f"Mean weekly {cargo_label.lower()} calls per port, "
            f"{date_range[0]:%b %Y}–{date_range[1]:%b %Y} · 600 busiest ports shown",
            "Source: IMF PortWatch",
        )
        fig.update_layout(height=520)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Port coordinates unavailable — check data/raw/ports_reference.csv.")

    st.markdown("#### Total transits across all chokepoints")
    ts = (cp_f.groupby("date", as_index=False)[vcol].sum())
    ts["smoothed"] = D.smooth(ts[vcol], smoothing)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ts["date"], y=ts[vcol], mode="lines",
                             line=dict(color=T.CONTEXT_LIGHT, width=1),
                             name="Daily", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=ts["date"], y=ts["smoothed"], mode="lines",
                             line=dict(color=T.HIGHLIGHT, width=2.4),
                             name=f"{smoothing}-day average"))
    apply_events(fig)
    T.titled(fig,
             "Aggregate transit volume is resilient — the disruption shows up in the routing, not the total",
             f"All 28 chokepoints combined · {cargo_label.lower()}",
             "Source: IMF PortWatch")
    fig.update_layout(height=420, showlegend=True)
    st.plotly_chart(fig, use_container_width=True)


# --------------------------------------------------------------------------
# Tab 2 - Chokepoints
# --------------------------------------------------------------------------
with tab2:
    st.subheader("Chokepoint comparison")
    st.markdown(
        "<p class='caption'>Series are indexed so each chokepoint's own "
        "pre-crisis average = 100. Suez handles far more traffic than the "
        "Bosporus, so raw volumes would hide the proportional shock.</p>",
        unsafe_allow_html=True,
    )

    names = sorted(cp["chokepoint"].dropna().unique())
    defaults = [n for n in names
                if any(k in n.lower() for k in
                       ("suez", "good hope", "panama", "bab"))][:4]
    chosen = st.multiselect("Chokepoints to compare", names,
                            default=defaults or names[:4])

    if chosen:
        sub = cp_f[cp_f["chokepoint"].isin(chosen)].copy()
        sub = (sub.groupby(["date", "chokepoint"], as_index=False)[vcol].sum()
               .sort_values("date"))
        sub[vcol] = (sub.groupby("chokepoint")[vcol]
                     .transform(lambda s: D.smooth(s, smoothing)))

        base_lo = max(pd.Timestamp(date_range[0]), pd.Timestamp("2023-01-01"))
        base_hi = base_lo + pd.Timedelta(days=180)
        sub = D.index_to_baseline(sub, vcol, "chokepoint", "date",
                                  (str(base_lo.date()), str(base_hi.date())))

        fig = go.Figure()
        for i, name in enumerate(chosen):
            d = sub[sub["chokepoint"] == name]
            is_focus = "suez" in name.lower()
            fig.add_trace(go.Scatter(
                x=d["date"], y=d[f"{vcol}_idx"], mode="lines", name=name,
                line=dict(color=T.HIGHLIGHT if is_focus else T.CATEGORICAL[i % len(T.CATEGORICAL)],
                          width=2.6 if is_focus else 1.8),
            ))
        fig.add_hline(y=100, line=dict(color=T.CONTEXT, width=1, dash="dot"))
        apply_events(fig)
        T.titled(fig,
                 "Traffic did not disappear — it relocated",
                 f"Transit calls indexed to each chokepoint's {base_lo:%b %Y}–{base_hi:%b %Y} average = 100",
                 "Source: IMF PortWatch")
        fig.update_layout(height=470, yaxis_title="Index (baseline = 100)")
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Cargo mix at a single chokepoint")
        one = st.selectbox("Chokepoint", chosen, index=0)
        d1 = cp_f[cp_f["chokepoint"] == one]
        long = D.to_long_cargo(d1, "n", ["date"])
        long = (long.groupby(["date", "cargo"], as_index=False)["value"].sum()
                .sort_values("date"))
        long["value"] = (long.groupby("cargo")["value"]
                         .transform(lambda s: D.smooth(s, max(smoothing, 7))))

        fig = px.area(long, x="date", y="value", color="cargo",
                      color_discrete_sequence=T.CATEGORICAL)
        fig.update_traces(line=dict(width=0.5))
        apply_events(fig)
        T.titled(fig,
                 f"Cargo composition at {one} shifts as well as its volume",
                 f"{smoothing}-day smoothed daily transit calls by vessel class",
                 "Source: IMF PortWatch")
        fig.update_layout(height=420, yaxis_title="Transit calls")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Select at least one chokepoint.")


# --------------------------------------------------------------------------
# Tab 3 - Ports
# --------------------------------------------------------------------------
with tab3:
    st.subheader("Winners and losers at port level")

    if ports_weekly.empty:
        st.info("ports_weekly.parquet not found — run scripts/build_dashboard_data.py.")
    else:
        pcol = port_value_col()
        pw = ports_weekly.copy()

        c1, c2 = st.columns(2)
        with c1:
            before = st.date_input(
                "Baseline window",
                value=(pd.Timestamp("2023-01-01").date(),
                       pd.Timestamp("2023-10-01").date()),
                key="before",
            )
        with c2:
            after = st.date_input(
                "Comparison window",
                value=(pd.Timestamp("2024-01-01").date(),
                       pd.Timestamp("2024-10-01").date()),
                key="after",
            )

        if len(before) == 2 and len(after) == 2:
            changes = D.pct_change_between(
                pw, pcol, "portname", "week",
                (str(before[0]), str(before[1])),
                (str(after[0]), str(after[1])),
                min_base=5.0,
            )
            n = st.slider("Ports to show per side", 5, 25, 12)
            top = pd.concat([changes.head(n), changes.tail(n)]).drop_duplicates("portname")
            top = top.sort_values("pct_change")

            fig = go.Figure(go.Bar(
                x=top["pct_change"],
                y=top["portname"],
                orientation="h",
                marker=dict(
                    color=top["pct_change"],
                    colorscale=[[0.0, T.HIGHLIGHT_2], [0.5, "#F2F2F2"],
                                [1.0, T.HIGHLIGHT]],
                    cmid=0,
                    line=dict(width=0),
                ),
                hovertemplate="<b>%{y}</b><br>%{x:+.1f}%<extra></extra>",
            ))
            fig.add_vline(x=0, line=dict(color=T.INK_SOFT, width=1))
            T.titled(fig,
                     "Rerouting produced clear winners and clear losers",
                     f"Change in mean weekly {cargo_label.lower()} calls, "
                     f"{after[0]:%b %Y}–{after[1]:%b %Y} vs {before[0]:%b %Y}–{before[1]:%b %Y}",
                     "Source: IMF PortWatch")
            fig.update_layout(height=28 * len(top) + 190,
                              xaxis_title="Change (%)", yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("See the underlying numbers"):
                st.dataframe(
                    top[["portname", "before", "after", "pct_change"]]
                    .rename(columns={"portname": "Port", "before": "Baseline",
                                     "after": "Comparison", "pct_change": "Change %"})
                    .round(1),
                    use_container_width=True, hide_index=True,
                )

        st.markdown("#### Track individual ports")
        picks = st.multiselect(
            "Ports",
            sorted(pw["portname"].dropna().unique()),
            default=list(pw.groupby("portname")[pcol].sum().nlargest(3).index),
        )
        if picks:
            d = in_range(pw[pw["portname"].isin(picks)], "week")
            d = d.groupby(["week", "portname"], as_index=False)[pcol].sum()
            fig = px.line(d, x="week", y=pcol, color="portname",
                          color_discrete_sequence=T.CATEGORICAL)
            fig.update_traces(line=dict(width=2.1))
            apply_events(fig)
            T.titled(fig, "Individual port trajectories diverge sharply",
                     f"Weekly {cargo_label.lower()} calls",
                     "Source: IMF PortWatch")
            fig.update_layout(height=430, yaxis_title="Weekly calls", xaxis_title="")
            st.plotly_chart(fig, use_container_width=True)


# --------------------------------------------------------------------------
# Tab 4 - Resilience
# --------------------------------------------------------------------------
with tab4:
    st.subheader("Concentration and exposure")

    if not ports_weekly.empty:
        pcol = port_value_col()
        pw = ports_weekly.copy()
        pw["year"] = pw["week"].dt.year
        hhi = []
        for yr, grp in pw.groupby("year"):
            shares = grp.groupby("portid")[pcol].sum()
            shares = shares[shares > 0]
            if len(shares) > 10:
                hhi.append({"year": yr, "hhi": D.herfindahl(shares),
                            "top20": 100 * shares.nlargest(20).sum() / shares.sum()})
        hhi = pd.DataFrame(hhi)

        if not hhi.empty:
            fig = go.Figure(go.Scatter(
                x=hhi["year"], y=hhi["top20"], mode="lines+markers",
                line=dict(color=T.HIGHLIGHT, width=2.6),
                marker=dict(size=8, color=T.HIGHLIGHT),
            ))
            T.titled(fig,
                     "A small group of ports carries a large share of global traffic",
                     f"Share of all {cargo_label.lower()} calls handled by the 20 busiest ports",
                     "Source: IMF PortWatch")
            fig.update_layout(height=400, yaxis_title="Top-20 share (%)",
                              xaxis_title="")
            st.plotly_chart(fig, use_container_width=True)
            st.markdown(
                "<p class='caption'>Concentration is a fragility measure: the "
                "higher this line, the more global trade depends on a handful "
                "of nodes staying open.</p>",
                unsafe_allow_html=True,
            )

    if not country_monthly.empty:
        st.markdown("#### Country-level maritime activity")
        cm = in_range(country_monthly, "month")
        col = "portcalls" if "portcalls" in cm.columns else cm.columns[-1]
        agg = cm.groupby(["country", "ISO3"], as_index=False)[col].sum()

        fig = px.choropleth(
            agg, locations="ISO3", color=col, hover_name="country",
            color_continuous_scale=T.SEQUENTIAL, projection="natural earth",
        )
        T.titled(fig,
                 "Maritime activity maps onto a familiar set of trading economies",
                 f"Total port calls, {date_range[0]:%b %Y}–{date_range[1]:%b %Y}",
                 "Source: IMF PortWatch")
        fig.update_layout(height=500,
                          coloraxis_colorbar=dict(title="", thickness=12))
        st.plotly_chart(fig, use_container_width=True)


# --------------------------------------------------------------------------
# Tab 5 - Method
# --------------------------------------------------------------------------
with tab5:
    st.subheader("Method & sources")
    st.markdown(
        """
**Primary data — IMF PortWatch.** Daily port-call and trade-volume estimates
for 2,065 ports and daily transit counts for 28 major chokepoints, derived from
satellite AIS signals broadcast by roughly 90,000 vessels. Published by the
International Monetary Fund and updated weekly.

**What these numbers are.** Port calls are *observed vessel movements*. The
trade volumes are **model-based estimates** derived from vessel type, capacity
and draft — they are not customs records. They are excellent for measuring
*relative change over time*, and should be treated cautiously as absolute
trade values.

**Processing.**

- Daily series are smoothed with a centred rolling mean (default 7 days) to remove the weekly port-operations cycle without shifting turning points.
- Chokepoint comparisons are indexed to each chokepoint's own baseline period, because absolute volumes differ by an order of magnitude across passages.
- Port-level change compares mean weekly calls in two user-chosen windows, excluding ports below a minimum baseline so that very small ports don't generate meaningless percentage swings.
- The dashboard reads pre-aggregated parquet files rather than the raw CSVs, which keeps it inside Streamlit Community Cloud's memory limit.

**Event dates** shown as shaded bands are drawn from public reporting and are
provided as visual context, not as data.

**Design.** All figures use the Okabe–Ito palette, which remains
distinguishable under the common forms of colour vision deficiency. Context
series are muted grey; one highlight colour marks the focus of each chart.

**Attribution.** IMF PortWatch, portwatch.imf.org — International Monetary Fund.
        """
    )
    st.markdown("---")
    c1, c2 = st.columns(2)
    c1.markdown("**Source data:** [portwatch.imf.org](https://portwatch.imf.org/)")
    c2.markdown("**Repository:** add your GitHub URL here")
