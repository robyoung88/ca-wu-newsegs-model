from functools import partial

from dash import dcc, html
import dash_bootstrap_components as dbc
from dash_bootstrap_components._components.Card import Card as dbc_Card
from dash_bootstrap_components._components.CardBody import CardBody as dbc_CardBody
from dash_bootstrap_components._components.Row import Row as dbc_Row
from dash_bootstrap_components._components.Col import Col as dbc_Col
import plotly.express as px

from newsegsmodelapp.components.get_focussed_metamodel import get_focussed_metamodel
from newsegsmodelapp.components import energy_balance_estimation
from newsegsmodelapp.components.update_energy_balance_sprake import update_estimated_energy_balance
from newsegsmodelapp.registers import register_feedback_graph_artist
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface


def create_indicative_net_energy_card():
    """
    A Bootstrap card holding plots to help with generation and consumption sizing.
    """
    return dbc_Card([
        dbc_CardBody([
            html.Details([
                html.Summary(
                    html.H5(
                        ['Indicative net energy']
                        ),
                ),
                dbc_Row([
                    dbc_Col(
                        dcc.Graph(
                            id={'type': 'feedback-graph', 'section': 'feedback', 'key': 'estimated-annual-energy'},
                            config={'displayModeBar': False},
                            style={
                                'height': '120px',
                                'border': '1px solid #dee2e6',
                                'borderRadius': '0.5rem',
                                'backgroundColor': 'transparent'
                            }
                        )
                    ),
                    dbc_Col(
                        dcc.Graph(
                            id={'type': 'feedback-graph', 'section': 'feedback', 'key': 'estimated-maximum-daily-energy'},
                            config={'displayModeBar': False},
                            style={
                                'height': '120px',
                                'border': '1px solid #dee2e6',
                                'borderRadius': '0.5rem',
                                'backgroundColor': 'transparent'
                            }
                        )
                    )
                ])
            ])
        ])
    ])

_feedback_graph_bar = partial(
    px.bar,
    x = 'value',
    color = 'label',
    orientation = 'h'
)

_feedback_graph_layout = dict(
    height=120,
    margin={'l': 0, 'r': 0, 't': 28, 'b': 0},
    title={
        'x': 0.5,
        'xanchor': 'center',
        'yanchor': 'top',
        'font': {'size': 12, 'family': 'Arial', 'color': '#212529', 'weight': 'bold'}
    },
    showlegend=False,
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    bargap=0.75
)


@register_feedback_graph_artist('estimated-annual-energy', 'default')
def _(
    project_id: str, 
    project_provider: NewsegsProjectProviderInterface,
    eb: energy_balance_estimation.EstimatedEnergyBalance | None = None
):
    mm = get_focussed_metamodel(project_id, project_provider)
    if not eb:
        eb = energy_balance_estimation.EstimatedEnergyBalance()

    eb = update_estimated_energy_balance(mm, eb)

    df = eb.estimated_annual_energy_balance

    fig_ann = _feedback_graph_bar(df, y = 'type')
    fig_ann.update_layout(**_feedback_graph_layout) # pyright: ignore[reportArgumentType]
    fig_ann.update_layout(title = {'text': 'Annual'})
    fig_ann.update_traces(width=0.35, marker_line_width=0)
    fig_ann.update_xaxes(showticklabels=False, title_text=None, showgrid=False, zeroline=False)
    fig_ann.update_yaxes(showticklabels=True, title_text=None, showgrid=False, zeroline=False)

    return fig_ann

@register_feedback_graph_artist('estimated-maximum-daily-energy', 'default')
def _(
    project_id: str, 
    project_provider: NewsegsProjectProviderInterface,
    eb: energy_balance_estimation.EstimatedEnergyBalance | None = None
):
    mm = get_focussed_metamodel(project_id, project_provider)
    if not eb:
        eb = energy_balance_estimation.EstimatedEnergyBalance()

    eb = update_estimated_energy_balance(mm, eb)

    df = eb.estimated_maximum_daily_balance
    fig_max = _feedback_graph_bar(df, y = 'label')
    fig_max.update_layout(**_feedback_graph_layout) # pyright: ignore[reportArgumentType]
    fig_max.update_layout(title = {'text': '(Max) Daily'})
    fig_max.update_traces(width=0.35, marker_line_width=0)
    fig_max.update_xaxes(showticklabels=False, title_text=None, showgrid=False, zeroline=False)
    fig_max.update_yaxes(showticklabels=True, title_text=None, showgrid=False, zeroline=False)

    return fig_max