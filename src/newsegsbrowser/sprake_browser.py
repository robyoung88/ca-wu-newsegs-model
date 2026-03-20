# A Dash Leaflet map browser for manipulating the Sprake Model
import json, uuid

from dash import Dash, html, Input, Output, dcc, State, ALL, no_update
import dash_leaflet as dl
import dash_bootstrap_components as dbc

from config import settings

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
                html.H4("Site Name", contentEditable="true", id='site-name-input', style={"padding": "10px"}),
                width=12,
                lg=6
            ),
            dbc.Col(
                dbc.Row(
                    html.H4(
                        children=[
                            html.Span("("),
                            html.Span("Lat", contentEditable="true", id="site-lat-input", style={'display': 'inline-block', 'width': "7rem"}),
                            html.Span(", "),
                            html.Span("Lon", contentEditable="true", id="site-lon-input", style={'display': 'inline-block', 'width': "7rem"}),
                            html.Span(")")
                            ],
                            style={'textAlign':'right'}
                        ),
                    id='latlon-container',
                    align='start',
                    justify='end'
                    ),
                width=12,
                lg=6,
                align='start'
            ),
        ],
        justify='between'),
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
    app = add_potential_site_change_callback(app)
    app.config.suppress_callback_exceptions = True
    app = add_confirm_site_change_btn_callback(app)
    app.config.suppress_callback_exceptions = False

    app=add_remove_confirm_popup(app)
    app = add_site_change_callback(app)

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
            return json.dumps({'lat':lat,'lon':lon})
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
            print('displaying popup')
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
        Output('site-location', 'data'),
        Input({'type': 'confirm-site-popup-btn', 'index': ALL}, 'n_clicks'),
        State('potential-site-location', 'data'),
        prevent_initial_call=True
    )
    def change_site(click_data, json_latlon):
        if click_data[0] is None:
            return no_update
        print(f"a click {click_data}")
        return json_latlon
    return app

def add_remove_confirm_popup(app):
    @app.callback(
        Output('site-confirm-container','children',allow_duplicate=True),
        Input('site-location', 'data'),
        prevent_initial_call=True
    )
    def remove_confirm_popup(site_loc):
        return []
    return app

def add_site_change_callback(app):
    @app.callback(
        Output('site-marker-container', 'children'),
        Input('site-location', 'data'),
        prevent_initial_call=True
    )
    def add_site_marker(json_latlon):
        coords = json.loads(json_latlon)
        pos = [float(coords['lat']), float(coords['lon'])]
        return [dl.Marker(id='site-marker',
                          position=pos,
                          children=[dl.Tooltip("Site Location")])]
    return app


if __name__=="__main__":
    app = create_app()

    app.run(debug=True)