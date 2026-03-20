# A Dash Leaflet map browser for manipulating the Sprake Model
import json, uuid
from pyproj import Transformer

from dash import Dash, html, Input, Output, dcc, State, ALL, no_update
import dash_leaflet as dl
import dash_bootstrap_components as dbc
import dash_daq as daq

from config import settings

_trans_togb = Transformer.from_crs("EPSG:4326", "EPSG:27700")

def create_layout():
    mapview = html.Div([
        
        dbc.Row([
            dbc.Col(
                dl.Map(
                    id='sitemap',
                    children=[
                        dl.TileLayer(),
                        dl.LayerGroup(id='site-marker-container'),
                        dl.LayerGroup(id='site-confirm-container'),
                    ],
                    center=(53.165716, -3.728402),
                    zoom=9,
                    doubleClickZoom=False,
                    style={"height":"33vh"},
                ),
                width=12
            )
        ]),
        dbc.Row([
            dbc.Col(
                html.H1("Site Name", contentEditable="true", id='site-name-input', style={"padding": "10px"}),
                width=12,
                lg=6
            ),
            dbc.Col(
                [
                    dbc.Row(
                        html.Div(
                            html.H4(
                                children=[
                                html.I(className="bi bi-geo-alt", style={"padding": "10px", 'font-size':'1.5rem'}),
                                html.Span("(", style={'margin-right': '0.2rem'}),
                                dcc.Input(id="site-lat-input", type="text", debounce=True, placeholder="Lat", style={'width': "7rem", 'margin-right': '0.2rem'}),
                                html.Span(", "),
                                dcc.Input(id="site-lon-input", type="text", debounce=True, placeholder="Lon", style={'width': "7rem", 'margin-left': '0.2rem'}),
                                html.Span(")", style={'margin-left': '0.2rem'})
                            ]
                            )
                            ,
                            style={"display": "flex", "justifyContent": "flex-end", "alignItems": "center", "width": "100%"}
                        ),
                    id='latlon-container',
                    align='start'
                    ),
                    dbc.Row(
                        html.Div(
                            html.H5(
                                children=[
                                html.I(className="bi bi-map", style={"padding": "10px", 'font-size':'1.3rem'}),
                                html.Span("OSGB:", style={'margin-right': '0.2rem'}),
                                html.Span("(", style={'margin-right': '0.2rem'}),
                                html.Span("easting", id="site-osgb-easting-text"),
                                html.Span(", "),
                                html.Span("northing", id="site-osgb-northing-text"),
                                html.Span(")", style={'margin-left': '0.2rem'})
                            ]
                            )
                            ,
                            style={"display": "flex", "justifyContent": "flex-end", "alignItems": "center", "width": "100%"}
                        ),
                    id='osgb-container',
                    align='start'
                    )
                ],
                width=12,
                lg=6,
                align='start'
            ),
        ],
        justify='between'),
        html.Hr(),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H2([
                            html.I(className="bi bi-lightning-charge", style={'padding': "10px"}),
                            'Generation'
                        ],
                        className='card-title'),
                        html.H4([
                            'Total generation: ',
                            html.I(className="bi bi-wind", style={"margin-right": "0.1rem"}),
                            " = ",
                            html.Span("0.0", id='gen-smry-wind-cap'),
                            " kW; ",
                            html.I(className="bi bi-sun", style={"margin-right": "0.1rem", "margin-left": "0.2rem"}),
                            " = ",
                            html.Span("0.0", id='gen-smry-solar-cap'),
                            " kWp"
                        ],
                        className='card-subtitle'),
                        html.Details([
                            html.Summary(""),
                            html.Div([
                                dbc.Row(
                                    html.Div([
                                        html.H5([
                                            html.I(className="bi bi-wind", style={"padding": "7px"}),
                                            html.Span("Wind Capacity (kW rated): ", style={'margin-right': '0.2rem'}),
                                        ],
                                        style={'display':'inline', "width":"50%"}),                                            
                                        dbc.Input(id='wind-capacity-input', type='number', placeholder=0.0, debounce='True', style={'display':'inline-block', 'float':'right', "width":"30%"})
                                ])),
                                dbc.Row(
                                    html.Div([
                                        html.H5([
                                            html.I(className="bi bi-sun", style={"padding": "7px"}),
                                            html.Span("Solar PV Capacity (kWp): ", style={'margin-right': '0.2rem'}),
                                        ],
                                        style={'display':'inline', "width":"50%"}),                                            
                                        dbc.Input(id='solar-capacity-input', type='number', placeholder=0.0, debounce='True', style={'display':'inline-block', 'float':'right', "width":"30%"})
                                ]))
                            ])
                        ])
                    ])
                ])
            ],
            width = 12,
            md = 6),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H2([
                            html.I(className="bi bi-battery-half", style={"padding": "10px"}),
                            "Storage"
                        ],
                        className='card-title'),
                        html.H4([
                            'Storage capacity: ',
                            html.Span("0.0", id='stor-smry-cap'),
                            " kWh"
                        ],
                        className='card-subtitle'),
                        html.Details([
                            html.Summary(""),
                            html.Div([
                                dbc.Row([
                                    html.Div([
                                        html.H5([
                                            html.I(className="bi bi-battery-half", style={"padding": "7px"}),
                                            html.Span("Storage Capacity (kWh): ", style={'margin-right': '0.2rem'}),
                                        ],
                                        style={'display':'inline', "width":"50%"}
                                        ),
                                        dbc.Input(
                                            id='storage-capacity-input', 
                                            type='number', 
                                            placeholder=0.0, 
                                            debounce='True', 
                                            style={'display':'inline-block', 
                                                   'float':'right', 
                                                "width":"30%"}
                                        )             
                                    ])
                                ])
                            ])
                        ])
                    ])
                ])
                
            ],
            width = 12,
            md = 6),
        ]),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H2([
                            html.I(
                                className="bi bi-houses",
                                style={"padding": "10px"}
                                ),
                            "Building Consumption"
                        ],
                        className='card-title'),
                        html.H4([
                            'Site size: ',
                            html.Span("0", id="bc-smry-n-units"),
                            " units"
                        ],
                        className='card-subtitle'),
                        html.Details([
                            html.Summary(""),
                            html.Div([
                                dbc.Row([
                                    html.Div([
                                        html.H5([
                                            html.I(className="bi bi-houses", style={"padding": "7px"}),
                                            html.Span("No. of households: ", style={'margin-right': '0.2rem'}),
                                        ],
                                        style={'display':'inline', "width":"50%"}
                                        ),
                                        dbc.Input(
                                            id='n-unit-input', 
                                            type='number', 
                                            placeholder=0.0, 
                                            debounce='True', 
                                            style={'display':'inline-block', 
                                                   'float':'right', 
                                                   'width':'30%'}
                                        )
                                    ])
                                ]),
                                dbc.Row([
                                    html.Div([
                                        html.H5([
                                            html.I(className="bi bi-fire", style={"padding": "7px"}),
                                            html.Span("HLP (W/m²/K): ", style={'margin-right': '0.2rem'}),
                                        ],
                                        style={'display':'inline', "width":"50%"}
                                        ),
                                        dbc.Input(
                                            id='hlp-input', 
                                            type='number', 
                                            placeholder=0.0, 
                                            debounce='True', 
                                            style={'display':'inline-block', 
                                                   'float':'right', 
                                                   'width':'30%'}
                                        )
                                    ])
                                ]),
                                dbc.Row([
                                    html.Div([
                                        html.H5([
                                            html.I(className="bi bi-rulers", style={"padding": "7px"}),
                                            html.Span("Mean GFA (m²/household): ", style={'margin-right': '0.2rem'}),
                                        ],
                                        style={'display':'inline', "width":"50%"}
                                        ),
                                        dbc.Input(
                                            id='gfa-input', 
                                            type='number', 
                                            placeholder=0.0, 
                                            debounce='True', 
                                            style={'display':'inline-block', 
                                                   'float':'right', 
                                                   'width':'30%'}
                                        )
                                    ])
                                ]),
                                # TODO: Output Fabric Energy Efficiency here
                                dbc.Row([
                                    html.Div([
                                        html.H5([
                                            html.I(className="bi bi-droplet", style={"padding": "7px", "padding-right":"2px"}),
                                            html.I(className="bi bi-thermometer-high", style={"padding": "7px", "padding-left":"2px"}),
                                            html.Span("Reference hot water demand (kWh/day): ", style={'margin-right': '0.2rem'}),
                                        ],
                                        style={'display':'inline', "width":"50%"}
                                        ),
                                        dbc.Input(
                                            id='ref-hotwater-input', 
                                            type='number', 
                                            placeholder=0.0, 
                                            debounce='True', 
                                            style={'display':'inline-block', 
                                                   'float':'right', 
                                                   'width':'30%'}
                                        )
                                    ])
                                ]),
                                dbc.Row([
                                    html.Div([
                                        html.H5([
                                            html.I(className="bi bi-droplet", style={"padding": "7px", "padding-right":"2px"}),
                                            html.I(className="bi bi-plus-slash-minus", style={"padding": "7px", "padding-left":"2px"}),
                                            html.Span("Seasonal variation (%): ", style={'margin-right': '0.2rem'}),
                                        ],
                                        style={'display':'inline', "width":"50%"}
                                        ),
                                        dbc.Input(
                                            id='variation-hotwater-input', 
                                            type='number', 
                                            placeholder=0.0, 
                                            debounce='True', 
                                            style={'display':'inline-block', 
                                                   'float':'right', 
                                                   'width':'30%'}
                                        )
                                    ])
                                ])
                                # TODO: Output annual DHW demand
                            ])
                        ])
                    ])
                ])
            ],
            width = 12,
            md = 6
            ),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H2([
                            html.I(className="bi bi-plug", style={'padding': "10px"}),
                            'Appliance Consumption'
                        ],
                        className='card-title'),
                        html.H4([
                            html.I(className="bi bi-lamp", style={"margin-right": "0.1rem"}),
                            " = ",
                            html.Span("0.0", id="cons-smry-app"),
                            " kWh/yr; ",
                            html.I(className="bi bi-ev-front", style={"margin-right": "0.1rem"}),
                            " = ",
                            html.Span("0.0", id="cons-smry-ev"),
                            " kWh/yr"
                        ],
                        className='card-subtitle'),
                        html.Details([
                            html.Summary(""),
                            html.Div([
                                dbc.Row(
                                    html.Div([
                                        html.H5([
                                            html.I(className="bi bi-graph-down-arrow", style={"padding": "7px"}),
                                            html.Span("High-efficiency appliances consumption reduction (%)"),
                                        ],
                                        style={'display':'inline', "width":"50%"}),
                                        dbc.Input(id='app-efficiency-input', 
                                                  type='number',
                                                  placeholder=0.0,
                                                  debounce='True',
                                                  style={'display':'inline-block', 'float':'right', "width":"30%"})
                                    ])
                                ),
                                dbc.Row(
                                    html.Div([
                                        html.H5([
                                            html.I(className="bi bi-ev-station", style={"padding": "7px"}),
                                            html.Span("Residential charging per EV (kWh/yr)"),
                                        ],
                                        style={'display':'inline', "width":"50%"}),
                                        dbc.Input(id='ev-ann-charge-input', 
                                                  type='number',
                                                  placeholder=0.0,
                                                  debounce='True',
                                                  style={'display':'inline-block', 'float':'right', "width":"30%"})
                                    ])
                                ),
                                dbc.Row(
                                    html.Div([
                                        html.H5([
                                            html.I(className="bi bi-ev-front", style={"padding": "7px"}),
                                            html.Span("EVs per household (n)"),
                                        ],
                                        style={'display':'inline', "width":"50%"}),
                                        dbc.Input(id='ev-per-unit-input', 
                                                  type='number',
                                                  placeholder=0.0,
                                                  debounce='True',
                                                  style={'display':'inline-block', 'float':'right', "width":"30%"})
                                    ])
                                ),
                            ])
                        ])
                    ])
                ])
            ],
            width = 12,
            md = 6
            ),
        ]),
        html.Hr(),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H2([
                            html.I(className="bi bi-cash-stack", style={'padding': "10px","padding-right":"2px"}),
                            html.I(className="bi bi-lightning-charge", style={'padding': "10px", "padding-left":"2px"}),
                            "Generation Costs"
                        ],
                        className='card-title')
                    ])
                ])
            ],
            lg=6),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H2([
                            html.I(className="bi bi-cash-stack", style={'padding': "10px", "padding-right":"2px"}),
                            html.I(className="bi bi-battery-half", style={'padding': "10px", "padding-left":"2px"}),
                            "Storage Costs"
                        ],
                        className='card-title')
                    ])
                ])
            ],
            lg=6),
        ]),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H2([
                            html.I(className="bi bi-receipt-cutoff", style={'padding': "10px"}),
                            "Sales"
                        ],
                        className='card-title')
                    ])
                ])
            ],
            lg=6),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H2([
                            html.I(className="bi bi-box-arrow-in-down-right", style={'padding': "10px"}),
                            "Import Costs"
                        ],
                        className='card-title')
                    ])
                ])
            ],
            lg=6),
        ]),
        html.Hr(),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H2([
                            html.I(className="bi bi-cpu", style={'padding': "10px"}),
                            "Model Settings"
                        ],
                        className='card-title')
                    ])
                ])
            ],
            width=12)
        ]),
        html.Hr(),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Span([
                            html.H2([
                                html.I(className="bi bi-bar-chart", style={'padding': "10px"}),
                                "Results"
                            ],
                            style={
                                'display': 'inline-block',
                                'float': 'left'
                            }),
                            html.Span([
                                html.H5("Per year",style={'display': 'inline-block', 'vertical-align': 'middle'}),
                                daq.ToggleSwitch(style={'display': 'inline-block', 'vertical-align': 'middle','padding': "10px"}),
                                html.H5('To horizon',style={'display': 'inline-block', 'vertical-align': 'middle'})
                            ],
                            style={
                                'display': 'inline-block',
                                'float': 'right'
                            })
                        ],
                        className='card-title')
                    ])
                ])
            ],
            width=12)
        ]),
        dcc.Store(id='potential-site-location'),
        dcc.Store(id='site-location')
    ])

    return dbc.Container(mapview, fluid=False)
    
