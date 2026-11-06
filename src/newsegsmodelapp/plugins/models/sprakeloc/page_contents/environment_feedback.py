"""Feedback on the environmental conditions of a site for the `sprakeloc` model type.

The data are those that a run of the focussed configuration uses (see `SiteConfiguration`): its
run period, and the heights of its wind turbine and PV array. They are fetched once for both, so
that a run after the feedback fetches nothing, and the feedback after a run fetches only what the
run did not.

The data source fetches, for a site:

- the hourly wind speeds and directions at the turbine height, from NEWA;
- the hourly wind speeds at the height of the PV array, which runs use, from NEWA;
- the hourly external temperature (with the horizontal solar flux), from PVGIS;
- the hourly global solar flux on planes at `PV_PITCH` facing each of `PV_AZIMUTHS`, from PVGIS;
- the horizon, from PVGIS.

The artists draw a wind rose, the distribution of the wind speeds, a sun path diagram, the monthly
external temperature (with those of the other sites of the project whose data are cached), and a
table of the specific generation potential.
"""
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from dash import dcc, html
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pvlib

from newsegsmodelapp import registers
from newsegsmodelapp.components import colours
from newsegsmodelapp.components.feedback.environmental_conditions import EnvironmentFeedbackItem
import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc
from newsegsmodelframework.core import generation
from newsegsmodelframework.core.location.location import AspectLocation, Location, RaisedLocation
from newsegsmodelframework.core.timespan.timespan import TimeSpan
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsmodel import sprakelocmodel

_MODEL_TYPE = 'sprakeloc'

PV_PITCH = 35.
"""Pitch (degrees from horizontal) of the planes of the PV generation potential."""
PV_AZIMUTHS = {'East': 90., 'South-east': 135., 'South': 180., 'South-west': 225., 'West': 270.}
"""Azimuths (degrees clockwise from north) of the planes of the PV generation potential."""
PV_PERFORMANCE_RATIO = 0.8
"""Ratio of the energy of a PV array to that of the flux on its plane at its rated efficiency."""

WIND_ROSE_SECTORS = 16
WIND_ROSE_SPEED_BINS = [0, 3, 6, 9, 12, 18, 24, 50]

ITEMS = [
    EnvironmentFeedbackItem('wind-rose', 6),
    EnvironmentFeedbackItem('wind-speed-distribution', 6),
    EnvironmentFeedbackItem('sun-path', 6),
    EnvironmentFeedbackItem('external-temperature', 6),
    EnvironmentFeedbackItem('generation-potential', 12),
]
"""The items of environmental feedback, in order."""

_LAYOUT = dict(
    height = 400,
    margin = {'l': 50, 'r': 20, 't': 40, 'b': 40},
    title = {
        'x': 0.5,
        'xanchor': 'center',
        'yanchor': 'top',
        'font': {'size': 13, 'family': 'Arial', 'color': colours.TEXT, 'weight': 'bold'}
    },
    template = colours.PLOT_TEMPLATES,
    paper_bgcolor = 'rgba(0,0,0,0)',
    plot_bgcolor = 'rgba(0,0,0,0)',
    legend = {'font': {'size': 10}},
)

# A horizontal legend below the plot, so that it does not cover the plot or its annotation
_LEGEND_BELOW = dict(orientation = 'h', x = 0.5, xanchor = 'center', y = -0.2, yanchor = 'top', font = {'size': 10})

_GRAPH_STYLE = {
    'border': '1px solid var(--bs-border-color)',
    'borderRadius': '0.5rem',
    'backgroundColor': 'transparent',
}

def _server():
    return sprakelocmodel.get_sprakeloc_environment_server()

@dataclass
class SiteConfiguration:
    """What the data of a configuration depend on, other than its location.

    Attributes:
        timespan: The run period.
        turbine_height: Height (m) of the wind turbine.
        pv_height: Height (m) of the PV array, at which runs use the wind speed.
        cp: Power coefficient of the wind turbine, as a function of the wind speed.
    """
    timespan: TimeSpan
    turbine_height: float
    pv_height: float
    cp: Callable[[Any], Any]

    @classmethod
    def from_metamodel(cls, metamodel: NewsegsMetaModel) -> 'SiteConfiguration':
        """The configuration of a metamodel of the `sprakeloc` model type.

        Raises:
            ValueError: if the metamodel has no wind turbine or no PV array.
        """
        model = metamodel.model
        plants = model.generation.generator.generators # pyright: ignore[reportAttributeAccessIssue]
        wind = next((x for x in plants if isinstance(x, generation.PowerPlantHomogeneousWind)), None)
        pv = next((x for x in plants if isinstance(x, generation.PowerPlantHomogeneousPV)), None)
        if wind is None or pv is None:
            raise ValueError(f'Metamodel {metamodel.id} has no wind turbine or no PV array')
        return cls(
            timespan = model.run_period, # pyright: ignore[reportAttributeAccessIssue]
            turbine_height = float(wind.location.height_agl),
            pv_height = float(pv.location.height_agl), # pyright: ignore[reportAttributeAccessIssue]
            cp = wind.turbine.cp,
        )

