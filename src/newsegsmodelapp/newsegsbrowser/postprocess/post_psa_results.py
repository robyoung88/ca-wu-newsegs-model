import pandas as pd

from newsegsmodelframework.newsegssensitivity import psa

def psa_results_to_tables(
    psa_results: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    return psa.basic_psa_stats(psa_results)
