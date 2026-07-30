# Project plan — Global Supply Chain Performance

**Course:** Data Visualization, Summer 2026 · **Deadline:** Friday 31 July 2026

---

## The story in one sentence

Between 2023 and 2024 two of the world's four critical maritime chokepoints
constricted at the same time — the Red Sea to conflict, the Panama Canal to
drought — and the satellite record shows exactly how global shipping absorbed
it, which routes took the strain, and which economies recovered fastest.

That is the spine. Every question below either builds the setup, quantifies the
shock, or answers *who coped*.

---

## Dataset

**Primary — IMF PortWatch** (portwatch.imf.org). Daily port-call and trade
volume estimates for **2,065 ports**, plus daily transit data for **28 major
chokepoints**, derived from satellite AIS signals off ~90,000 ships. Published
by the IMF, free to use with attribution.

Four attribute types in one source, which is exactly what Step 1 of the brief asks for:

| Type | Columns |
|---|---|
| Temporal | `date`, `year`, `month`, `day` — daily, 2019→present |
| Spatial | port coordinates, `country`, `ISO3`, 28 named chokepoints |
| Categorical | 5 cargo classes, systemic-importance class (global / regional / domestic) |
| Numerical | port calls, import/export volume, transit capacity |

**Secondary joins** (all optional but each adds a dimension the primary source lacks):

| Source | What it adds | Where |
|---|---|---|
| World Bank LPI | Logistics quality per country, 6 sub-scores | lpi.worldbank.org |
| UNCTAD Port LSCI | Liner-network connectivity per port, quarterly | unctadstat.unctad.org |
| NY Fed GSCPI | Monthly global supply-chain pressure index | newyorkfed.org/research/policy/gscpi |

> Merging sources is explicitly called out as a plus in the brief. Even one
> join (LPI is the easiest — a single spreadsheet keyed on country) lifts the
> dataset-selection score.

---

## The 10 analytical questions

Each is multi-dimensional: it relates variables, compares groups, or tracks
change across time or space. None is a value count or a single-variable
distribution.

### Act I — Setting the scene

**Q1. How did daily transit volumes at Suez, Bab el-Mandeb and the Cape of Good Hope diverge after October 2023, and did the gain at the Cape offset the loss at Suez?**

- *Chart:* multi-line time series, 7-day smoothed, indexed to a 2023 baseline = 100
- *Design:* Suez in the highlight colour, all other chokepoints muted grey; shaded event band over the crisis period; direct annotation on the divergence point
- *Insight to land:* the volume didn't vanish, it moved — and the offset is visibly incomplete
- *Helpers:* `index_to_baseline()`, `event_band()`, `annotate()`

**Q2. Did rerouting hit all cargo types equally, or did container traffic retreat from the Red Sea faster than tankers and dry bulk?**

- *Chart:* small multiples (one facet per cargo type), each showing Suez transit indexed to baseline
- *Design:* identical y-scales across facets so the comparison is honest; highlight the steepest facet
- *Insight:* container lines (schedule-driven, high-value cargo, reputational risk) move first; tankers are stickier
- *Helpers:* `to_long_cargo()`, `index_to_baseline()`

**Q3. Which of the 28 chokepoints were most volatile between 2019 and 2026, and does volatility cluster geographically?**

- *Chart:* horizontal lollipop ranked by coefficient of variation, coloured by region
- *Design:* top 3 highlighted, the rest grey; direct labels instead of a legend
- *Insight:* volatility is not evenly distributed — it concentrates in politically exposed passages

### Act II — The shock

**Q4. Did the Panama drought and the Red Sea crisis compound each other, or did traffic substitute between the two routes?**

- *Chart:* dual time series with a connected-scatter inset of daily deviations from baseline
- *Design:* one colour per chokepoint, shaded bands for both disruption windows
- *Insight:* two simultaneous constraints on the two main Asia↔US-East-Coast options — this is the crux of the story
- *Helpers:* `smooth()`, `event_band()`

**Q5. Which individual ports gained and lost the most container traffic after the Red Sea disruption, and where are they?**

- *Chart:* diverging horizontal bar (top 15 gainers / 15 losers) **plus** a `scatter_geo` world map sized by absolute change and coloured on the diverging scale
- *Design:* diverging CVD-safe scale (blue ↔ vermillion), zero line emphasised, direct value labels
- *Insight:* named winners and losers — this is the most quotable chart in the deck
- *Helpers:* `pct_change_between()`

**Q6. How concentrated is global container traffic, and has concentration risen or fallen since 2019?**

