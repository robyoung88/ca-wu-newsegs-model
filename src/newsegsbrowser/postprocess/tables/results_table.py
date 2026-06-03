from dash import html

from src.newsegsbrowser import icons

def create_tbl_head(n_configs):
    """
    Create a header for results tables, labelling columns with configuration numbers.
    """
    return [
        html.Thead(
            html.Tr([
                html.Th(""),
                html.Th("")
            ] + [
                html.Th(icons.get_icon(f'config-{x+1}')) for x in range(n_configs)
            ])
        )
    ]
