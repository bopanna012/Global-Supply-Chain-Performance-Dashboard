"""
Shared visual identity for the whole project.

Every figure in the notebook and the dashboard goes through this module, so the
palette, typography and decluttering rules are identical everywhere.

Design rules encoded here (from the course brief):
  - CVD-safe palette (Okabe-Ito, the standard safe-for-all-colour-vision set)
  - Muted grey for context, ONE highlight colour for focus
  - No gridlines, no chart junk, no redundant ink
  - Clean white background, clear visual hierarchy
  - Titles state the takeaway, not the variables
"""

from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

# --------------------------------------------------------------------------
# Palette - Okabe & Ito (2008), distinguishable under all common forms of
# colour vision deficiency. Do not add colours outside this set.
# --------------------------------------------------------------------------
OKABE_ITO = {
    "orange": "#E69F00",
    "sky": "#56B4E9",
    "green": "#009E73",
    "yellow": "#F0E442",
    "blue": "#0072B2",
    "vermillion": "#D55E00",
    "purple": "#CC79A7",
    "black": "#000000",
}

# Qualitative sequence - ordered so the first few are maximally distinct
CATEGORICAL = [
    OKABE_ITO["blue"],
    OKABE_ITO["vermillion"],
    OKABE_ITO["green"],
    OKABE_ITO["orange"],
    OKABE_ITO["purple"],
    OKABE_ITO["sky"],
    OKABE_ITO["yellow"],
]

# The single highlight colour. Use sparingly - one series per chart.
HIGHLIGHT = OKABE_ITO["vermillion"]
# Secondary highlight, only when a chart genuinely needs two focal series.
HIGHLIGHT_2 = OKABE_ITO["blue"]
# Everything that is context rather than the point of the chart.
CONTEXT = "#BDBDBD"
CONTEXT_LIGHT = "#E0E0E0"

INK = "#2B2B2B"       # primary text
INK_SOFT = "#6B6B6B"  # secondary text, axis labels
BACKGROUND = "#FFFFFF"

# Diverging scale for gain/loss maps and bars (blue <-> vermillion, CVD-safe)
DIVERGING = [
    [0.0, OKABE_ITO["blue"]],
    [0.5, "#F2F2F2"],
    [1.0, OKABE_ITO["vermillion"]],
]

# Sequential scale, single-hue so it reads correctly in greyscale too
SEQUENTIAL = ["#EAF2F8", "#A9CCE3", "#5499C7", "#1F618D", "#0B3C5D"]

FONT = "Inter, Segoe UI, Helvetica Neue, Arial, sans-serif"


def _build_template() -> go.layout.Template:
    """The single Plotly template used by every figure in the project."""
    return go.layout.Template(
        layout=go.Layout(
            font=dict(family=FONT, size=13, color=INK),
            title=dict(
                font=dict(size=19, color=INK),
                x=0,
                xanchor="left",
                y=0.96,
                yanchor="top",
                pad=dict(b=12),
            ),
            paper_bgcolor=BACKGROUND,
            plot_bgcolor=BACKGROUND,
            colorway=CATEGORICAL,
            # Declutter: no vertical gridlines, whisper-light horizontal ones only
            xaxis=dict(
                showgrid=False,
                zeroline=False,
                showline=True,
                linecolor=CONTEXT_LIGHT,
                linewidth=1,
                ticks="outside",
                tickcolor=CONTEXT_LIGHT,
                ticklen=4,
                tickfont=dict(size=12, color=INK_SOFT),
                title=dict(font=dict(size=12, color=INK_SOFT)),
                automargin=True,
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor="#F2F2F2",
                gridwidth=1,
                zeroline=False,
                showline=False,
                ticks="",
                tickfont=dict(size=12, color=INK_SOFT),
                title=dict(font=dict(size=12, color=INK_SOFT)),
                automargin=True,
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="left",
                x=0,
                bgcolor="rgba(0,0,0,0)",
                borderwidth=0,
                font=dict(size=12, color=INK_SOFT),
                title=dict(text=""),
            ),
            margin=dict(l=70, r=40, t=95, b=60),
            hoverlabel=dict(
                bgcolor="white",
                bordercolor=CONTEXT_LIGHT,
                font=dict(family=FONT, size=12, color=INK),
            ),
            colorscale=dict(sequential=SEQUENTIAL, diverging=DIVERGING),
            geo=dict(
                bgcolor=BACKGROUND,
                landcolor="#F5F5F5",
                lakecolor=BACKGROUND,
                oceancolor=BACKGROUND,
                showocean=True,
                showcountries=True,
                countrycolor="#E4E4E4",
                coastlinecolor="#DCDCDC",
                showframe=False,
            ),
        )
    )


