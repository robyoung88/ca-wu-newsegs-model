"""Result group containers module.

TODO: Describe the purpose of the module.
"""
from dash import html

import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc

def create_results_container(
    children = [],
    section: str = 'results',
    supersection: str = 'results',
    className: str = ''
):
    """The highest level of results component. Blurs on activity and has a spinner.
    
    A type = 'results-container' holds both a 'results-content', which holds the actual
    results children, and a 'results-overlay', which holds the spinner and has no id.

    The className argument can be used to add extra classes to the results-container
    """
    cn = 'results-container'
    if className:
        cn +=  ' ' + className
    
    return html.Div(
        id = {"type": "results-container", "section": section, "supersection": supersection},
        className = cn,
        children = [
            # Layer A: Actual Content (blurs when calculating)
            html.Div(
                id={"type": "results-content", 'section': section, "supersection": supersection},
                className = "results-content",
                children = children,
            ),
            # Layer B: Spinner Overlay (fades in over the top)
            html.Div(
                children=[
                    html.Div(className="spinner"),
                    html.P(
                        "Computing...",
                        id = {
                            'type': 'results-overlay-text',
                            'section': section,
                            'supersection': supersection
                        },
                        className="results-overlay-title"
                    ),
                    html.Small(
                        '',
                        id = {
                            'type': 'results-overlay-subtext',
                            'section': section,
                            'supersection': supersection
                        },
                        className="results-overlay-subtext"
                    ),

                    dbc.Progress(
                        id={
                            'type': 'results-progress-bar',
                            'section': section,
                            'supersection': supersection
                        },
                        value=100,
                        animated=True,
                        striped=True,
                        className="results-progress"
                    ),

                    dbc.Button(
                        "Cancel Jobs",
                        id = {
                            'type': 'cancel-job-button',
                            'section': section,
                            'supersection': supersection,
                        }
                    ),
                ],
                className="results-overlay"
            )
        ],
        # Default data attribute state
        **{"data-status": "IDLE"}, # type: ignore
    )
