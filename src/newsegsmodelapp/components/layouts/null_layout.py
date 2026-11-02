"""A layout which shows nothing.
"""
from dash import html

def NULL_LAYOUT(*args, **kwargs):
    """A layout which shows nothing.

    Used as the default `creation_function` of cards.

    Args:
        *args: Further positional arguments.
        **kwargs: Further keyword arguments.

    Returns:
        An empty span.
    """
    return html.Span()
