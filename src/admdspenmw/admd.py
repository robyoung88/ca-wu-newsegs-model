import os

import numpy as np
import pandas as pd

from admdspenmw import PACKAGEDIR

lookups = pd.read_csv(os.path.join(PACKAGEDIR,'data','admd_lookups.csv'))\
    .set_index('diversity_level')

def diversity_level(N_customers:int) -> int:
    match 1:
        case 1 if (N_customers < 5):
            return 1
        case 1 if (N_customers < 10):
            return 5
        case 1 if (N_customers < 15):
            return 10
        case 1 if (N_customers < 20):
            return 15
        case 1 if (N_customers < 25):
            return 20
        case 1 if (N_customers < 50):
            return 25
        case 1 if (N_customers < 81):
            return 50
        case 1 if (N_customers < 102):
            return 100
        case _:
            return 200
        
def EV_NSC(diversity_level:int,
           N_EV_chargers:float
           ) -> float:
    return lookups.loc[diversity_level,'EV_NSC_standard_perunit'] * N_EV_chargers

def EV_SC(diversity_level:int,
          N_EV_chargers:float
          ) -> float:
    return lookups.loc[diversity_level,'EV_SC_standard_perunit'] * N_EV_chargers

def EV_total(EV_NSC:float,
             EV_SC:float,
             smart_charging:bool
             ) -> float:
    if smart_charging:
        return EV_SC
    else:
        return EV_NSC

def ASHP_5kW_standard(diversity_level:int,
                      N_ASHP_5kW:float
                      ) -> float:
    return lookups.loc[diversity_level,'ASHP_5kW_standard_perunit'] * N_ASHP_5kW

def ASHP_8kW_standard(diversity_level:int,
                      N_ASHP_8kW:float
                      ) -> float:
    return lookups.loc[diversity_level,'ASHP_8kW_standard_perunit'] * N_ASHP_8kW

def ASHP_16kW_standard(diversity_level:int,
                       N_ASHP_16kW:float
                       ) -> float:
    return lookups.loc[diversity_level,'ASHP_16kW_standard_perunit'] * N_ASHP_16kW

def ASHP_standard_total(ASHP_5kW_standard:float,
                        ASHP_8kW_standard:float,
                        ASHP_16kW_standard:float
                        ) -> float:
    return ASHP_5kW_standard + ASHP_8kW_standard + ASHP_16kW_standard

def GSHP_5kW_standard(diversity_level:int,
                      N_GSHP_5kW:float
                      ) -> float:
    return lookups.loc[diversity_level,'GSHP_5kW_standard_perunit'] * N_GSHP_5kW

def GSHP_8kW_standard(diversity_level:int,
                      N_GSHP_8kW:float
                      ) -> float:
    return lookups.loc[diversity_level,'GSHP_8kW_standard_perunit'] * N_GSHP_8kW

def GSHP_16kW_standard(diversity_level:int,
                       N_GSHP_16kW:float
                       ) -> float:
    return lookups.loc[diversity_level,'GSHP_16kW_standard_perunit'] * N_GSHP_16kW

def GSHP_standard_total(GSHP_5kW_standard:float,
                        GSHP_8kW_standard:float,
                        GSHP_16kW_standard:float
                        ) -> float:
    return GSHP_5kW_standard + GSHP_8kW_standard + GSHP_16kW_standard

def HyHP_5kW_standard(diversity_level:int,
                      N_HyHP_5kW:float
                      ) -> float:
    return lookups.loc[diversity_level,'HyHP_5kW_standard_perunit'] * N_HyHP_5kW

def HyHP_8kW_standard(diversity_level:int,
                      N_HyHP_8kW:float
                      ) -> float:
    return lookups.loc[diversity_level,'HyHP_8kW_standard_perunit'] * N_HyHP_8kW

def HyHP_16kW_standard(diversity_level:int,
                       N_HyHP_16kW:float
                       ) -> float:
    return lookups.loc[diversity_level,'HyHP_16kW_standard_perunit'] * N_HyHP_16kW

def HyHP_standard_total(HyHP_5kW_standard:float,
                        HyHP_8kW_standard:float,
                        HyHP_16kW_standard:float
                        ) -> float:
    return HyHP_5kW_standard + HyHP_8kW_standard + HyHP_16kW_standard

def storage_5kW_standard(diversity_level:int,
                         N_storage_5kW:float
                         ) -> float:
    return lookups.loc[diversity_level,'storage_5kW_standard_perunit'] * N_storage_5kW

def storage_8kW_standard(diversity_level:int,
                         N_storage_8kW:float
                         ) -> float:
    return lookups.loc[diversity_level,'storage_8kW_standard_perunit'] * N_storage_8kW

