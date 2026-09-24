from functools import partial
from typing import Collection

from dash import dcc, html
import dash_bootstrap_components as dbc
import dash_leaflet as dl

from newsegsmodelapp.newsegsbrowser import icons

def create_map_layout(map_id='sitemap',
                      center=(53.165716, -3.728402)):
    return [
        dl.Map(
            id=map_id,
            children=[
                dl.TileLayer(),
                dl.LayerGroup(id='site-marker-container'),
                dl.LayerGroup(id='site-confirm-container'),
            ],
            center=center,
            zoom=9,
            doubleClickZoom=False,
            style={"height":"33vh"},
        ),
        dcc.Store(id='potential-site-location'),
        dcc.Store(id='site-location')
        ]

def create_latlon_input():
    ll_input = partial(
        dcc.Input,
        type = 'text',
        debounce = True,
        style = {
            'width': '7rem',
            'margin-right': '0.2rem'
        }
    )

    return [
        html.Span(icons.get_icon('latlon'), style={'fontSize':'1.5rem'}),
        html.Span("(", style={'marginRight': '0.2rem'}),
        ll_input(id = 'site-lat-input', placeholder = 'Lat'),
        html.Span(", "),
        ll_input(id = 'site-lon-input', placeholder = 'Lon'),
        html.Span(")", style={'marginLeft': '0.2rem'})
    ]

def create_osgb_feedback():
    return [
        html.Span(icons.get_icon('osgb'), style={'fontSize':'1.3rem'}),
        html.Span("OSGB:", style={'marginRight': '0.2rem'}),
        html.Span("(", style={'marginRight': '0.2rem'}),
        html.Span("easting", id="site-osgb-easting-text"),
        html.Span(", "),
        html.Span("northing", id="site-osgb-northing-text"),
        html.Span(")", style={'marginLeft': '0.2rem'})
    ]

def create_site_selector_map(
        map_id: str = 'sitemap',
        center: Collection[float] = (53.165716, -3.728402)
    ):
    elements = html.Div(
        [
            dbc.Row([
                dbc.Col(
                    create_map_layout(map_id, center),
                    width=12
                )
            ]),
            dbc.Row([
                dbc.Col(
                    html.H1(
                        dcc.Input(
                            placeholder = 'Site Name',
                            debounce = True,
                            type = 'text',
                            id = 'site-name-input',
                            style = {
                                'border': 'none',
                                'outline': 'none',
                                'width': '25',
                                'height': 'auto',
                                'lineHeight': '1.5',
                                'padding': '5px 0',
                                'background': 'transparent',
                            },
                            className='p-2 m-1'
                        )
                    ),  
                    width = 12,
                    lg = 6
                ),
                dbc.Col([
                    dbc.Row(
                        html.Div(
                            html.H4(create_latlon_input()),
                            style={"display": "flex", 
                                   "justifyContent": "flex-end", 
                                   "alignItems": "center", 
                                   "width": "100%"}
                        ),
                        id = 'latlon-container',
                        align = 'start'
                    ),
                    dbc.Row(
                        html.Div(
                            html.H5(create_osgb_feedback()),
                            style={"display": "flex", 
                                   "justifyContent": "flex-end", 
                                   "alignItems": "center", 
                                   "width": "100%"}
                        ),
                        id = 'osgb-container',
                        align = 'start'
                    ),
                    ],
                    width = 12,
                    lg = 6,
                    align = 'start'
                ),
            ],
            justify='between')
        ]
    )
    return elements