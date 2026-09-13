import json
from typing import cast
from pyproj import Transformer
from dash import Dash, html, dcc, Input, Output, State, ALL, no_update
from dash.exceptions import PreventUpdate
import dash_leaflet as dl
import dash_bootstrap_components as dbc
from dash_bootstrap_components._components.Row import Row as dbc_Row
from dash_bootstrap_components._components.Col import Col as dbc_Col

from newsegsmodelapp.dash_extension import NewsegsDash
from newsegsmodelframework.core import location as modlocation
from newsegsmodelapp.newsegsbrowser.app_cache_manager import NewsegsBrowserCacheManager
from newsegsmodelapp.newsegsbrowser.common import get_icon
from newsegsmodelframework.newsegsproject.newsegsproject import NewsegsProject

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
        html.Span(get_icon('latlon'), style={'fontSize':'1.5rem'}),
        html.Span("(", style={'marginRight': '0.2rem'}),
        dcc.Input(id="site-lat-input", type="text", debounce=True, placeholder="Lat", style={'width': "7rem", 'margin-right': '0.2rem'}),
        html.Span(", "),
        dcc.Input(id="site-lon-input", type="text", debounce=True, placeholder="Lon", style={'width': "7rem", 'margin-left': '0.2rem'}),
        html.Span(")", style={'marginLeft': '0.2rem'})
    ]

def create_osgb_feedback():
    return [
        html.Span(get_icon('osgb'), style={'fontSize':'1.3rem'}),
        html.Span("OSGB:", style={'marginRight': '0.2rem'}),
        html.Span("(", style={'marginRight': '0.2rem'}),
        html.Span("easting", id="site-osgb-easting-text"),
        html.Span(", "),
        html.Span("northing", id="site-osgb-northing-text"),
        html.Span(")", style={'marginLeft': '0.2rem'})
    ]

def create_site_selector_map(map_id='sitemap',
                             center=(53.165716, -3.728402)):
    elements = html.Div(
        [
            dbc_Row([
                dbc_Col(
                    create_map_layout(map_id, center),
                    width=12
                )
            ]),
            dbc_Row([
                dbc_Col(
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
                    width=12,
                    lg=6
                ),
                dbc_Col([
                    dbc_Row(
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
                    dbc_Row(
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

def add_latlon_sync_callbacks(app: NewsegsDash):
    @app.callback(
        Output('site-location', 'data', allow_duplicate=True),
        
        Input('site-lat-input', 'value'),
        Input('site-lon-input', 'value'),
        Input('site-name-input', 'value'),
        State('site-location', 'data'),
        prevent_initial_call=True
    )
    def sync_inputs_to_store(lat_val, lon_val, site_name, current_site):
        if lat_val is None or lon_val is None or site_name is None:
            return no_update
        try:
            lat = float(lat_val)
            lon = float(lon_val)
        except (TypeError, ValueError):
            return no_update
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return no_update
        easting,northing = _trans_togb.transform(lat, lon)
        new_site = json.dumps({'lat': lat, 'lon': lon, 'easting': easting, 'northing': northing, 'name': site_name})
        if new_site == current_site:
            return no_update
        return new_site

    @app.callback(
        Output('site-lat-input', 'value'),
        Output('site-lon-input', 'value'),
        Output('site-name-input', 'value'),

        Input('site-location', 'data'),
        State('active-project-id', 'data'),
        prevent_initial_call=True
    )
    def sync_store_to_inputs(site_loc, active_project_id):
        if site_loc is None:
            raise PreventUpdate
        try:
            coords = json.loads(site_loc)
            lat = float(coords.get('lat', ''))
            lon = float(coords.get('lon', ''))
            name = coords.get('name', no_update)
        except (TypeError, ValueError, json.JSONDecodeError, AttributeError):
            raise PreventUpdate
        
        newloc = modlocation.Location(lat, lon, name = name)

        proj = app.project_provider.get_project(active_project_id)
        mm = proj.get_focussed_metamodel()

        modified = False
        if not(newloc == mm.model.location):
            mm.model.location = newloc
            modified = True
        if not mm.model.location.name != name:
            mm.model.location.name = name
            modified = True

        if modified:
            app.project_provider.upsert_component(proj, force = True)

        return f"{lat:.6f}", f"{lon:.6f}", name

def add_map_click_callback(app: NewsegsDash):
    @app.callback(
        Output('potential-site-location', 'data'),

        Input('sitemap', 'dblclickData'),
        State('potential-site-location', 'data'),
        State('site-name-input', 'value'),
        prevent_initial_call=True
    )
    def change_site_loc(click_data, current_val, current_name):
        if not current_val is None:
            coords = json.loads(current_val)
            pos = [float(coords['lat']), float(coords['lon'])]
            if pos[0] == 0 and pos[1] == 0:
                return []
        if not click_data is None:
            coordinates = click_data['latlng']
            lat, lon = coordinates.values()
            easting,northing = _trans_togb.transform(lat, lon)
            return json.dumps({'lat':lat,'lon':lon, 'easting': easting, 'northing': northing, 'name': current_name})
        else:
            return json.dumps({'lat':0,'lon':0, 'name': current_name})


def add_potential_site_change_callback(app: NewsegsDash):
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
                                        "textAlign": "center"
                                    }
                                )
                             ]
                             )]

def add_confirm_site_change_btn_callback(app: NewsegsDash):
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

def add_site_change_callback(app) -> Dash:
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
        easting = coords.get('easting', None)
        northing = coords.get('northing', None)
        if not easting:
            easting, northing = _trans_togb.transform(pos[0], pos[1])
        return ([dl.Marker(id='site-marker',
                          position=pos,
                          children=[dl.Tooltip("Site Location")])], 
                          f"{float(easting):,.0f}",
                          f"{float(northing):,.0f}")
    return app

def add_site_selector_callbacks(app: NewsegsDash):
    add_map_click_callback(app)
    add_latlon_sync_callbacks(app)
    add_potential_site_change_callback(app)
    app.config.suppress_callback_exceptions = True
    add_confirm_site_change_btn_callback(app)
    app.config.suppress_callback_exceptions = False

    add_remove_confirm_popup(app)
    add_site_change_callback(app)
    
    return app
