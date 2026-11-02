"""Post psa results module.

TODO: Describe the purpose of the module.
"""
import pandas as pd

from newsegsmodelframework.newsegssensitivity import psa

def psa_results_to_tables(
    psa_results: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Psa results to tables.

    TODO: Add a description.

    Args:
        psa_results: TODO.

    Returns:
        TODO.
    """
    return psa.basic_psa_stats(psa_results)
