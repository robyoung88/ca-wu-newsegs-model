from dash import html

from newsegsbrowser import icons

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
                html.Th(icons.get_icon(
                    f'config-{x+1}',
                    icon_class = icons.ICON_COLOUR_CLASSES[x % len(icons.ICON_COLOUR_CLASSES)]
                )) for x in range(n_configs)
            ])
        )
    ]
