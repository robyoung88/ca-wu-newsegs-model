"""
The colour scheme of the app: the single source of its colours, in the UI and in plots.

The stylesheet takes these colours as CSS custom properties (`--ns-*`) and the configuration colour classes, which
`scripts/build_css.py` writes into `src/assets/newsegs.css`. After changing a colour here, rebuild the stylesheet with
`python scripts/build_css.py`; a unit test fails while it is out of date.

The scheme:

* The background is a cool off-white.
* Borders and accents are in the purple of ClwydAlyn housing association. It replaces Bootstrap's `primary`.
* Configurations (metamodels) each have a colour of the red-green part of the spectrum, starting with the red of
  Wrexham University, so that a configuration is recognised by its colour in every input, header and plot. Their
  lightness differs as well as their hue, so that they stay distinct for colour-blind users: the smallest CIEDE2000
  difference between two of them is about 10, with normal vision and simulated protanopia, deuteranopia and
  tritanopia.
* Anything else drawn in a plot (energy flows, bounds, bins) takes the cool colours of `SERIES_COLOURS` or
  `SEQUENTIAL_COLOURS`, never a configuration colour.

Plots use the `newsegs` Plotly template (`PLOT_TEMPLATE`), registered on import, which sets the text colour, the
grid and the colours of series. `set_default_plot_template` makes it the default of every figure.
"""

import plotly.graph_objects as go
import plotly.io as pio

# -----------------------------------------------
# UI
# -----------------------------------------------

BACKGROUND = '#F3F5F8'
"""Background of the page: a cool off-white."""

SURFACE = '#FFFFFF'
"""Background of cards, inputs and plots' boxes, on the page."""

TEXT = '#212529'
"""Body text."""

MUTED = '#6C757D'
"""Secondary text: hints, labels and headings of minor elements."""

BRAND = '#432461'
"""The purple of ClwydAlyn housing association: Bootstrap's `primary`, accents and emphasised borders."""

BRAND_MID = '#6A4C82'
"""A lighter purple, for hover and secondary accents."""

BRAND_SOFT = '#D9D2E0'
"""A pale purple: the colour of borders."""

BRAND_SUBTLE = '#EFEBF3'
"""The palest purple: the background of selected or highlighted elements."""

# -----------------------------------------------
# Configurations
# -----------------------------------------------

CONFIG_COLOURS = [
    '#E64550',  # Crimson, the red of Wrexham University
    '#034818',  # Forest
    '#C58B03',  # Gold
    '#01857F',  # Teal
    '#762D43',  # Wine
    '#B0501F',  # Burnt orange
    '#61A076',  # Green
    '#AAB167',  # Sage
]
"""Colours of the configurations (metamodels), in order: configuration n has colour n, modulo the length. The first
four are the most distinct, as most projects have few configurations."""

CONFIG_COLOUR_CLASSES = [f'config-colour-{i + 1}' for i in range(len(CONFIG_COLOURS))]
"""CSS classes setting the colour of text and icons to each configuration colour, in the order of `CONFIG_COLOURS`."""

def config_colour(index: int) -> str:
    """The colour of a configuration.

    Args:
        index: Index of the configuration, from 0.

    Returns:
        The colour, as a hex string.
    """
    return CONFIG_COLOURS[index % len(CONFIG_COLOURS)]

def config_colour_class(index: int) -> str:
    """The CSS class giving text and icons the colour of a configuration.

    Args:
        index: Index of the configuration, from 0.

    Returns:
        The class name.
    """
    return CONFIG_COLOUR_CLASSES[index % len(CONFIG_COLOUR_CLASSES)]

# -----------------------------------------------
# Status
# -----------------------------------------------

STATUS_OK = '#82FD45'
"""Up-to-date results (see `components/staleness.py`)."""

STATUS_WARNING = '#F3B248'
"""Results which may be out of date."""

STATUS_ERROR = '#E60233'
"""Out-of-date or failed results."""

# -----------------------------------------------
# Plots
# -----------------------------------------------