def _raised(location: Location, height: float) -> RaisedLocation:
    return RaisedLocation(location.lat, location.lon, height)

def _pv_locations(location: Location) -> dict[str, AspectLocation]:
    return {
        name: AspectLocation(location.lat, location.lon, height_agl = 2., azimuth = azimuth, pitch = PV_PITCH)
        for name, azimuth in PV_AZIMUTHS.items()
    }

def _point(location: Location) -> Location:
    return Location(location.lat, location.lon)

def _requirements(location: Location, config: SiteConfiguration) -> list[tuple[str, Location, TimeSpan | None]]:
    """The measures, at their locations and time spans, of the feedback on a site."""
    timespan = config.timespan
    turbine = _raised(location, config.turbine_height)
    return [
        ('wind_speeds', turbine, timespan),
        ('wind_directions', turbine, timespan),
        # Not shown, but used by runs
        ('wind_speeds', _raised(location, config.pv_height), timespan),
        ('external_temperature', _point(location), timespan),
        ('horizon', _point(location), None),
    ] + [
        ('solar_flux_on_plane', loc, timespan) for loc in _pv_locations(location).values()
    ]

class SprakeLocEnvironmentData:
    """The source of the environmental feedback data of the `sprakeloc` model type."""

    def is_available(self, location: Location, metamodel: NewsegsMetaModel) -> bool:
        server = _server()
        config = SiteConfiguration.from_metamodel(metamodel)
        return all(server.is_cached(*x) for x in _requirements(location, config))

    def is_pending(self, location: Location, metamodel: NewsegsMetaModel) -> bool:
        server = _server()
        config = SiteConfiguration.from_metamodel(metamodel)
        return any(server.is_pending(*x) for x in _requirements(location, config))

    def fetch(self, location: Location, metamodel: NewsegsMetaModel) -> None:
        server = _server()
        config = SiteConfiguration.from_metamodel(metamodel)
        timespan = config.timespan
        # The speeds are fetched with the directions
        server.get_wind_directions(_raised(location, config.turbine_height), timespan)
        server.get_wind_speeds(_raised(location, config.pv_height), timespan)
        server.get_external_temperature(_point(location), timespan)
        server.get_horizon(_point(location))
        server.get_solar_flux_on_plane(list(_pv_locations(location).values()), timespan)

registers.register_environment_data_source(SprakeLocEnvironmentData(), _MODEL_TYPE)

def _hourly(values, timespan: TimeSpan) -> pd.Series:
    """An hourly series of the values of a measure from the start of a time span."""
    values = np.asarray(values, dtype = float).ravel()
    return pd.Series(values, index = pd.date_range(timespan.start, periods = len(values), freq = 'h'))

def _n_years(series: pd.Series) -> float:
    return len(series) / (365.25 * 24.)

def _graph(figure: go.Figure) -> dcc.Graph:
    return dcc.Graph(figure = figure, config = {'displayModeBar': False}, style = _GRAPH_STYLE)

def _note(text: str, right: bool = False) -> dict:
    """A boxed annotation in the top left of a figure, or the top right."""
    return dict(
        text = text, xref = 'paper', yref = 'paper', x = 1. if right else 0., y = 1.,
        xanchor = 'right' if right else 'left', yanchor = 'top',
        showarrow = False, align = 'left', font = {'size': 11},
        bgcolor = 'rgba(255,255,255,0.85)', bordercolor = colours.BRAND_SOFT, borderwidth = 1, borderpad = 4,
    )

def _wind(location: Location, config: SiteConfiguration) -> tuple[pd.Series, pd.Series]:
    server = _server()
    timespan = config.timespan
    loc = _raised(location, config.turbine_height)
    return (
        _hourly(server.get_wind_speeds(loc, timespan), timespan),
        _hourly(server.get_wind_directions(loc, timespan), timespan),
    )