- *Chart:* HHI (or top-20 share) as a line over time, with a Lorenz-style inset for the first and last year
- *Design:* single highlighted line, annotated turning points
- *Insight:* speaks directly to supply-chain fragility — concentration means single points of failure
- *Helpers:* `herfindahl()`

### Act III — Who coped

**Q7. Do countries with higher World Bank LPI scores recover port-call volumes faster after disruption?**

- *Chart:* scatter — LPI score (x) vs recovery half-life in days (y) — bubble size = port calls, colour = region, with trendline
- *Design:* label only the notable outliers, not all 160 countries
- *Insight:* the payoff question — does logistics quality actually buy resilience?
- *Helpers:* `recovery_half_life()`
- *Caveat to state honestly:* this is correlation across a small n, not a causal claim

**Q8. Which economies are most exposed to a single chokepoint — whose maritime trade funnels through one narrow passage?**

- *Chart:* choropleth of a single-chokepoint exposure index, plus a ranked bar of the top 15
- *Design:* sequential single-hue scale (safe in greyscale), muted basemap
- *Insight:* exposure is a structural property, independent of whether a crisis is currently happening

**Q9. Is there a weekly rhythm to port activity, and does it differ between globally systemic and domestically systemic ports?**

- *Chart:* heatmap, day-of-week × port class, values = mean calls indexed to each class's own weekly mean
- *Design:* diverging scale centred on 100; annotate the strongest cell
- *Insight:* global hubs run closer to 24/7; domestic ports keep office hours — an operational-tempo difference visible in satellite data
- *Helpers:* `add_calendar()`

**Q10. Does the NY Fed's GSCPI lead or lag the physically observable disruption in the AIS data?**

- *Chart:* standardised dual-line overlay, plus a small lagged cross-correlation bar chart
- *Design:* GSCPI in grey as context, physical chokepoint measure in the highlight colour
- *Insight:* closes the loop — does a widely watched economic index actually track the ships, and by how many weeks?
- *Caveat:* GSCPI is monthly, the AIS data daily — resample before correlating, and say so

**Q11 (spare / bonus). Did the disruptions leave a measurable imprint on the import–export balance of the most affected economies?**

- *Chart:* slope chart, pre-crisis vs post-crisis, one line per country
- Keep this in reserve in case one of the ten above turns out thin.

---

## Deliverable mapping

| Brief requirement | Where it lives |
|---|---|
| Jupyter notebook, EDA + 10 questions, Plotly only | `notebooks/analysis.ipynb` |
| PDF/HTML export of the notebook | `jupyter nbconvert --to html` |
| Dataset file or link | `data/raw/` + source links in README |
| Presentation, exported to PDF | build from the exported figures |
| Streamlit dashboard, deployed | `app.py` → Community Cloud |
| Public GitHub repo | this repo |

---

## Two-day schedule

**Wednesday evening**

1. `python scripts/download_data.py` — start it and let it run, the ports file is large
2. Skim the notebook's EDA section; confirm date coverage and missing-value patterns
3. Lock Q1, Q2, Q4 — the chokepoint questions are the fastest to produce and they carry the story

**Thursday morning**

4. Q3, Q5, Q6 — the port-level questions; Q5 is your headline chart, give it the most polish
5. Download the World Bank LPI spreadsheet, join on ISO3, do Q7

**Thursday afternoon**

6. Q8, Q9, Q10; write the takeaway title for every figure — this is where the design marks are
7. `python scripts/build_dashboard_data.py`, then `streamlit run app.py` locally

**Thursday evening**

8. Push to GitHub, deploy on Community Cloud, screenshot the live dashboard
9. Build the slide deck from the exported figures; embed the dashboard URL

**Friday morning**

10. Export the notebook to HTML, export the deck to PDF, final check against the brief's checklist, submit on Teams

> Deadline discipline: if you are behind on Thursday evening, cut Q9 and Q10
> before you cut polish. Ten mediocre charts score worse than eight excellent
> ones plus the spare question — but do keep the count at ten if you can.

---

## Grading notes

The brief weights **Methods / Ideas / Procedure at 40%** — more than correctness
and polish combined. So in the notebook, write the *reasoning* in markdown
before each chart: why this question matters, what you expected, what you
actually found, and what the chart cannot tell you. That prose is the single
highest-leverage thing in this project.

Two more easy marks:

- **Every title states a takeaway.** "Suez transits fell 68% in eight weeks" beats "Suez transits over time". Do this for all ten.
- **Say what the data can't do.** PortWatch volumes are *estimates* derived from AIS signals, not customs records. Acknowledging that reads as rigour, not weakness.
