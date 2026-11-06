"""The feedback on the environmental conditions of a site: plots and tables of the environmental
data of its location, drawn by the artists registered for the model type.

The data are fetched only when the user asks, with the button under the map, as fetching is slow;
see `environment_feedback_callbacks`. The feedback is held in a closed Details, and is drawn when
the Details is opened and the data of the site are available.
"""
from dataclasses import dataclass
from typing import Sequence

from dash import dcc, html
from dash_iconify import DashIconify

from newsegsmodelapp.components.icons import get_icon
import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc

DETAILS_ID = 'environment-feedback-details'
SUMMARY_ID = 'environment-feedback-summary'
STATUS_ID = 'environment-feedback-status'
CONTAINER_ID = 'environment-feedback-container'
FETCH_BUTTON_ID = 'btn-fetch-environment-data'
FETCH_SPINNER_ID = 'environment-data-fetch-spinner'
FETCH_RESULT_ID = 'environment-data-fetch-result'
FETCH_RUNNING_ID = 'environment-data-fetch-running'
PENDING_INTERVAL_ID = 'environment-data-pending-interval'
DRAWN_ID = 'environment-feedback-drawn'
READY_ID = 'environment-feedback-ready'
ITEM_TYPE = 'environment-feedback'

STALE_CLASS = 'environment-feedback-stale'

@dataclass
class EnvironmentFeedbackItem:
    """An item of environmental feedback, drawn by the artist registered for its key.

    Attributes:
        key: Key of the artist.
        width: Width of the item in the Bootstrap grid (of 12) on large screens.
    """
    key: str
    width: int = 6

def item_id(key: str) -> dict:
    """Id of the container of an item of environmental feedback."""
    return {'type': ITEM_TYPE, 'key': key}

def create_environmental_conditions_card(items: Sequence[EnvironmentFeedbackItem]):
    """A Bootstrap card holding the environmental feedback items, in a closed Details.

    Args:
        items: The items, in order.

    Returns:
        The card.
    """
    return dbc.Card([
        dbc.CardBody([
            html.Details([
                html.Summary(
                    html.H5(
                        [
                            DashIconify(icon = 'bi:cloud-sun', width = 24, className = 'd-inline-flex m-1'),
                            html.H3('Site environmental conditions', className = 'd-inline-flex'),
                            dbc.Badge(
                                id = STATUS_ID,
                                color = 'warning',
                                className = 'ms-3 align-self-center',
                                style = {'display': 'none'},
                            ),
                        ],
                        className = 'd-flex align-content-center flex-wrap m-0',
                    ),
                    style = {
                        'listStyle': 'none',  # Removes marker in modern browsers
                        'cursor': 'pointer',
                        'userSelect': 'none',
                    },
                    className = 'summary-no-caret', # Hook for browser-specific caret hiding
                    # Clicks are counted to tell whether the Details is open, as Dash does not
                    # report its open state: an odd count is open
                    id = SUMMARY_ID,
                    n_clicks = 0,
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            dcc.Loading(html.Div(id = item_id(item.key)), delay_show = 300),
                            width = 12,
                            lg = item.width,
                            className = 'mb-3',
                        )
                        for item in items
                    ],
                    id = CONTAINER_ID,
                    className = 'mt-3', # Adds spacing between title and items when expanded
                ),
            ],
            id = DETAILS_ID,
            open = False,
            ),
            # The site whose data are available to draw; None when they are not
            dcc.Store(id = READY_ID, storage_type = 'memory'),
            # The site whose feedback is drawn, so that it is not drawn again on reopening
            dcc.Store(id = DRAWN_ID, storage_type = 'memory'),
            # Polls the data source while another process fetches the data of the site
            dcc.Interval(id = PENDING_INTERVAL_ID, interval = 3000, disabled = True),
        ],
        className = 'p-2', # Tightens CardBody padding
        )
    ])

def create_environment_data_button():
    """The button which fetches the environmental data of the site, shown under the map when
    the model type has environmental feedback.

    Returns:
        List of components.
    """
    return [
        dbc.Button(
            [
                html.I(className = get_icon('gen-wind', style_name = 'raw') + ' me-1'),
                html.I(className = get_icon('gen-pv', style_name = 'raw') + ' me-2'),
                'Get environmental data',
                # Shown while the data are fetched
                html.Span(
                    id = FETCH_SPINNER_ID,
                    className = 'spinner-border spinner-border-sm ms-2',
                    style = {'display': 'none'},
                ),
            ],
            id = FETCH_BUTTON_ID,
            color = 'primary',
            outline = True,
            size = 'sm',
            disabled = True,
            className = 'm-1',
        ),
        # The location fetched, and the error if the data could not be obtained
        dcc.Store(id = FETCH_RESULT_ID, storage_type = 'memory'),
        # Whether the fetch is running; the fetch is a background callback, which may not have
        # started fetching (and so locked the data) for some time after the click
        dcc.Store(id = FETCH_RUNNING_ID, data = False, storage_type = 'memory'),
    ]

def create_placeholder_layout():
    """The components of the environmental feedback, empty and hidden, for pages of model types
    without it, and for the validation layout of the app. Their callbacks need all of their ids
    on the page, and do nothing for a model type without a data source.

    Returns:
        The hidden components.
    """
    return html.Div(
        [create_environmental_conditions_card([]), *create_environment_data_button()],
        style = {'display': 'none'},
    )