def annual_specific_wind_energy(speeds: pd.Series, air_density: float, cp: Callable[[Any], Any]) -> float:
    """Mean annual energy (kWh/m²) of a wind turbine per unit of its swept area.

    Args:
        speeds: Hourly wind speeds (m/s).
        air_density: Air density (kg/m³).
        cp: Power coefficient of the turbine, as a function of the wind speed.

    Returns:
        The energy.
    """
    power = 0.5 * air_density * cp(speeds.to_numpy()) * speeds.to_numpy()**3 / 1000.
    return float(np.sum(power) / _n_years(speeds))

def _air_density(location: Location, config: SiteConfiguration) -> float:
    return float(np.mean(_server().get_air_density(_raised(location, config.turbine_height), config.timespan)))

@registers.register_environment_feedback_artist('wind-rose', _MODEL_TYPE)
def draw_wind_rose(location: Location, sites: Sequence[tuple[str, Location]], metamodel: NewsegsMetaModel):
    """Wind rose at the turbine height: the proportion of time with wind from each direction, by
    wind speed, with the mean wind speed."""
    config = SiteConfiguration.from_metamodel(metamodel)
    speeds, directions = _wind(location, config)
    width = 360. / WIND_ROSE_SECTORS
    sector = np.floor(((directions.to_numpy() + width / 2.) % 360.) / width).astype(int)
    speed_bin = pd.cut(speeds, WIND_ROSE_SPEED_BINS, right = False)
    counts = (
        pd.crosstab(sector, speed_bin.to_numpy())
        .reindex(index = range(WIND_ROSE_SECTORS), fill_value = 0)
    )
    proportions = 100. * counts / len(speeds)

    fig = go.Figure()
    for colour, interval in zip(colours.SEQUENTIAL_COLOURS, speed_bin.cat.categories):
        if interval not in proportions.columns:
            continue
        fig.add_trace(go.Barpolar(
            r = proportions[interval].to_numpy(),
            theta = np.arange(WIND_ROSE_SECTORS) * width,
            width = width,
            name = f'{interval.left:g}–{interval.right:g} m/s',
            marker_color = colour,
            hovertemplate = '%{theta}°: %{r:.1f}%<extra>%{fullData.name}</extra>',
        ))
    fig.update_layout(
        **{**_LAYOUT, 'legend': {**_LEGEND_BELOW, 'y': -0.08}, 'margin': {'l': 30, 'r': 30, 't': 50, 'b': 30}},
        title_text = f'Wind rose at {config.turbine_height:g} m',
        polar = dict(
            angularaxis = dict(direction = 'clockwise', rotation = 90, tickvals = [0, 90, 180, 270], ticktext = ['N', 'E', 'S', 'W']),
            radialaxis = dict(ticksuffix = '%', angle = 22.5, tickangle = 22.5, nticks = 4, tickfont = {'size': 8}),
            bgcolor = 'rgba(0,0,0,0)',
        ),
        annotations = [_note(f'Mean wind speed<br><b>{speeds.mean():.1f} m/s</b>')],
    )
    return _graph(fig)