SERIES_COLOURS = [
    '#432461',  # Purple
    '#4F7CAC',  # Steel blue
    '#9C7BB8',  # Lavender
    '#1F3A5F',  # Navy
    '#8A94A6',  # Slate
    '#2E5E8C',  # Blue
    '#C6B4D8',  # Lilac
    '#3D3D4E',  # Charcoal
]
"""Colours of the series of a plot which are not configurations: blues, purples and greys, apart from the
configuration colours."""

SEQUENTIAL_COLOURS = ['#EDE5F4', '#D5C6E3', '#B7A3D0', '#9781BC', '#7563A2', '#534881', '#342F5B']
"""An ordered scale of purples, from light to dark, for binned quantities such as wind speeds."""

PLOT_NEUTRAL = '#8A94A6'
"""Reference lines and other context in a plot."""

PLOT_EMPHASIS = '#3D3D4E'
"""Lines and markers to stand out from the series of a plot, such as a frontier or a mean."""

PLOT_GRID = '#E4E7EC'
"""Grid lines of plots."""

PLOT_TEMPLATE = 'newsegs'
"""The name of the Plotly template of the app's plots, layered on `plotly_white`."""

pio.templates[PLOT_TEMPLATE] = go.layout.Template(
    layout = dict(
        colorway = SERIES_COLOURS,
        font = dict(color = TEXT),
        xaxis = dict(gridcolor = PLOT_GRID, zerolinecolor = PLOT_GRID, linecolor = PLOT_GRID),
        yaxis = dict(gridcolor = PLOT_GRID, zerolinecolor = PLOT_GRID, linecolor = PLOT_GRID),
        polar = dict(
            angularaxis = dict(gridcolor = PLOT_GRID, linecolor = PLOT_GRID),
            radialaxis = dict(gridcolor = PLOT_GRID, linecolor = PLOT_GRID),
        ),
    )
)

PLOT_TEMPLATES = f'plotly_white+{PLOT_TEMPLATE}'
"""`plotly_white` with the `newsegs` template over it: the value of a figure's `template`."""

def rgba(colour: str, alpha: float) -> str:
    """A colour with transparency, as Plotly and CSS take it.

    Args:
        colour: The colour, as a hex string (`#RRGGBB`).
        alpha: Its opacity, from 0 (transparent) to 1.

    Returns:
        The colour, as `rgba(r, g, b, alpha)`.
    """
    return f'rgba({_rgb(colour)}, {alpha:g})'

def set_default_plot_template():
    """Make `PLOT_TEMPLATES` the default template of Plotly figures, including those of Plotly Express."""
    pio.templates.default = PLOT_TEMPLATES

# -----------------------------------------------
# CSS
# -----------------------------------------------

def _rgb(colour: str) -> str:
    return ', '.join(str(int(colour[i:i + 2], 16)) for i in (1, 3, 5))

def css_tokens() -> str:
    """The colours as CSS: the custom properties on `:root`, and the configuration colour classes.

    Written into the stylesheet by `scripts/build_css.py`.

    Returns:
        The CSS.
    """
    tokens = {
        'bg': BACKGROUND,
        'surface': SURFACE,
        'text': TEXT,
        'muted': MUTED,
        'brand': BRAND,
        'brand-mid': BRAND_MID,
        'brand-soft': BRAND_SOFT,
        'brand-subtle': BRAND_SUBTLE,
        'status-ok': STATUS_OK,
        'status-warning': STATUS_WARNING,
        'status-error': STATUS_ERROR,
        **{f'config-{i + 1}': c for i, c in enumerate(CONFIG_COLOURS)},
    }
    lines = ['/* The colours of components/colours.py */', ':root {']
    lines += [f'    --ns-{k}: {v};' for k, v in tokens.items()]
    lines += [f'    --ns-brand-rgb: {_rgb(BRAND)};', f'    --ns-brand-mid-rgb: {_rgb(BRAND_MID)};', '}', '']
    # Utilities, as Bootstrap's text colours which they replace
    for i, cls in enumerate(CONFIG_COLOUR_CLASSES):
        lines.append(f'.{cls} {{ color: var(--ns-config-{i + 1}) !important; }}')
    return '\n'.join(lines) + '\n'