def serve_layout():
    session_id = str(uuid.uuid4())

    return html.Div([
        create_layout(),
        dcc.Store(data=session_id, id='session-id')
    ])

def create_app(external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP]):
    app = Dash(external_stylesheets=external_stylesheets)
    app.layout = serve_layout

    app = add_map_click_callback(app)
    app = add_latlon_sync_callbacks(app)
    app = add_potential_site_change_callback(app)
    app.config.suppress_callback_exceptions = True
    app = add_confirm_site_change_btn_callback(app)
    app.config.suppress_callback_exceptions = False

    app=add_remove_confirm_popup(app)
    app = add_site_change_callback(app)

    app.title = "Sprake Energy Model"

    return app

def add_latlon_sync_callbacks(app):
    @app.callback(
        Output('site-location', 'data', allow_duplicate=True),
        Input('site-lat-input', 'value'),
        Input('site-lon-input', 'value'),
        State('site-location', 'data'),
        prevent_initial_call=True
    )
    def sync_inputs_to_store(lat_val, lon_val, current_site):
        if lat_val is None or lon_val is None:
            return no_update
        try:
            lat = float(lat_val)
            lon = float(lon_val)
        except (TypeError, ValueError):
            return no_update
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return no_update
        easting,northing = _trans_togb.transform(lat, lon)
        new_site = json.dumps({'lat': lat, 'lon': lon, 'easting': easting, 'northing': northing})
        if new_site == current_site:
            return no_update
        return new_site

    @app.callback(
        Output('site-lat-input', 'value'),
        Output('site-lon-input', 'value'),
        Input('site-location', 'data'),
        prevent_initial_call=True
    )
    def sync_store_to_inputs(site_loc):
        if site_loc is None:
            return no_update, no_update
        try:
            coords = json.loads(site_loc)
            lat = float(coords.get('lat', ''))
            lon = float(coords.get('lon', ''))
        except (TypeError, ValueError, json.JSONDecodeError, AttributeError):
            return no_update, no_update
        return f"{lat:.6f}", f"{lon:.6f}"

    return app

