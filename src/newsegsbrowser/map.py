import json
from pyproj import Transformer
from dash import html, dcc, Input, Output, State, ALL, no_update
import dash_leaflet as dl
import dash_bootstrap_components as dbc

from src.newsegsbrowser.common import get_icon

_trans_togb = Transformer.from_crs("EPSG:4326", "EPSG:27700")

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
    return [
        html.Span(get_icon('latlon'), style={'font-size':'1.5rem'}),
        html.Span("(", style={'margin-right': '0.2rem'}),
        dcc.Input(id="site-lat-input", type="text", debounce=True, placeholder="Lat", style={'width': "7rem", 'margin-right': '0.2rem'}),
        html.Span(", "),
        dcc.Input(id="site-lon-input", type="text", debounce=True, placeholder="Lon", style={'width': "7rem", 'margin-left': '0.2rem'}),
        html.Span(")", style={'margin-left': '0.2rem'})
    ]

def create_osgb_feedback():
    return [
        html.Span(get_icon('osgb'), style={'font-size':'1.3rem'}),
        html.Span("OSGB:", style={'margin-right': '0.2rem'}),
        html.Span("(", style={'margin-right': '0.2rem'}),
        html.Span("easting", id="site-osgb-easting-text"),
        html.Span(", "),
        html.Span("northing", id="site-osgb-northing-text"),
        html.Span(")", style={'margin-left': '0.2rem'})
    ]

def create_site_selector_map(map_id='sitemap',
                             center=(53.165716, -3.728402)):
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
                    html.H1("Site Name", 
                            contentEditable="true", 
                            id='site-name-input',
                            className='p-2 m-1'
                            ),
                    width=12,
                    lg=6
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
                        id='latlon-container',
                        align='start'
                    ),
                    dbc.Row(
                        html.Div(
                            html.H5(create_osgb_feedback()),
                            style={"display": "flex", 
                                   "justifyContent": "flex-end", 
                                   "alignItems": "center", 
                                   "width": "100%"}
                        ),
                        id='osgb-container',
                        align='start'
                    ),
                    ],
                    width=12,
                    lg=6,
                    align='start'
                ),
            ],
            justify='between')
        ]
    )
    return elements

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

def add_site_selector_callbacks(app):
    app = add_map_click_callback(app)
    app = add_latlon_sync_callbacks(app)
    app = add_potential_site_change_callback(app)
    app.config.suppress_callback_exceptions = True
    app = add_confirm_site_change_btn_callback(app)
    app.config.suppress_callback_exceptions = False

    app = add_remove_confirm_popup(app)
    app = add_site_change_callback(app)
    
    return app
