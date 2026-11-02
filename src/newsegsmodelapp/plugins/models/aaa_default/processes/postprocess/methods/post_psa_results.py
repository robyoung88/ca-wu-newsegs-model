"""Conversion of the results of a PSA into tables.
"""
import pandas as pd

from newsegsmodelframework.newsegssensitivity import psa

def psa_results_to_tables(
    psa_results: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Convert the results of a PSA into tables of summary statistics.

    Args:
        psa_results: Dataframe of the results of the PSA.

    Returns:
        The tables.
    """
    return psa.basic_psa_stats(psa_results)