def add_map_click_callback(app):
    @app.callback(
        Output('potential-site-location', 'data'),
        Input('sitemap', 'dblclickData'),
        State('potential-site-location', 'data'),
        prevent_initial_call=True
    )
    def change_site_loc(click_data, current_val):
        if not current_val is None:
            coords = json.loads(current_val)
            pos = [float(coords['lat']), float(coords['lon'])]
            if pos[0] == 0 and pos[1] == 0:
                return []
        if not click_data is None:
            coordinates = click_data['latlng']
            lat, lon = coordinates.values()
            easting,northing = _trans_togb.transform(lat, lon)
            return json.dumps({'lat':lat,'lon':lon, 'easting': easting, 'northing': northing})
        else:
            return json.dumps({'lat':0,'lon':0})
    return app

def add_potential_site_change_callback(app):
    @app.callback(
        Output('site-confirm-container', 'children',allow_duplicate=True),
        Input('potential-site-location', 'data'),
        prevent_initial_call=True
        
    )
    def change_potential_site(json_latlon):
        coords = json.loads(json_latlon)
        pos = [float(coords['lat']), float(coords['lon'])]
        if pos[0] == 0 and pos[1] == 0:
            return []
        else:
            return [dl.Popup(id={'type': 'confirm-site-popup', 'index':0},
                             position = pos,
                             children = [
                                html.Span(
                                    children = [
                                        html.H4("Confirm site change"),
                                        html.H5(f"({pos[0]:.3f}, {pos[1]:.3f})"),
                                        html.I(className="bi bi-geo-alt-fill btn btn-primary",
                                               style={"font-size":"2rem"},
                                               id={'type': 'confirm-site-popup-btn', 'index':1})
                                    ],
                                    style = {
                                        "display": "table-cell",
                                        "text-align": "center"
                                    }
                                )
                             ]
                             )]
    return app

