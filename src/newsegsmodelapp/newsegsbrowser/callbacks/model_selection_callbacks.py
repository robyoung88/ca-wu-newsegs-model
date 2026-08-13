import json

from dash import Dash, Input, Output, ALL, ctx, no_update

from newsegsmodelapp.newsegsbrowser import variable_dash_component as var_dc
from newsegsmodelapp.newsegsbrowser.app_cache_manager import NewsegsBrowserCacheManager

def assign_callbacks(app: Dash, acm: NewsegsBrowserCacheManager):

    @app.callback(
        Output('url', 'pathname'),
        Output('selected-model', 'data'),
        Input({'type': 'btn-model-type-selector', 'label': ALL}, 'n_clicks'),
        prevent_initial_call = True,
    )
    def update_model_type(btn_click):
        NUP = no_update
        
        trig = ctx.triggered
        if len(trig) > 1:
            # Can only set one model at a time
            return NUP
        trig = trig[0]

        if trig['value'] is None:
            return NUP
        
        pid = json.loads(trig['prop_id'].rstrip('.n_clicks'))
        match pid['label']:
            case 'sprake':
                selected_model = 'sprake'
            case 'localised':
                selected_model = 'localised'
            case _:
                raise ValueError(f'Unknown prop has called update_model_type: {pid}')
        
        return f'/{selected_model}/landing', selected_model
    
    return app
