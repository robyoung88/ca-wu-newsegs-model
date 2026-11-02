"""The results sections of the deterministic page for the Sprake model: which results are shown, in which cards.
"""
from newsegsmodelapp.components.layouts.results_card import create_results_table_card
from newsegsmodelapp.components import icons


def create_generation_results_card():
    """
    A Bootstrap card holding results for generation
    """
    return create_results_table_card(
        'deterministic',
        'tabledraw',
        key = 'table_generation',
        title = [icons.get_icon('generation'), 'Generation Results'],
        header_section = 'postprocess',
        header_key = 'postproc_generation'
    )

def create_storage_results_card():
    """
    A Bootstrap card holding results for storage
    """
    return create_results_table_card(
        'deterministic',
        'tabledraw',
        key = 'table_storage',
        title = [icons.get_icon('storage'), 'Storage Results'],
        header_section = 'postprocess',
        header_key = 'postproc_storage'
    )

def create_consumption_results_card():
    """
    A Bootstrap card holding results for consumption
    """
    return create_results_table_card(
        'deterministic',
        'tabledraw',
        key = 'table_consumption',
        title = [icons.get_icon('consumption-direct'), 'Consumption Results'],
        header_section = 'postprocess',
        header_key = 'postproc_consumption'
    )

def create_net_results_card():
    """
    A Bootstrap card holding results for net energy flow
    """
    return create_results_table_card(
        'deterministic',
        'tabledraw',
        key  = 'table_net',
        title = [icons.get_icon('import-export'), 'Net Energy Results'],
        header_section = 'postprocess',
        header_key = 'postproc_net'
    )

def create_finance_results_so_card():
    """
    A Bootstrap card holding results for finance results (system owner)
    """
    return create_results_table_card(
        'deterministic',
        'tabledraw',
        key = 'table_finance',
        title = [icons.get_icon('cost'), 'Financial Results - System Owner'],
        header_section = 'tabledraw',
        header_key = 'table_finance'
    )