def storage_16kW_standard(diversity_level:int,
                          N_storage_16kW:float
                          ) -> float:
    return lookups.loc[diversity_level,'storage_16kW_standard_perunit'] * N_storage_16kW

def storage_standard_total(storage_5kW_standard:float,
                           storage_8kW_standard:float,
                           storage_16kW_standard:float
                        ) -> float:
    return storage_5kW_standard + storage_8kW_standard + storage_16kW_standard

def N_ASHP(N_ASHP_5kW:float,
           N_ASHP_8kW:float,
           N_ASHP_16kW:float
           ) -> float:
    return N_ASHP_5kW + N_ASHP_8kW + N_ASHP_16kW

def N_GSHP(N_GSHP_5kW:float,
           N_GSHP_8kW:float,
           N_GSHP_16kW:float
           ) -> float:
    return N_GSHP_5kW + N_GSHP_8kW + N_GSHP_16kW

def N_HyHP(N_HyHP_5kW:float,
           N_HyHP_8kW:float,
           N_HyHP_16kW:float
           ) -> float:
    return N_HyHP_5kW + N_HyHP_8kW + N_HyHP_16kW

def N_storage(N_storage_5kW:float,
              N_storage_8kW:float,
              N_storage_16kW:float
              ) -> float:
    return N_storage_5kW + N_storage_8kW + N_storage_16kW

def N_no_lct(N_customers:int,
             N_EV_chargers:float,
             N_EV_and_HP:float,
             N_ASHP:float,
             N_GSHP:float,
             N_HyHP:float,
             N_storage:float
             ) -> float:
    return N_customers - (N_EV_chargers - N_EV_and_HP) - N_ASHP - N_GSHP - N_HyHP - N_storage 

def no_lct_standard_total(diversity_level:int,
                          N_no_lct:float
                          ) -> float:
    return lookups.loc[diversity_level,'house_only_per_unit'] * N_no_lct

def admd_standard_subtotal_1(EV_total:float,
                             ASHP_standard_total:float,
                             GSHP_standard_total:float,
                             HyHP_standard_total:float,
                             storage_standard_total:float,
                             no_lct_standard_total:float
                             ) -> float:
    return EV_total + ASHP_standard_total + GSHP_standard_total + HyHP_standard_total + storage_standard_total + no_lct_standard_total

def ADMD_standard(diversity_level:int,
                  admd_standard_subtotal_1:float,
                  N_EV_and_HP:float
                  ) -> float:
    return (
        admd_standard_subtotal_1
            - N_EV_and_HP * lookups.loc[diversity_level,'ev_hp_cofactor']
    )

def ASHP_5kW_coldload(diversity_level:int,
                      N_ASHP_5kW:float
                      ) -> float:
    return lookups.loc[diversity_level,'ASHP_5kW_coldload_perunit'] * N_ASHP_5kW

def ASHP_8kW_coldload(diversity_level:int,
                      N_ASHP_8kW:float
                      ) -> float:
    return lookups.loc[diversity_level,'ASHP_8kW_coldload_perunit'] * N_ASHP_8kW

def ASHP_16kW_coldload(diversity_level:int,
                       N_ASHP_16kW:float
                       ) -> float:
    return lookups.loc[diversity_level,'ASHP_16kW_coldload_perunit'] * N_ASHP_16kW

def ASHP_coldload_total(ASHP_5kW_coldload:float,
                        ASHP_8kW_coldload:float,
                        ASHP_16kW_coldload:float
                        ) -> float:
    return ASHP_5kW_coldload + ASHP_8kW_coldload + ASHP_16kW_coldload

def GSHP_5kW_coldload(diversity_level:int,
                      N_GSHP_5kW:float
                      ) -> float:
    return lookups.loc[diversity_level,'GSHP_5kW_coldload_perunit'] * N_GSHP_5kW

def GSHP_8kW_coldload(diversity_level:int,
                      N_GSHP_8kW:float
                      ) -> float:
    return lookups.loc[diversity_level,'GSHP_8kW_coldload_perunit'] * N_GSHP_8kW

def GSHP_16kW_coldload(diversity_level:int,
                       N_GSHP_16kW:float
                       ) -> float:
    return lookups.loc[diversity_level,'GSHP_16kW_coldload_perunit'] * N_GSHP_16kW

def GSHP_coldload_total(GSHP_5kW_coldload:float,
                        GSHP_8kW_coldload:float,
                        GSHP_16kW_coldload:float
                        ) -> float:
    return GSHP_5kW_coldload + GSHP_8kW_coldload + GSHP_16kW_coldload