pio.templates["supplychain"] = _build_template()
pio.templates.default = "supplychain"

TEMPLATE = "supplychain"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def titled(fig: go.Figure, takeaway: str, subtitle: str = "", source: str = "") -> go.Figure:
    """
    Apply a takeaway-first title.

    `takeaway` should be a sentence stating the finding ("Suez transits fell 68%
    within eight weeks"), NOT a description of the axes ("Transits over time").
    """
    title = f"<b>{takeaway}</b>"
    if subtitle:
        title += f"<br><span style='font-size:13px;color:{INK_SOFT}'>{subtitle}</span>"
    fig.update_layout(title=dict(text=title))
    if subtitle:
        fig.update_layout(margin=dict(t=115))
    if source:
        add_source(fig, source)
    return fig


def add_source(fig: go.Figure, text: str) -> go.Figure:
    """Small source credit in the bottom-left, outside the plotting area."""
    fig.add_annotation(
        text=f"<span style='font-size:11px;color:{INK_SOFT}'>{text}</span>",
        xref="paper",
        yref="paper",
        x=0,
        y=-0.16,
        showarrow=False,
        xanchor="left",
        yanchor="top",
    )
    return fig


def annotate(fig: go.Figure, x, y, text: str, ax: int = 30, ay: int = -40,
             color: str = HIGHLIGHT) -> go.Figure:
    """Direct annotation on the figure - preferred over a legend entry."""
    fig.add_annotation(
        x=x,
        y=y,
        text=f"<span style='color:{color}'>{text}</span>",
        showarrow=True,
        arrowhead=0,
        arrowwidth=1.2,
        arrowcolor=color,
        ax=ax,
        ay=ay,
        font=dict(size=12, color=color),
        align="left",
        bgcolor="rgba(255,255,255,0.85)",
        borderpad=3,
    )
    return fig


def event_band(fig: go.Figure, x0, x1, label: str = "", y: float = 1.0) -> go.Figure:
    """Shade a period of interest (e.g. the Red Sea crisis) behind the data."""
    fig.add_vrect(
        x0=x0,
        x1=x1,
        fillcolor=CONTEXT,
        opacity=0.16,
        layer="below",
        line_width=0,
    )
    if label:
        fig.add_annotation(
            x=x0,
            xref="x",
            y=y,
            yref="paper",
            text=f"<span style='font-size:11px;color:{INK_SOFT}'>{label}</span>",
            showarrow=False,
            xanchor="left",
            yanchor="bottom",
            xshift=4,
        )
    return fig


def emphasise(n: int, focus_index: int | list[int]) -> list[str]:
    """
    Return a colour list of length `n` where only `focus_index` is highlighted
    and everything else is muted grey. This is the muted-context + one-highlight
    rule expressed in code.
    """
    focus = {focus_index} if isinstance(focus_index, int) else set(focus_index)
    palette = [HIGHLIGHT, HIGHLIGHT_2, OKABE_ITO["green"]]
    out, k = [], 0
    for i in range(n):
        if i in focus:
            out.append(palette[k % len(palette)])
            k += 1
        else:
            out.append(CONTEXT)
    return out
