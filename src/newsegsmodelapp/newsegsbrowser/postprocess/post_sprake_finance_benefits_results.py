from newsegsmodelframework.newsegsmodel.sprakemodel import SprakeModel
from newsegsmodelframework.newsegsfinance.sprakefinance import SprakeFinance

from newsegsmodelframework.newsegsstats.core import assign_year_index
from newsegsmodelframework.newsegsstats import basic_summary_stats

def finance_benefits_results_to_interface_sprake(
    mdl: SprakeModel,
    fnc: SprakeFinance
) -> dict:
    """
    Extracts the financial benefits results required for the Dash interface
    """
    # This holds our final returned data structure
    results_to_interface = {}

    n_units = mdl.consumption_storage.n_units

    resident_receipts = fnc.resident_receipts_undiscounted
    ev_receipts = fnc.ev_receipts_undiscounted
    export_receipts = fnc.export_receipts_undiscounted

    receipts = (
        resident_receipts
        .loc[:,['receipts']]
        .rename(columns = {'receipts': 'receipts_resident'})
        .assign(receipts_resident_perunit = lambda df: df['receipts_resident'] / n_units)
        .join(
            ev_receipts
            .loc[:, ['receipts']]
            .rename(columns = {'receipts': 'receipts_ev'})
        )
        .join(
            export_receipts
            .loc[:, ['receipts']]
            .rename(columns = {'receipts': 'receipts_exports'})
        )
        .assign(
            receipts_total = lambda df: df.sum(axis=1)
        )
    )

    undiscounted_receipts_summaries = (
        receipts
        .pipe(assign_year_index)
        .query('year_index >= 0')
        .pipe(basic_summary_stats.meter_annual_summary2)
    )

    results_to_interface['undiscounted_receipts_summaries'] = (
        undiscounted_receipts_summaries
        .pipe(basic_summary_stats.meter_annual_summary2_to_interface)
    )

    results_to_interface['present_benefits_undiscounted'] = fnc.get_total_present_benefits_undiscounted()
    results_to_interface['present_benefits_discounted'] = fnc.get_total_present_benefits_discounted()
    results_to_interface['benefits_discount_rate'] = fnc.benefit_discount_rate

    # Results used by the summary headers
    undiscounted_receipts_summaries = undiscounted_receipts_summaries.set_index(['variable','statistic'])
    results_to_interface['smry_residential_peryear'] = float(undiscounted_receipts_summaries.loc[('receipts_resident', 'mean'), 'value'])
    results_to_interface['smry_exports_peryear'] = float(undiscounted_receipts_summaries.loc[('receipts_exports', 'mean'),'value'])

    return results_to_interface