def HyHP_5kW_coldload(diversity_level:int,
                      N_HyHP_5kW:float
                      ) -> float:
    return lookups.loc[diversity_level,'HyHP_5kW_coldload_perunit'] * N_HyHP_5kW

def HyHP_8kW_coldload(diversity_level:int,
                      N_HyHP_8kW:float
                      ) -> float:
    return lookups.loc[diversity_level,'HyHP_8kW_coldload_perunit'] * N_HyHP_8kW

def HyHP_16kW_coldload(diversity_level:int,
                       N_HyHP_16kW:float
                       ) -> float:
    return lookups.loc[diversity_level,'HyHP_16kW_coldload_perunit'] * N_HyHP_16kW

def HyHP_coldload_total(HyHP_5kW_coldload:float,
                        HyHP_8kW_coldload:float,
                        HyHP_16kW_coldload:float
                        ) -> float:
    return HyHP_5kW_coldload + HyHP_8kW_coldload + HyHP_16kW_coldload

def admd_coldload_subtotal_1(EV_total:float,
                             ASHP_coldload_total:float,
                             GSHP_coldload_total:float,
                             HyHP_coldload_total:float,
                             storage_standard_total:float,
                             no_lct_standard_total:float
                             ) -> float:
    return EV_total + ASHP_coldload_total + GSHP_coldload_total + HyHP_coldload_total + storage_standard_total + no_lct_standard_total

def ADMD_coldload(diversity_level:int,
                  admd_coldload_subtotal_1:float,
                  N_EV_and_HP:float
                  ) -> float:
    return (
        admd_coldload_subtotal_1
            - N_EV_and_HP * lookups.loc[diversity_level,'ev_hp_coldload_cofactor']
    )
    
def ASHP_count(type_:np.ndarray[tuple[int], np.dtype(str)],
               beds:np.ndarray[tuple[int], np.dtype(int)]
               ) -> dict:
    is_apt = type_ == 'apt'
    is_5kW = np.logical_or(
        is_apt,
        beds < 3
    )
    is_8kW = np.logical_and(
        np.logical_not(is_apt),
        np.logical_and(
            beds >= 3,
            beds < 5
        )
    )
    is_16kW = np.logical_and(
        np.logical_not(is_apt),
        beds >= 5
    )
    return {
        'N_ASHP_5kW': float(np.sum(is_5kW)),
        'N_ASHP_8kW': float(np.sum(is_8kW)),
        'N_ASHP_16kW': float(np.sum(is_16kW))
    }

def GSHP_count(type_:np.ndarray[tuple[int], np.dtype(str)],
               beds:np.ndarray[tuple[int], np.dtype(int)]
               ) -> dict:
    is_apt = type_ == 'apt'
    is_5kW = np.logical_or(
        is_apt,
        beds < 3
    )
    is_8kW = np.logical_and(
        np.logical_not(is_apt),
        np.logical_and(
            beds >= 3,
            beds < 5
        )
    )
    is_16kW = np.logical_and(
        np.logical_not(is_apt),
        beds >= 5
    )
    return {
        'N_GSHP_5kW': float(np.sum(is_5kW)),
        'N_GSHP_8kW': float(np.sum(is_8kW)),
        'N_GSHP_16kW': float(np.sum(is_16kW))
    }

def HyHP_count(type_:np.ndarray[tuple[int], np.dtype(str)],
               beds:np.ndarray[tuple[int], np.dtype(int)]
               ) -> dict:
    is_apt = type_ == 'apt'
    is_5kW = np.logical_or(
        is_apt,
        beds < 3
    )
    is_8kW = np.logical_and(
        np.logical_not(is_apt),
        np.logical_and(
            beds >= 3,
            beds < 5
        )
    )
    is_16kW = np.logical_and(
        np.logical_not(is_apt),
        beds >= 5
    )
    return {
        'N_HyHP_5kW': float(np.sum(is_5kW)),
        'N_HyHP_8kW': float(np.sum(is_8kW)),
        'N_HyHP_16kW': float(np.sum(is_16kW))
    }

def storage_count(type_:np.ndarray[tuple[int], np.dtype(str)],
               beds:np.ndarray[tuple[int], np.dtype(int)]
               ) -> dict:
    is_apt = type_ == 'apt'
    is_5kW = np.logical_or(
        is_apt,
        beds < 3
    )
    is_8kW = np.logical_and(
        np.logical_not(is_apt),
        np.logical_and(
            beds >= 3,
            beds < 5
        )
    )
    is_16kW = np.logical_and(
        np.logical_not(is_apt),
        beds >= 5
    )
    return {
        'N_storage_5kW': float(np.sum(is_5kW)),
        'N_storage_8kW': float(np.sum(is_8kW)),
        'N_storage_16kW': float(np.sum(is_16kW))
    }
