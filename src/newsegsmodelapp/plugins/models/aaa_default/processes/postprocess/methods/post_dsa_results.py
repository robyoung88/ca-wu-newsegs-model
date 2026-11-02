"""Conversion of the results of a DSA into tables.
"""
import pandas as pd

def _melt_dsa(df, scale_label = 'absolute'):
    df = df.reset_index()
    variable_order = df['variable'].unique()
    odf = (
        df
        .melt(
            id_vars=['variable', 'bound'],
            var_name = 'statistic',
            value_name = 'value'
        )
        .set_index(['variable', 'statistic'])
        .pivot(
            columns = 'bound',
            values = ['value']
        )
        .loc[variable_order, :]
    )
    bound_names = odf.columns.levels[1]
    odf.columns = pd.MultiIndex.from_product(
        [[scale_label], bound_names], names = ['scale', 'bound']
    )
    return odf

def _interval_width(
    df,
    bound_variable: str = 'bound',
    bound_values: tuple[str, str] = ('lower', 'upper')
):
    odata = (
        df.xs(bound_values[1], axis = 1, level = bound_variable, drop_level = True)
        - df.xs(bound_values[0], axis = 1, level = bound_variable, drop_level = True)
    ).abs()

    odata.columns = pd.MultiIndex.from_product([df.columns.levels[0], ['interval']], names = ['scale', 'bound'])
    return odata

def _deltas_dsa(
    det_value_data,
    sens_value_data
):
    # Trust numpy to do a sensible broadcast
    da = det_value_data.to_numpy()
    sa = sens_value_data.to_numpy()

    deltas = sa - da

    return _melt_dsa(
        pd.DataFrame(
            deltas,
            index = sens_value_data.index,
            columns = sens_value_data.columns
        ),
        'delta'
    )

def dsa_results_to_tables(
    dsa_data: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    
    """Convert the results of a DSA into tables.

    The first row of the data is the deterministic run, the others the runs with each variable at its bounds. Raises `TypeError` if the data are not long enough.

    Args:
        dsa_data: Dataframe of the results of the DSA.

    Returns:
        The tables: the deterministic result, and the sensitivities with their labels.
    """
    if len(dsa_data) < 2:
        raise TypeError('dsa_data is not long enough')

    # Deterministic results
    det = dsa_data.loc[[('deterministic', 'central')], :]
    det_value_data = det.drop(columns = ['value'])

    # Cannot anti-join on Pandas < 3.0
    #sens = pd.merge(dsa_data, det, how='left_anti', left_index = True, right_index=True)
    sens = dsa_data.iloc[range(1, len(dsa_data)), :] # pyright: ignore[reportArgumentType, reportCallIssue]
    sens_label_data = sens.loc[:, ['value']]
    sens_value_data = sens.drop(columns = ['value'])

    det_long = _melt_dsa(det_value_data)
    sens_long = _melt_dsa(sens_value_data)

    intervals = _interval_width(sens_long)

    deltas_long = _deltas_dsa(
        det_value_data,
        sens_value_data
    )

    dsa_table_data = (
        sens_long
        .join(intervals)
        .join(deltas_long)
        .reset_index()
        .set_index('statistic')
        .join(
            det_long
            .reset_index()
            .set_index('statistic')
            .drop(columns = ('variable', ''))
        )
        .reset_index()
        .set_index(['variable', 'statistic'])
    )

    dsa_label_data = _melt_dsa(sens_label_data.rename(columns={'value': 'variable_value'}))

    return (dsa_table_data, dsa_label_data)