def add_confirm_site_change_btn_callback(app):
    @app.callback(
        Output('site-location', 'data', allow_duplicate=True),
        Input({'type': 'confirm-site-popup-btn', 'index': ALL}, 'n_clicks'),
        State('potential-site-location', 'data'),
        prevent_initial_call=True
    )
    def change_site(click_data, json_latlon):
        if click_data[0] is None:
            return no_update
        return json_latlon
    return app

def add_remove_confirm_popup(app):
    @app.callback(
        Output('site-confirm-container', 'children'),
        Input('site-location', 'data'),
        prevent_initial_call=True,
        allow_duplicate=True
    )
    def remove_confirm_popup(site_loc):
        return []
    return app

def add_site_change_callback(app):
    @app.callback(
        Output('site-marker-container', 'children'),
        Output('site-osgb-easting-text', 'children'),
        Output('site-osgb-northing-text', 'children'),
        Input('site-location', 'data'),
        prevent_initial_call=True
    )
    def add_site_marker(json_latlon):
        coords = json.loads(json_latlon)
        pos = [float(coords['lat']), float(coords['lon'])]
        return ([dl.Marker(id='site-marker',
                          position=pos,
                          children=[dl.Tooltip("Site Location")])], 
                          f"{float(coords['easting']):,.0f}",
                          f"{float(coords['northing']):,.0f}")
    return app


if __name__=="__main__":
    app = create_app()

    app.run(debug=True)