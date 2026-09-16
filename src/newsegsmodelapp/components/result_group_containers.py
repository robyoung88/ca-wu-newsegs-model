from dash import html


def result_group_container(
    section: str,
    supersection: str
):
    return (
        html.Div(id = {'type': 'result-options-container', 'section': section, 'supersection': supersection}),
        html.Div(id = {'type': ''})
    )

def figure_container(
    triggering_section: str,
    triggering_key: str,
):
    ...