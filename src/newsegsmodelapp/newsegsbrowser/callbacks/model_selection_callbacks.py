import json

from dash import Input, Output, ALL, ctx, no_update

from newsegsmodelapp.dash_extension import NewsegsDash

def assign_callbacks(app: NewsegsDash):

    @app.callback(
        Output('url', 'pathname'),
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
                model_type = 'sprake'
            case 'localised':
                model_type = 'sprake-localised'
            case _:
                raise ValueError(f'Unknown prop has called update_model_type: {pid}')

        print('Model selected - going to landing')
        
        return f'/{model_type}/landing'