@registers.register_environment_feedback_artist('wind-speed-distribution', _MODEL_TYPE)
def draw_wind_speed_distribution(location: Location, sites: Sequence[tuple[str, Location]], metamodel: NewsegsMetaModel):
    """Distribution of the wind speeds at the turbine height, with the overall mean and the means
    of the lowest and highest years, and the annual specific energy of the turbine."""
    config = SiteConfiguration.from_metamodel(metamodel)
    speeds, _ = _wind(location, config)
    # Only whole years are compared
    counts = speeds.groupby(speeds.index.year).count()
    years = counts.index[counts >= 365 * 24]
    yearly = speeds[speeds.index.year.isin(years)].groupby(speeds.index.year[speeds.index.year.isin(years)]).mean()

    fig = go.Figure(go.Histogram(
        x = speeds.to_numpy(),
        xbins = dict(start = 0., end = float(np.ceil(speeds.max())) + 0.5, size = 0.5),
        histnorm = 'percent',
        marker_color = colours.SEQUENTIAL_COLOURS[2],
        name = 'Hours',
        hovertemplate = '%{x} m/s: %{y:.1f}% of hours<extra></extra>',
    ))
    lines = [('Mean', speeds.mean(), colours.PLOT_EMPHASIS, 'solid')]
    if len(yearly):
        lines += [
            (f'Lowest year ({yearly.idxmin()})', yearly.min(), colours.SERIES_COLOURS[1], 'dash'),
            (f'Highest year ({yearly.idxmax()})', yearly.max(), colours.SERIES_COLOURS[0], 'dash'),
        ]
    for name, value, colour, dash in lines:
        fig.add_trace(go.Scatter(
            x = [value, value], y = [0, 1], yaxis = 'y2', mode = 'lines',
            line = {'color': colour, 'dash': dash, 'width': 2},
            name = f'{name}: {value:.2f} m/s',
            hoverinfo = 'name',
        ))
    energy = annual_specific_wind_energy(speeds, _air_density(location, config), config.cp)
    fig.update_layout(
        **{**_LAYOUT, 'legend': {**_LEGEND_BELOW, 'y': -0.25}, 'margin': {**_LAYOUT['margin'], 'b': 90}},
        title_text = f'Wind speed at {config.turbine_height:g} m',
        xaxis = dict(title = 'Wind speed (m/s)'),
        yaxis = dict(title = 'Hours (%)'),
        yaxis2 = dict(overlaying = 'y', range = [0, 1], visible = False),
        # On the right, over the tail of the distribution
        annotations = [_note(f'Annual specific energy<br><b>{energy:,.0f} kWh/m²</b>', right = True)],
        bargap = 0.05,
    )
    return _graph(fig)

@registers.register_environment_feedback_artist('sun-path', _MODEL_TYPE)
def draw_sun_path(location: Location, sites: Sequence[tuple[str, Location]], metamodel: NewsegsMetaModel):
    """Sun path diagram: the elevation of the sun over the day at the solstices and equinox,
    with the horizon."""
    horizon = _server().get_horizon(_point(location)).sort_index()
    fig = go.Figure(go.Scatter(
        x = horizon.index.to_numpy(), y = horizon.to_numpy(),
        fill = 'tozeroy', mode = 'lines', line = {'color': colours.PLOT_NEUTRAL, 'width': 1},
        fillcolor = colours.rgba(colours.PLOT_NEUTRAL, 0.35), name = 'Horizon',
        hovertemplate = 'Azimuth %{x:.0f}°: %{y:.1f}°<extra>Horizon</extra>',
    ))
    year = pd.Timestamp.now().year
    days = [
        ('21 June', f'{year}-06-21', colours.SERIES_COLOURS[0]),
        ('20 March', f'{year}-03-20', colours.SERIES_COLOURS[2]),
        ('21 December', f'{year}-12-21', colours.SERIES_COLOURS[1]),
    ]
    for name, day, colour in days:
        times = pd.date_range(f'{day} 00:00', f'{day} 23:59', freq = '5min', tz = 'Europe/London')
        position = pvlib.solarposition.get_solarposition(times, location.lat, location.lon)
        up = position[position['apparent_elevation'] > 0.]
        fig.add_trace(go.Scatter(
            x = up['azimuth'], y = up['apparent_elevation'], mode = 'lines',
            line = {'color': colour, 'width': 2}, name = name,
            customdata = up.index.strftime('%H:%M'),
            hovertemplate = '%{customdata}: azimuth %{x:.0f}°, elevation %{y:.1f}°<extra>' + name + '</extra>',
        ))
        hours = up[up.index.minute == 0]
        fig.add_trace(go.Scatter(
            x = hours['azimuth'], y = hours['apparent_elevation'], mode = 'markers+text',
            marker = {'color': colour, 'size': 5}, text = hours.index.strftime('%H'),
            textposition = 'top center', textfont = {'size': 8}, showlegend = False, hoverinfo = 'skip',
        ))
    fig.update_layout(
        **{**_LAYOUT, 'legend': {**_LEGEND_BELOW, 'y': -0.25}, 'margin': {**_LAYOUT['margin'], 'b': 90}},
        title_text = 'Sun path (local time)',
        xaxis = dict(
            title = 'Azimuth', range = [0, 360],
            tickvals = [0, 45, 90, 135, 180, 225, 270, 315, 360],
            ticktext = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW', 'N'],
        ),
        yaxis = dict(title = 'Elevation (°)', range = [0, 70], rangemode = 'tozero'),
    )
    return _graph(fig)

