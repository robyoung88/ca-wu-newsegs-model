"""
Create a landing layout for an app.
"""
from dataclasses import asdict, dataclass, field
import re
from typing import Any, Callable

from dash import dcc, html
import dash_ag_grid as dag
import pandas as pd

from newsegsmodelapp.components import navigation
from newsegsmodelapp import registers
import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc
from newsegsmodelapp.components import icons
from newsegsmodelapp.types import Page

PAGE_TYPE = 'landing'

def create_landing_header(**kwargs):
    """Create the header of the landing page.

    Args:
        **kwargs: Further keyword arguments.

    Returns:
        The header.
    """
    return html.H1(kwargs.get('head_text', ''))

@dataclass
class LandingLayoutConfiguration(registers.LayoutConfiguration):
    """Layout configuration of the landing page.

    Attributes:
        layout_navigation: Function creating the navigation bar.
        layout_top: Function creating the header.
        width_head: Width of the header, in columns.
        width_body: Width of the body text, in columns.
        width_assumptions: Width of the assumptions, in columns.
        head_text: Heading of the page.
        body_text: Markdown of the body text.
        model_diagram: Source of the model diagram, or a function returning it.
        assumptions_text: Markdown of the assumptions.
    """
    page_type: str = PAGE_TYPE
    layout_navigation: Callable[[str], Any] = navigation.create_navigation_component
    layout_top: Callable[[], Any] = create_landing_header
    width_head: int = 11
    width_body: int = 6
    width_assumptions: int = 6
    head_text: str = 'A NewSEGS model'
    body_text: str|list[str] = 'Some text'
    model_diagram: str | Callable[[], Any] = ''
    assumptions_text: str|list[str] = '# Assumptions\nSome assumptions text'
    default_values_table: pd.DataFrame = field(default_factory = lambda: pd.DataFrame.from_dict({}))

_URL_PATTERN = re.compile(r'https?://[^\s<>]+')

# Shares of the table width taken by the last two columns; the other columns split the rest
_LAST_COLUMNS_WIDTHS = (33, 25)

def _link_last_column(table: pd.DataFrame) -> pd.DataFrame:
    """Turn the URLs in the last column of a table into Markdown autolinks.

    Args:
        table: The table.

    Returns:
        A copy of the table, with its last column as Markdown.
    """
    if table.empty:
        return table
    table = table.copy()
    last = table.columns[-1]
    table[last] = table[last].map(
        lambda text: _URL_PATTERN.sub(r'<\g<0>>', text) if isinstance(text, str) else text
    )
    return table

def _default_values_column_defs(table: pd.DataFrame) -> list[dict[str, Any]]:
    """Create the column definitions of the default values table.

    The last two columns take fixed shares of the table width, and the last column renders as Markdown so its
    links can be followed.

    Args:
        table: The default values table.

    Returns:
        The column definitions.
    """
    columns = list(table.columns)
    if len(columns) < 2:
        return [{'field': column} for column in columns]
    other_width = (100 - sum(_LAST_COLUMNS_WIDTHS)) / (len(columns) - 2)
    column_defs: list[dict[str, Any]] = [{'field': column, 'flex': other_width} for column in columns[:-2]]
    column_defs.append({'field': columns[-2], 'flex': _LAST_COLUMNS_WIDTHS[0]})
    column_defs.append({
        'field': columns[-1],
        'flex': _LAST_COLUMNS_WIDTHS[1],
        'cellRenderer': 'markdown',
        'linkTarget': '_blank',
        # Long URLs have no spaces to wrap at
        'cellStyle': {'overflowWrap': 'anywhere'},
    })
    return column_defs

def create_landing_layout(config: LandingLayoutConfiguration):

    """The layout of the landing page: the description of the model, its diagram and its assumptions.

    Args:
        config: The layout configuration of the page.

    Returns:
        The layout.
    """
    header = dbc.Row([
        dbc.Col(
            config.layout_navigation(config.model_type),
            width = 'auto',
        ),
        dbc.Col(
            config.layout_top(**(asdict(config))),
            class_name = 'page-top',
        ) 
    ])

    body = dbc.Col([
        dcc.Markdown(config.body_text),
    ],
    width = config.width_body
    )
    
    assumptions = dbc.Col([
        dbc.Row(html.H4('Model block diagram')),
        dbc.Row(
        # Make the image fill the column width responsively but not expand beyond it
            html.Img(
                src = config.model_diagram() if isinstance(config.model_diagram, Callable) else config.model_diagram,
                style={
                    'width': '100%',
                    'height': 'auto',
                    'objectFit': 'contain',
                    'display': 'block'
                }
            ),
        ),
        dbc.Row(
            dcc.Markdown(config.assumptions_text),
        ),
    ])

    default_values = dbc.Col([
        dbc.Row(html.H3('Default values')),
        dbc.Row(
            dag.AgGrid(
                id='default_values_table',
                rowData = _link_last_column(config.default_values_table).to_dict('records'),
                # AG Grid shows its loading overlay until column definitions are set
                columnDefs = _default_values_column_defs(config.default_values_table),
                # Wrap long text and grow each row to fit it
                defaultColDef = {'wrapText': True, 'autoHeight': True},
                dashGridOptions={'domLayout':'autoHeight'}
            )
        )
    ])

    return html.Div(
        [
            header,
            html.Hr(),
            dbc.Container([
                dbc.Row([
                    body,
                    assumptions
                ]),
                dbc.Row([
                    default_values,
                ]),
            ])
        ]
    )

landing_page = Page(
    id = PAGE_TYPE,
    nav_label = 'Landing page',
    nav_icon = html.I(
        className = icons.get_icon('nav-landing', style_name = 'raw'),
        style = {'display': 'inline'}
    ),
    layout = create_landing_layout, # type: ignore
    default_configuration = LandingLayoutConfiguration()
)
registers.add_page(landing_page)
