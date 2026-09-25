from dash import html

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
                        id = {'type': 'results-overlay-text', 'section': section, 'supersection': supersection}
                    )
                ],
                className="results-overlay"
            )
        ],
        # Default data attribute state
        **{"data-status": "IDLE"}, # type: ignore
    )

# def result_group_container(
#     section: str,
#     supersection: str
# ):
#     return (
#         html.Div(id = {'type': 'result-options-container', 'section': section, 'supersection': supersection}),
#         html.Div(id = {'type': ''})
#     )

# def figure_container(
#     triggering_section: str,
#     triggering_key: str,
# ):
#     ...