def _monthly_temperature(location: Location, timespan: TimeSpan) -> pd.Series:
    temperature = _hourly(_server().get_external_temperature(_point(location), timespan), timespan)
    return temperature.groupby(temperature.index.month).mean()

_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

@registers.register_environment_feedback_artist('external-temperature', _MODEL_TYPE)
def draw_external_temperature(location: Location, sites: Sequence[tuple[str, Location]], metamodel: NewsegsMetaModel):
    """Monthly mean external temperature of the site, and of the other sites of the project whose
    data are cached; those of other sites are not fetched."""
    server = _server()
    timespan = SiteConfiguration.from_metamodel(metamodel).timespan
    fig = go.Figure()
    # The other sites in the colours of series other than the first, which is this site's
    others = colours.SERIES_COLOURS[1:]
    for i, (name, loc) in enumerate(sites):
        if not server.is_cached('external_temperature', _point(loc), timespan):
            continue
        monthly = _monthly_temperature(loc, timespan)
        fig.add_trace(go.Scatter(
            x = [_MONTHS[m - 1] for m in monthly.index], y = monthly.to_numpy(), mode = 'lines',
            line = {'width': 1.5, 'dash': 'dot', 'color': others[i % len(others)]}, opacity = 0.7, name = name,
            hovertemplate = '%{x}: %{y:.1f} °C<extra>' + name + '</extra>',
        ))
    monthly = _monthly_temperature(location, timespan)
    fig.add_trace(go.Scatter(
        x = [_MONTHS[m - 1] for m in monthly.index], y = monthly.to_numpy(), mode = 'lines+markers',
        line = {'width': 3, 'color': colours.SERIES_COLOURS[0]}, name = 'This site',
        hovertemplate = '%{x}: %{y:.1f} °C<extra>This site</extra>',
    ))
    timespan_years = f'{timespan.start.year}–{(timespan.end - pd.Timedelta(1, "s")).year}'
    fig.update_layout(
        **_LAYOUT,
        title_text = f'Mean external temperature, {timespan_years}',
        xaxis = dict(title = None),
        yaxis = dict(title = 'Temperature (°C)'),
    )
    return _graph(fig)

def generation_potential(location: Location, metamodel: NewsegsMetaModel) -> pd.DataFrame:
    """The specific generation potential of the site: the mean annual energy of the wind turbine
    of a configuration per unit of swept area, and of PV per unit of rated power on each plane.

    Args:
        location: Location of the site.
        metamodel: The configuration.

    Returns:
        A row for each generator, with its `Technology`, `Position`, `Annual production` and
        `Units`.
    """
    server = _server()
    config = SiteConfiguration.from_metamodel(metamodel)
    timespan = config.timespan
    speeds, _ = _wind(location, config)
    rows = [{
        'Technology': 'Wind',
        'Position': f'{config.turbine_height:g} m hub height',
        'Annual production': annual_specific_wind_energy(speeds, _air_density(location, config), config.cp),
        'Units': 'kWh/m² swept area',
    }]
    for name, loc in _pv_locations(location).items():
        flux = _hourly(server.get_solar_flux_on_plane(loc, timespan), timespan)
        # Flux (W/m²) over an hour is energy (Wh/m²); at 1 kW/m² a 1 kWp array is at its rating
        insolation = flux.sum() / 1000. / _n_years(flux)
        rows.append({
            'Technology': 'PV',
            'Position': f'{name}, {PV_PITCH:g}° pitch',
            'Annual production': insolation * PV_PERFORMANCE_RATIO,
            'Units': 'kWh/kWp',
        })
    return pd.DataFrame(rows)

@registers.register_environment_feedback_artist('generation-potential', _MODEL_TYPE)
def draw_generation_potential(location: Location, sites: Sequence[tuple[str, Location]], metamodel: NewsegsMetaModel):
    """Table of the specific generation potential of the site."""
    table = generation_potential(location, metamodel)
    table['Annual production'] = table['Annual production'].map('{:,.0f}'.format)
    return html.Div([
        html.H6('Specific generation potential', className = 'text-center fw-bold'),
        dbc.Table.from_dataframe(table, striped = True, bordered = False, hover = True, size = 'sm'),
        html.Small(
            "Wind: the configuration's turbine, with its power coefficient curve. "
            f'PV: the global irradiance on the plane, with a performance ratio of {PV_PERFORMANCE_RATIO:g}. '
            'Means over the run period of the model.',
            className = 'text-muted',
        ),
    ])
