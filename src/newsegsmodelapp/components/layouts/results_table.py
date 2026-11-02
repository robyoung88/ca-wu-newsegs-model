import dash_ag_grid as dag

from newsegsmodelapp.components import icons

# Label fields that may lead a record, in display order. Consecutive equal
# values of a spanned field are merged into a single cell.
_LABEL_FIELDS = {
    'variable': {'flex': 3, 'minWidth': 220, 'spanRows': True},
    'season': {'flex': 1, 'minWidth': 80, 'spanRows': True},
    'statistic': {'flex': 1, 'minWidth': 100},
}

# Zoomable date cells hold a dict of {'label', 'start'[, 'end']}. Avoids `typeof`,
# which dash-ag-grid's function-string evaluator does not support.
_JS_IS_ZOOM_CELL = "params.value && params.value.label"

# Rows flagged '_wrap' are given a fixed two-line height. Fixed heights avoid the
# per-cell measurement of `autoHeight`, which dominated grid mount time.
_WRAP_ROW_HEIGHT = 60

def _config_icon_class(idx):
    """The full class string for the header icon of config idx (zero-based)"""
    return ' '.join([
        icons.get_icon(f'config-{idx+1}', style_name='raw'),
        'p-1 m-2',
        icons.ICON_COLOUR_CLASSES[idx % len(icons.ICON_COLOUR_CLASSES)]
    ])

def create_result_grid(
    records: list[dict],
    n_configs: int,
    grid_id: dict,
    none_str: str = '-'
) -> dag.AgGrid:
    """
    Render records from the stats *_records functions as an AG Grid.

    Configurations missing from the records are shown as none_str. Clicks on
    zoomable date cells arrive through the grid's `cellClicked` prop; give
    grid_id a 'type' of 'result-grid' to have them zoom the timeseries.
    """
    config_keys = [f'config-{x+1}' for x in range(n_configs)]
    records = [{k: none_str for k in config_keys} | rec for rec in records]
    label_fields = [x for x in _LABEL_FIELDS if records and x in records[0]]

    column_defs = [
        {
            'field': field,
            'headerName': '',
            'wrapText': True,
            **_LABEL_FIELDS[field],
        } for field in label_fields
    ]
    if 'statistic' in label_fields:
        column_defs[-1]['cellStyle'] = {'function': "params.data._align_end ? {textAlign: 'end'} : null"}

    column_defs += [
        {
            'field': key,
            'headerComponent': 'ResultConfigHeader',
            'headerComponentParams': {'iconClassName': _config_icon_class(x)},
            'cellDataType': False,
            'flex': 2,
            'minWidth': 120,
            'wrapText': True,
            'valueFormatter': {'function': f"{_JS_IS_ZOOM_CELL} ? params.value.label : params.value"},
            'cellStyle': {'function': (
                f"{_JS_IS_ZOOM_CELL} ? "
                "{cursor: 'zoom-in', lineHeight: '1.4', display: 'flex', alignItems: 'center'} : null"
            )},
        } for x, key in enumerate(config_keys)
    ]

    return dag.AgGrid(
        id = grid_id,
        rowData = records,
        columnDefs = column_defs,
        defaultColDef = {
            'sortable': False,
            'suppressMovable': True,
            'resizable': True,
        },
        dashGridOptions = {
            'enableCellSpan': True,
            'domLayout': 'autoHeight',
            'suppressCellFocus': True,
            'getRowHeight': {'function': f"params.data._wrap ? {_WRAP_ROW_HEIGHT} : null"},
        },
        style = {'height': None},
    )
