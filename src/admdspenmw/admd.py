"""After Diversity Maximum Demand (ADMD) calculation for housing with low carbon technologies.

A Python version of the *Public ADMD Calculator V1.1* spreadsheet published by SP Energy
Networks for the SP Manweb area (the `spenmw` of the package name); see
[the calculator](https://www.spenergynetworks.co.uk/pages/admd_calculator.aspx). It estimates the
maximum demand, in kW, that a group of customers on a feeder places on the network after
allowing for diversity - the fact that individual peaks do not coincide - when some
households have electric vehicle (EV) chargers, heat pumps or storage heating.

Two results are produced:

- `ADMD_standard` - under standard (peak) conditions;
- `ADMD_coldload` - under cold load pickup conditions, when supply is restored after an
  interruption and heating loads run simultaneously.

## Structure

The functions form a dataflow graph for [Hamilton](https://hamilton.apache.org): the name of each
function is the name of the value it calculates, and its parameters are the names of the
values it depends on - either other functions of this module, or inputs
(`N_customers`, `N_EV_chargers`, `N_EV_and_HP`, `smart_charging` and the `N_<type>_<size>kW`
counts of heat pumps and storage heating; see `model_config.default_model_inputs`). A Hamilton
driver (see `newsegsmodelframework.util.admd_helpers`) executes only what is needed for the
outputs requested. The calculation proceeds:

1. `diversity_level` - from the number of customers.
2. Per-group ADMD - `EV_total` (from `EV_NSC` or `EV_SC`); `<type>_<size>kW_standard` and
   `<type>_<size>kW_coldload` for `ASHP`, `GSHP` and `HyHP`; `storage_<size>kW_standard`;
   `no_lct_standard_total` for households with no low carbon technology (LCT), whose number
   is `N_no_lct`. Each is a per-household value from `data/admd_lookups.csv` at the diversity
   level, multiplied by a number of households.
3. Totals per type - `<type>_standard_total`, `<type>_coldload_total`.
4. `admd_standard_subtotal_1` and `admd_coldload_subtotal_1` - sums of the groups.
5. `ADMD_standard` and `ADMD_coldload` - the subtotals less a correction for households
   counted twice because they have both an EV charger and a heat pump.

`ASHP_count`, `GSHP_count`, `HyHP_count` and `storage_count` are helpers (not nodes of the
graph) that size systems from the types and bedrooms of dwellings.

## Assumptions

From the calculator's *Assumptions* sheet:

- Sizes: 5 kW is for a 1-2 bedroom house, 8 kW for a 3-4 bedroom house and 16 kW for a
  5+ bedroom house, with insulation to 1990s standard or better.
- Domestic EV charge points are 7.36 kW; smart charging (a control that reduces EV charging
  during peak hours) is modelled as 3.68 kW.
- ASHPs provide space heating and hot water and include a direct electric backup
  heater. GSHPs and hybrid heat pumps have no backup heater. Hybrid heat pumps are bi-valent,
  switching to gas below 8 °C. Storage heating provides space heating only.
- A standalone household with no LCT has an ADMD of about 2 kW (1.8 kW in the tables
  at 100 customers).

Undiversified electrical load of each system (kW), standard / cold load pickup:

| System | 5 kW | 8 kW | 16 kW |
|---|---|---|---|
| ASHP | 2.41 / 3.38 | 4.68 / 6.55 | 9.37 / 13.12 |
| GSHP | 2.6 | 3.8 | 6.5 |
| Hybrid | 1.22 | 2.69 | 4.57 |
| Storage heating | 5 | 8 | 16 |

## Differences from the spreadsheet

- The battery storage reduction of the spreadsheet is not implemented (it refers to a
  missing cell in V1.1).
- The spreadsheet's three input columns (bedroom bands, each with one average heat pump
  size) and its combination of the three using a "Total Diversity Level" are replaced by
  counts of systems by size; see `ASHP_count`.
- More than 101 customers use diversity level 200, rather than `N/A`.
- The `ADMD_*` results are totals for the feeder, not an average per household.
- At diversity level 20 the spreadsheet's house-only table gives 2.4 kW but its standalone
  household formula uses 2.2 kW; the lookup table here uses 2.2 kW for standalone households.
"""
import os

import numpy as np
import pandas as pd

from admdspenmw import PACKAGEDIR

lookups = pd.read_csv(os.path.join(PACKAGEDIR,'data','admd_lookups.csv'))\
    .set_index('diversity_level')

def diversity_level(N_customers:int) -> int:
    """Diversity level for a number of customers on the feeder.

    The ADMD of a group of customers falls, per customer, as the group gets larger, because
    their peak demands do not coincide. The calculator therefore tabulates demand for a
    set of *diversity levels* (the number of customers the tabulated value is for), and the
    level to use is chosen from the number of customers:

    | Customers | Diversity level |
    |---|---|
    | 1 - 4 | 1 |
    | 5 - 9 | 5 |
    | 10 - 14 | 10 |
    | 15 - 19 | 15 |
    | 20 - 24 | 20 |
    | 25 - 49 | 25 |
    | 50 - 80 | 50 |
    | 81 - 101 | 100 |
    | 102 or more | 200 |

    This is the "Establish Diversity Level" row of the spreadsheet. The spreadsheet gives
    `N/A` for more than 101 customers; here level 200 is used instead, which has the same
    values as level 100 in `admd_lookups.csv`.

    Args:
        N_customers: Number of customers (households) on the feeder.

    Returns:
        The diversity level; the index of the lookup table.
    """
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
    """ADMD of the electric vehicle chargers with no smart charging (standard conditions).

    Per-household demand for a household with a 7.36 kW (or two 3.68 kW) charger without
    smart charging, at the diversity level, multiplied by the number of chargers. The per-unit
    value includes the base household demand.
    Spreadsheet row: "Calculate Non Smart Charge Value".

    Args:
        diversity_level: Diversity level, from `diversity_level`.
        N_EV_chargers: Number of households with an EV charger.

    Returns:
        ADMD in kW of the households with EV chargers.
    """
    return lookups.loc[diversity_level,'EV_NSC_standard_perunit'] * N_EV_chargers

def EV_SC(diversity_level:int,
          N_EV_chargers:float
          ) -> float:
    """ADMD of the electric vehicle chargers with smart charging (standard conditions).

    As `EV_NSC`, for chargers with smart charging - a control function that reduces EV
    charging demand during peak hours (the spreadsheet models it as a 3.68 kW charge point).
    Spreadsheet row: "Calculate Smart Charge Value".

    Args:
        diversity_level: Diversity level, from `diversity_level`.
        N_EV_chargers: Number of households with an EV charger.

    Returns:
        ADMD in kW of the households with EV chargers.
    """
    return lookups.loc[diversity_level,'EV_SC_standard_perunit'] * N_EV_chargers

def EV_total(EV_NSC:float,
             EV_SC:float,
             smart_charging:bool
             ) -> float:
    """ADMD of the electric vehicle chargers, with or without smart charging.

    Selects `EV_SC` if smart charging is present, otherwise `EV_NSC`. The same value is used
    for the standard and cold load pickup calculations.
    Spreadsheet row: "Calculate EV Total".

    Args:
        EV_NSC: ADMD with no smart charging, from `EV_NSC`.
        EV_SC: ADMD with smart charging, from `EV_SC`.
        smart_charging: Whether the chargers have smart charging.

    Returns:
        ADMD in kW of the households with EV chargers.
    """
    if smart_charging:
        return EV_SC
    else:
        return EV_NSC

def ASHP_5kW_standard(diversity_level:int,
                      N_ASHP_5kW:float
                      ) -> float:
    """ADMD of the households with a 5 kW ASHP under standard (peak) conditions.

    The per-household demand at the diversity level (column `ASHP_5kW_standard_perunit` of
    `admd_lookups.csv`) multiplied by the number of households. The 5 kW size is for a 1-2
    bedroom house, with insulation to 1990s standard or better; the heating system is an
    air source heat pump (ASHP) with a 5 kW heat output which provides space heating and
    hot water and includes a direct electric backup heater. Its undiversified demand is
    2.41 kW electrical. The per- household value includes the base household demand.
    Spreadsheet row: "Calculate 5kW ASHP Total".

    Args:
        diversity_level: Diversity level, from `diversity_level`.
        N_ASHP_5kW: Number of households with this system.

    Returns:
        ADMD in kW of those households (a total, not a value per household).
    """
    return lookups.loc[diversity_level,'ASHP_5kW_standard_perunit'] * N_ASHP_5kW

def ASHP_8kW_standard(diversity_level:int,
                      N_ASHP_8kW:float
                      ) -> float:
    """ADMD of the households with a 8 kW ASHP under standard (peak) conditions.

    The per-household demand at the diversity level (column `ASHP_8kW_standard_perunit` of
    `admd_lookups.csv`) multiplied by the number of households. The 8 kW size is for a 3-4
    bedroom house, with insulation to 1990s standard or better; the heating system is an
    air source heat pump (ASHP) with a 8 kW heat output which provides space heating and
    hot water and includes a direct electric backup heater. Its undiversified demand is
    4.68 kW electrical. The per- household value includes the base household demand.
    Spreadsheet row: "Calculate 8kW ASHP Total".

    Args:
        diversity_level: Diversity level, from `diversity_level`.
        N_ASHP_8kW: Number of households with this system.

    Returns:
        ADMD in kW of those households (a total, not a value per household).
    """
    return lookups.loc[diversity_level,'ASHP_8kW_standard_perunit'] * N_ASHP_8kW

def ASHP_16kW_standard(diversity_level:int,
                       N_ASHP_16kW:float
                       ) -> float:
    """ADMD of the households with a 16 kW ASHP under standard (peak) conditions.

    The per-household demand at the diversity level (column `ASHP_16kW_standard_perunit`
    of `admd_lookups.csv`) multiplied by the number of households. The 16 kW size is for a
    5+ bedroom house, with insulation to 1990s standard or better; the heating system is
    an air source heat pump (ASHP) with a 16 kW heat output which provides space heating
    and hot water and includes a direct electric backup heater. Its undiversified demand
    is 9.37 kW electrical. The per-household value includes the base household demand.
    Spreadsheet row: "Calculate 16kW ASHP Total".

    Args:
        diversity_level: Diversity level, from `diversity_level`.
        N_ASHP_16kW: Number of households with this system.

    Returns:
        ADMD in kW of those households (a total, not a value per household).
    """
    return lookups.loc[diversity_level,'ASHP_16kW_standard_perunit'] * N_ASHP_16kW

def ASHP_standard_total(ASHP_5kW_standard:float,
                        ASHP_8kW_standard:float,
                        ASHP_16kW_standard:float
                        ) -> float:
    """Total ADMD of all air source heat pump (ASHP) households under standard conditions.

    Sum of the 5 kW, 8 kW and 16 kW results. Spreadsheet row: "Calculate ASHP Total".

    Args:
        ASHP_5kW_standard: ADMD of the 5 kW systems.
        ASHP_8kW_standard: ADMD of the 8 kW systems.
        ASHP_16kW_standard: ADMD of the 16 kW systems.

    Returns:
        ADMD in kW of all households with this system.
    """
    return ASHP_5kW_standard + ASHP_8kW_standard + ASHP_16kW_standard

def GSHP_5kW_standard(diversity_level:int,
                      N_GSHP_5kW:float
                      ) -> float:
    """ADMD of the households with a 5 kW GSHP under standard (peak) conditions.

    The per-household demand at the diversity level (column `GSHP_5kW_standard_perunit` of
    `admd_lookups.csv`) multiplied by the number of households. The 5 kW size is for a 1-2
    bedroom house, with insulation to 1990s standard or better; the heating system is an
    ground source heat pump (GSHP) with a 5 kW heat output which provides space heating
    and hot water and has no backup heater. Its undiversified demand is 2.6 kW electrical.
    The per-household value includes the base household demand. Spreadsheet row:
    "Calculate 5kW GSHP Total".

    Args:
        diversity_level: Diversity level, from `diversity_level`.
        N_GSHP_5kW: Number of households with this system.

    Returns:
        ADMD in kW of those households (a total, not a value per household).
    """
    return lookups.loc[diversity_level,'GSHP_5kW_standard_perunit'] * N_GSHP_5kW

def GSHP_8kW_standard(diversity_level:int,
                      N_GSHP_8kW:float
                      ) -> float:
    """ADMD of the households with a 8 kW GSHP under standard (peak) conditions.

    The per-household demand at the diversity level (column `GSHP_8kW_standard_perunit` of
    `admd_lookups.csv`) multiplied by the number of households. The 8 kW size is for a 3-4
    bedroom house, with insulation to 1990s standard or better; the heating system is an
    ground source heat pump (GSHP) with a 8 kW heat output which provides space heating
    and hot water and has no backup heater. Its undiversified demand is 3.8 kW electrical.
    The per-household value includes the base household demand. Spreadsheet row:
    "Calculate 8kW GSHP Total".

    Args:
        diversity_level: Diversity level, from `diversity_level`.
        N_GSHP_8kW: Number of households with this system.

    Returns:
        ADMD in kW of those households (a total, not a value per household).
    """
    return lookups.loc[diversity_level,'GSHP_8kW_standard_perunit'] * N_GSHP_8kW

def GSHP_16kW_standard(diversity_level:int,
                       N_GSHP_16kW:float
                       ) -> float:
    """ADMD of the households with a 16 kW GSHP under standard (peak) conditions.

    The per-household demand at the diversity level (column `GSHP_16kW_standard_perunit`
    of `admd_lookups.csv`) multiplied by the number of households. The 16 kW size is for a
    5+ bedroom house, with insulation to 1990s standard or better; the heating system is
    an ground source heat pump (GSHP) with a 16 kW heat output which provides space
    heating and hot water and has no backup heater. Its undiversified demand is 6.5 kW
    electrical. The per-household value includes the base household demand. Spreadsheet
    row: "Calculate 16kW GSHP Total".

    Args:
        diversity_level: Diversity level, from `diversity_level`.
        N_GSHP_16kW: Number of households with this system.

    Returns:
        ADMD in kW of those households (a total, not a value per household).
    """
    return lookups.loc[diversity_level,'GSHP_16kW_standard_perunit'] * N_GSHP_16kW

def GSHP_standard_total(GSHP_5kW_standard:float,
                        GSHP_8kW_standard:float,
                        GSHP_16kW_standard:float
                        ) -> float:
    """Total ADMD of all ground source heat pump (GSHP) households under standard conditions.

    Sum of the 5 kW, 8 kW and 16 kW results. Spreadsheet row: "Calculate GSHP Total".

    Args:
        GSHP_5kW_standard: ADMD of the 5 kW systems.
        GSHP_8kW_standard: ADMD of the 8 kW systems.
        GSHP_16kW_standard: ADMD of the 16 kW systems.

    Returns:
        ADMD in kW of all households with this system.
    """
    return GSHP_5kW_standard + GSHP_8kW_standard + GSHP_16kW_standard

def HyHP_5kW_standard(diversity_level:int,
                      N_HyHP_5kW:float
                      ) -> float:
    """ADMD of the households with a 5 kW HyHP under standard (peak) conditions.

    The per-household demand at the diversity level (column `HyHP_5kW_standard_perunit` of
    `admd_lookups.csv`) multiplied by the number of households. The 5 kW size is for a 1-2
    bedroom house, with insulation to 1990s standard or better; the heating system is an
    hybrid heat pump with a 5 kW heat output which provides space heating and hot water,
    has no backup heater and is bi-valent: it switches to gas when the outside temperature
    falls below a threshold (8 °C in the spreadsheet). Its undiversified demand is 1.22 kW
    electrical. The per-household value includes the base household demand. Spreadsheet
    row: "Calculate 5kW Hybrid Total".

    Args:
        diversity_level: Diversity level, from `diversity_level`.
        N_HyHP_5kW: Number of households with this system.

    Returns:
        ADMD in kW of those households (a total, not a value per household).
    """
    return lookups.loc[diversity_level,'HyHP_5kW_standard_perunit'] * N_HyHP_5kW

def HyHP_8kW_standard(diversity_level:int,
                      N_HyHP_8kW:float
                      ) -> float:
    """ADMD of the households with a 8 kW HyHP under standard (peak) conditions.

    The per-household demand at the diversity level (column `HyHP_8kW_standard_perunit` of
    `admd_lookups.csv`) multiplied by the number of households. The 8 kW size is for a 3-4
    bedroom house, with insulation to 1990s standard or better; the heating system is an
    hybrid heat pump with a 8 kW heat output which provides space heating and hot water,
    has no backup heater and is bi-valent: it switches to gas when the outside temperature
    falls below a threshold (8 °C in the spreadsheet). Its undiversified demand is 2.69 kW
    electrical. The per-household value includes the base household demand. Spreadsheet
    row: "Calculate 8kW Hybrid Total".

    Args:
        diversity_level: Diversity level, from `diversity_level`.
        N_HyHP_8kW: Number of households with this system.

    Returns:
        ADMD in kW of those households (a total, not a value per household).
    """
    return lookups.loc[diversity_level,'HyHP_8kW_standard_perunit'] * N_HyHP_8kW

def HyHP_16kW_standard(diversity_level:int,
                       N_HyHP_16kW:float
                       ) -> float:
    """ADMD of the households with a 16 kW HyHP under standard (peak) conditions.

    The per-household demand at the diversity level (column `HyHP_16kW_standard_perunit`
    of `admd_lookups.csv`) multiplied by the number of households. The 16 kW size is for a
    5+ bedroom house, with insulation to 1990s standard or better; the heating system is
    an hybrid heat pump with a 16 kW heat output which provides space heating and hot
    water, has no backup heater and is bi-valent: it switches to gas when the outside
    temperature falls below a threshold (8 °C in the spreadsheet). Its undiversified
    demand is 4.57 kW electrical. The per- household value includes the base household
    demand. Spreadsheet row: "Calculate 16kW Hybrid Total".

    Args:
        diversity_level: Diversity level, from `diversity_level`.
        N_HyHP_16kW: Number of households with this system.

    Returns:
        ADMD in kW of those households (a total, not a value per household).
    """
    return lookups.loc[diversity_level,'HyHP_16kW_standard_perunit'] * N_HyHP_16kW

def HyHP_standard_total(HyHP_5kW_standard:float,
                        HyHP_8kW_standard:float,
                        HyHP_16kW_standard:float
                        ) -> float:
    """Total ADMD of all hybrid heat pump households under standard conditions.

    Sum of the 5 kW, 8 kW and 16 kW results. Spreadsheet row: "Calculate Hybrid Total".

    Args:
        HyHP_5kW_standard: ADMD of the 5 kW systems.
        HyHP_8kW_standard: ADMD of the 8 kW systems.
        HyHP_16kW_standard: ADMD of the 16 kW systems.

    Returns:
        ADMD in kW of all households with this system.
    """
    return HyHP_5kW_standard + HyHP_8kW_standard + HyHP_16kW_standard

def storage_5kW_standard(diversity_level:int,
                         N_storage_5kW:float
                         ) -> float:
    """ADMD of the households with a 5 kW storage heating system under standard (peak) conditions.

    The per-household demand at the diversity level (column `storage_5kW_standard_perunit`
    of `admd_lookups.csv`) multiplied by the number of households. The 5 kW size is for a
    1-2 bedroom house, with insulation to 1990s standard or better; the heating system is
    an electric storage heating system with a 5 kW electrical rating which provides space
    heating only. Its undiversified demand is 5 kW. The per-household value includes the
    base household demand. Spreadsheet row: "Calculate 5kW Storage Total".

    The spreadsheet has no separate cold load pickup values for storage heating, so there
    is no `storage_*_coldload` function: `storage_standard_total` is used in
    `admd_coldload_subtotal_1` too.

    Args:
        diversity_level: Diversity level, from `diversity_level`.
        N_storage_5kW: Number of households with this system.

    Returns:
        ADMD in kW of those households (a total, not a value per household).
    """
    return lookups.loc[diversity_level,'storage_5kW_standard_perunit'] * N_storage_5kW

def storage_8kW_standard(diversity_level:int,
                         N_storage_8kW:float
                         ) -> float:
    """ADMD of the households with a 8 kW storage heating system under standard (peak) conditions.

    The per-household demand at the diversity level (column `storage_8kW_standard_perunit`
    of `admd_lookups.csv`) multiplied by the number of households. The 8 kW size is for a
    3-4 bedroom house, with insulation to 1990s standard or better; the heating system is
    an electric storage heating system with a 8 kW electrical rating which provides space
    heating only. Its undiversified demand is 8 kW. The per-household value includes the
    base household demand. Spreadsheet row: "Calculate 8kW Storage Total".

    The spreadsheet has no separate cold load pickup values for storage heating, so there
    is no `storage_*_coldload` function: `storage_standard_total` is used in
    `admd_coldload_subtotal_1` too.

    Args:
        diversity_level: Diversity level, from `diversity_level`.
        N_storage_8kW: Number of households with this system.

    Returns:
        ADMD in kW of those households (a total, not a value per household).
    """
    return lookups.loc[diversity_level,'storage_8kW_standard_perunit'] * N_storage_8kW

def storage_16kW_standard(diversity_level:int,
                          N_storage_16kW:float
                          ) -> float:
    """ADMD of the households with a 16 kW storage heating system under standard (peak) conditions.

    The per-household demand at the diversity level (column
    `storage_16kW_standard_perunit` of `admd_lookups.csv`) multiplied by the number of
    households. The 16 kW size is for a 5+ bedroom house, with insulation to 1990s
    standard or better; the heating system is an electric storage heating system with a 16
    kW electrical rating which provides space heating only. Its undiversified demand is 16
    kW. The per-household value includes the base household demand. Spreadsheet row:
    "Calculate 16kW Storage Total".

    The spreadsheet has no separate cold load pickup values for storage heating, so there
    is no `storage_*_coldload` function: `storage_standard_total` is used in
    `admd_coldload_subtotal_1` too.

    Args:
        diversity_level: Diversity level, from `diversity_level`.
        N_storage_16kW: Number of households with this system.

    Returns:
        ADMD in kW of those households (a total, not a value per household).
    """
    return lookups.loc[diversity_level,'storage_16kW_standard_perunit'] * N_storage_16kW

def storage_standard_total(storage_5kW_standard:float,
                           storage_8kW_standard:float,
                           storage_16kW_standard:float
                        ) -> float:
    """Total ADMD of all electric storage heating households.

    Sum of the 5 kW, 8 kW and 16 kW results. The spreadsheet uses the same values for the
    standard and cold load pickup calculations. Spreadsheet row: "Calculate Storage Heating Total".

    Args:
        storage_5kW_standard: ADMD of the 5 kW systems.
        storage_8kW_standard: ADMD of the 8 kW systems.
        storage_16kW_standard: ADMD of the 16 kW systems.

    Returns:
        ADMD in kW of all households with storage heating.
    """
    return storage_5kW_standard + storage_8kW_standard + storage_16kW_standard

def N_ASHP(N_ASHP_5kW:float,
           N_ASHP_8kW:float,
           N_ASHP_16kW:float
           ) -> float:
    """Total number of households with air source heat pumps.

    Sum over the 5 kW, 8 kW and 16 kW sizes.

    Args:
        N_ASHP_5kW: Number of households with a 5 kW system.
        N_ASHP_8kW: Number of households with an 8 kW system.
        N_ASHP_16kW: Number of households with a 16 kW system.

    Returns:
        Number of households.
    """
    return N_ASHP_5kW + N_ASHP_8kW + N_ASHP_16kW

def N_GSHP(N_GSHP_5kW:float,
           N_GSHP_8kW:float,
           N_GSHP_16kW:float
           ) -> float:
    """Total number of households with ground source heat pumps.

    Sum over the 5 kW, 8 kW and 16 kW sizes.

    Args:
        N_GSHP_5kW: Number of households with a 5 kW system.
        N_GSHP_8kW: Number of households with an 8 kW system.
        N_GSHP_16kW: Number of households with a 16 kW system.

    Returns:
        Number of households.
    """
    return N_GSHP_5kW + N_GSHP_8kW + N_GSHP_16kW

def N_HyHP(N_HyHP_5kW:float,
           N_HyHP_8kW:float,
           N_HyHP_16kW:float
           ) -> float:
    """Total number of households with hybrid heat pumps.

    Sum over the 5 kW, 8 kW and 16 kW sizes.

    Args:
        N_HyHP_5kW: Number of households with a 5 kW system.
        N_HyHP_8kW: Number of households with an 8 kW system.
        N_HyHP_16kW: Number of households with a 16 kW system.

    Returns:
        Number of households.
    """
    return N_HyHP_5kW + N_HyHP_8kW + N_HyHP_16kW

def N_storage(N_storage_5kW:float,
              N_storage_8kW:float,
              N_storage_16kW:float
              ) -> float:
    """Total number of households with electric storage heating systems.

    Sum over the 5 kW, 8 kW and 16 kW sizes.

    Args:
        N_storage_5kW: Number of households with a 5 kW system.
        N_storage_8kW: Number of households with an 8 kW system.
        N_storage_16kW: Number of households with a 16 kW system.

    Returns:
        Number of households.
    """
    return N_storage_5kW + N_storage_8kW + N_storage_16kW

def N_no_lct(N_customers:int,
             N_EV_chargers:float,
             N_EV_and_HP:float,
             N_ASHP:float,
             N_GSHP:float,
             N_HyHP:float,
             N_storage:float
             ) -> float:
    """Number of standalone households, with no low carbon technology (LCT).

    The customers on the feeder, less those that have an EV charger without a heat pump
    (`N_EV_chargers - N_EV_and_HP`), and those with an ASHP, GSHP, hybrid heat pump or storage
    heating. Households with both an EV charger and a heat pump are removed with the heat
    pump households, so they are not removed twice. This is the quantity used in the spreadsheet
    row "Calculate Standalone Households Total (No LCTs)".

    Args:
        N_customers: Number of customers on the feeder.
        N_EV_chargers: Number of households with an EV charger.
        N_EV_and_HP: Number of households with both an EV charger and a heat pump.
        N_ASHP: Number of households with an ASHP, from `N_ASHP`.
        N_GSHP: Number of households with a GSHP, from `N_GSHP`.
        N_HyHP: Number of households with a hybrid heat pump, from `N_HyHP`.
        N_storage: Number of households with storage heating, from `N_storage`.

    Returns:
        Number of households with no LCT.
    """
    return N_customers - (N_EV_chargers - N_EV_and_HP) - N_ASHP - N_GSHP - N_HyHP - N_storage 

def no_lct_standard_total(diversity_level:int,
                          N_no_lct:float
                          ) -> float:
    """ADMD of the households with no low carbon technology.

    The house-only per-household demand at the diversity level (1.8 kW at 100 customers,
    rising to 7.11 kW for a single customer) multiplied by the number of such households.
    Used for both standard and cold load pickup. Spreadsheet row: "Calculate Standalone
    Households Total (No LCTs)".

    Args:
        diversity_level: Diversity level, from `diversity_level`.
        N_no_lct: Number of households with no LCT, from `N_no_lct`.

    Returns:
        ADMD in kW of the standalone households.
    """
    return lookups.loc[diversity_level,'house_only_per_unit'] * N_no_lct

def admd_standard_subtotal_1(EV_total:float,
                             ASHP_standard_total:float,
                             GSHP_standard_total:float,
                             HyHP_standard_total:float,
                             storage_standard_total:float,
                             no_lct_standard_total:float
                             ) -> float:
    """Sum of the standard ADMD of every group of households, before the EV and heat pump correction.

    Spreadsheet row: "Sub Total". Households that have both an EV charger and a heat
    pump are counted in both the EV and the heat pump totals, so this is an over-estimate that
    `ADMD_standard` corrects.

    Args:
        EV_total: ADMD of households with EV chargers, from `EV_total`.
        ASHP_standard_total: from `ASHP_standard_total`.
        GSHP_standard_total: from `GSHP_standard_total`.
        HyHP_standard_total: from `HyHP_standard_total`.
        storage_standard_total: from `storage_standard_total`.
        no_lct_standard_total: from `no_lct_standard_total`.

    Returns:
        ADMD in kW, before correction.
    """
    return EV_total + ASHP_standard_total + GSHP_standard_total + HyHP_standard_total + storage_standard_total + no_lct_standard_total

def ADMD_standard(diversity_level:int,
                  admd_standard_subtotal_1:float,
                  N_EV_and_HP:float
                  ) -> float:
    """After Diversity Maximum Demand of the feeder under standard conditions.

    The subtotal less a correction of `ev_hp_cofactor` (from `admd_lookups.csv`) for each
    household that has both an EV charger and a heat pump. Each of those households has been
    counted in both the EV and the heat pump totals, and each total includes the base
    household demand, so one base household demand is removed. The cofactor is 1.1 kW for 20
    or more customers (diversity levels 20 to 200), and the house-only demand for fewer.
    Spreadsheet rows: "Reduce load by required level Sub Total 2" and "Total ADMD".

    The result is the total for all customers; divide by the number of customers for the
    "Average kW ADMD Per House Hold".

    Note:
        The spreadsheet has a further row, "Calculate Battery ADMD Reduction Effect", which would
        reduce ADMD by 40% of the peak where there is sufficient battery capacity (at least three
        times the ADMD without a battery, in kWh). It refers to a missing cell (`#REF!`) in the
        spreadsheet, is not used in its total, and is not implemented here.

    Args:
        diversity_level: Diversity level, from `diversity_level`.
        admd_standard_subtotal_1: Subtotal, from `admd_standard_subtotal_1`.
        N_EV_and_HP: Number of households with both an EV charger and a heat pump.

    Returns:
        ADMD in kW of all customers on the feeder.
    """
    return (
        admd_standard_subtotal_1
            - N_EV_and_HP * lookups.loc[diversity_level,'ev_hp_cofactor']
    )

def ASHP_5kW_coldload(diversity_level:int,
                      N_ASHP_5kW:float
                      ) -> float:
    """ADMD of the households with a 5 kW ASHP under cold load pickup conditions.

    The per-household demand at the diversity level (column `ASHP_5kW_coldload_perunit` of
    `admd_lookups.csv`) multiplied by the number of households. The 5 kW size is for a 1-2
    bedroom house, with insulation to 1990s standard or better; the heating system is an
    air source heat pump (ASHP) with a 5 kW heat output which provides space heating and
    hot water and includes a direct electric backup heater. Its undiversified demand is
    3.38 kW electrical. The per- household value includes the base household demand.
    Spreadsheet row: "Calculate 5kW ASHP Total".

    Args:
        diversity_level: Diversity level, from `diversity_level`.
        N_ASHP_5kW: Number of households with this system.

    Returns:
        ADMD in kW of those households (a total, not a value per household).
    """
    return lookups.loc[diversity_level,'ASHP_5kW_coldload_perunit'] * N_ASHP_5kW

def ASHP_8kW_coldload(diversity_level:int,
                      N_ASHP_8kW:float
                      ) -> float:
    """ADMD of the households with a 8 kW ASHP under cold load pickup conditions.

    The per-household demand at the diversity level (column `ASHP_8kW_coldload_perunit` of
    `admd_lookups.csv`) multiplied by the number of households. The 8 kW size is for a 3-4
    bedroom house, with insulation to 1990s standard or better; the heating system is an
    air source heat pump (ASHP) with a 8 kW heat output which provides space heating and
    hot water and includes a direct electric backup heater. Its undiversified demand is
    6.55 kW electrical. The per- household value includes the base household demand.
    Spreadsheet row: "Calculate 8kW ASHP Total".

    Args:
        diversity_level: Diversity level, from `diversity_level`.
        N_ASHP_8kW: Number of households with this system.

    Returns:
        ADMD in kW of those households (a total, not a value per household).
    """
    return lookups.loc[diversity_level,'ASHP_8kW_coldload_perunit'] * N_ASHP_8kW

def ASHP_16kW_coldload(diversity_level:int,
                       N_ASHP_16kW:float
                       ) -> float:
    """ADMD of the households with a 16 kW ASHP under cold load pickup conditions.

    The per-household demand at the diversity level (column `ASHP_16kW_coldload_perunit`
    of `admd_lookups.csv`) multiplied by the number of households. The 16 kW size is for a
    5+ bedroom house, with insulation to 1990s standard or better; the heating system is
    an air source heat pump (ASHP) with a 16 kW heat output which provides space heating
    and hot water and includes a direct electric backup heater. Its undiversified demand
    is 13.12 kW electrical. The per-household value includes the base household demand.
    Spreadsheet row: "Calculate 16kW ASHP Total".

    Args:
        diversity_level: Diversity level, from `diversity_level`.
        N_ASHP_16kW: Number of households with this system.

    Returns:
        ADMD in kW of those households (a total, not a value per household).
    """
    return lookups.loc[diversity_level,'ASHP_16kW_coldload_perunit'] * N_ASHP_16kW

def ASHP_coldload_total(ASHP_5kW_coldload:float,
                        ASHP_8kW_coldload:float,
                        ASHP_16kW_coldload:float
                        ) -> float:
    """Total ADMD of all air source heat pump (ASHP) households under cold load pickup conditions.

    Sum of the 5 kW, 8 kW and 16 kW results. Spreadsheet row: "Calculate ASHP Total".

    Args:
        ASHP_5kW_coldload: ADMD of the 5 kW systems.
        ASHP_8kW_coldload: ADMD of the 8 kW systems.
        ASHP_16kW_coldload: ADMD of the 16 kW systems.

    Returns:
        ADMD in kW of all households with this system.
    """
    return ASHP_5kW_coldload + ASHP_8kW_coldload + ASHP_16kW_coldload

def GSHP_5kW_coldload(diversity_level:int,
                      N_GSHP_5kW:float
                      ) -> float:
    """ADMD of the households with a 5 kW GSHP under cold load pickup conditions.

    The per-household demand at the diversity level (column `GSHP_5kW_coldload_perunit` of
    `admd_lookups.csv`) multiplied by the number of households. The 5 kW size is for a 1-2
    bedroom house, with insulation to 1990s standard or better; the heating system is an
    ground source heat pump (GSHP) with a 5 kW heat output which provides space heating
    and hot water and has no backup heater. Its undiversified demand is 2.6 kW electrical.
    The per-household value includes the base household demand. Spreadsheet row:
    "Calculate 5kW GSHP Total".

    Args:
        diversity_level: Diversity level, from `diversity_level`.
        N_GSHP_5kW: Number of households with this system.

    Returns:
        ADMD in kW of those households (a total, not a value per household).
    """
    return lookups.loc[diversity_level,'GSHP_5kW_coldload_perunit'] * N_GSHP_5kW

def GSHP_8kW_coldload(diversity_level:int,
                      N_GSHP_8kW:float
                      ) -> float:
    """ADMD of the households with a 8 kW GSHP under cold load pickup conditions.

    The per-household demand at the diversity level (column `GSHP_8kW_coldload_perunit` of
    `admd_lookups.csv`) multiplied by the number of households. The 8 kW size is for a 3-4
    bedroom house, with insulation to 1990s standard or better; the heating system is an
    ground source heat pump (GSHP) with a 8 kW heat output which provides space heating
    and hot water and has no backup heater. Its undiversified demand is 3.8 kW electrical.
    The per-household value includes the base household demand. Spreadsheet row:
    "Calculate 8kW GSHP Total".

    Args:
        diversity_level: Diversity level, from `diversity_level`.
        N_GSHP_8kW: Number of households with this system.

    Returns:
        ADMD in kW of those households (a total, not a value per household).
    """
    return lookups.loc[diversity_level,'GSHP_8kW_coldload_perunit'] * N_GSHP_8kW

def GSHP_16kW_coldload(diversity_level:int,
                       N_GSHP_16kW:float
                       ) -> float:
    """ADMD of the households with a 16 kW GSHP under cold load pickup conditions.

    The per-household demand at the diversity level (column `GSHP_16kW_coldload_perunit`
    of `admd_lookups.csv`) multiplied by the number of households. The 16 kW size is for a
    5+ bedroom house, with insulation to 1990s standard or better; the heating system is
    an ground source heat pump (GSHP) with a 16 kW heat output which provides space
    heating and hot water and has no backup heater. Its undiversified demand is 6.5 kW
    electrical. The per-household value includes the base household demand. Spreadsheet
    row: "Calculate 16kW GSHP Total".

    Args:
        diversity_level: Diversity level, from `diversity_level`.
        N_GSHP_16kW: Number of households with this system.

    Returns:
        ADMD in kW of those households (a total, not a value per household).
    """
    return lookups.loc[diversity_level,'GSHP_16kW_coldload_perunit'] * N_GSHP_16kW

def GSHP_coldload_total(GSHP_5kW_coldload:float,
                        GSHP_8kW_coldload:float,
                        GSHP_16kW_coldload:float
                        ) -> float:
    """Total ADMD of all ground source heat pump (GSHP) households under cold load pickup conditions.

    Sum of the 5 kW, 8 kW and 16 kW results. Spreadsheet row: "Calculate GSHP Total".

    Args:
        GSHP_5kW_coldload: ADMD of the 5 kW systems.
        GSHP_8kW_coldload: ADMD of the 8 kW systems.
        GSHP_16kW_coldload: ADMD of the 16 kW systems.

    Returns:
        ADMD in kW of all households with this system.
    """
    return GSHP_5kW_coldload + GSHP_8kW_coldload + GSHP_16kW_coldload

def HyHP_5kW_coldload(diversity_level:int,
                      N_HyHP_5kW:float
                      ) -> float:
    """ADMD of the households with a 5 kW HyHP under cold load pickup conditions.

    The per-household demand at the diversity level (column `HyHP_5kW_coldload_perunit` of
    `admd_lookups.csv`) multiplied by the number of households. The 5 kW size is for a 1-2
    bedroom house, with insulation to 1990s standard or better; the heating system is an
    hybrid heat pump with a 5 kW heat output which provides space heating and hot water,
    has no backup heater and is bi-valent: it switches to gas when the outside temperature
    falls below a threshold (8 °C in the spreadsheet). Its undiversified demand is 1.22 kW
    electrical. The per-household value includes the base household demand. Spreadsheet
    row: "Calculate 5kW Hybrid Total".

    Args:
        diversity_level: Diversity level, from `diversity_level`.
        N_HyHP_5kW: Number of households with this system.

    Returns:
        ADMD in kW of those households (a total, not a value per household).
    """
    return lookups.loc[diversity_level,'HyHP_5kW_coldload_perunit'] * N_HyHP_5kW

def HyHP_8kW_coldload(diversity_level:int,
                      N_HyHP_8kW:float
                      ) -> float:
    """ADMD of the households with a 8 kW HyHP under cold load pickup conditions.

    The per-household demand at the diversity level (column `HyHP_8kW_coldload_perunit` of
    `admd_lookups.csv`) multiplied by the number of households. The 8 kW size is for a 3-4
    bedroom house, with insulation to 1990s standard or better; the heating system is an
    hybrid heat pump with a 8 kW heat output which provides space heating and hot water,
    has no backup heater and is bi-valent: it switches to gas when the outside temperature
    falls below a threshold (8 °C in the spreadsheet). Its undiversified demand is 2.69 kW
    electrical. The per-household value includes the base household demand. Spreadsheet
    row: "Calculate 8kW Hybrid Total".

    Args:
        diversity_level: Diversity level, from `diversity_level`.
        N_HyHP_8kW: Number of households with this system.

    Returns:
        ADMD in kW of those households (a total, not a value per household).
    """
    return lookups.loc[diversity_level,'HyHP_8kW_coldload_perunit'] * N_HyHP_8kW

def HyHP_16kW_coldload(diversity_level:int,
                       N_HyHP_16kW:float
                       ) -> float:
    """ADMD of the households with a 16 kW HyHP under cold load pickup conditions.

    The per-household demand at the diversity level (column `HyHP_16kW_coldload_perunit`
    of `admd_lookups.csv`) multiplied by the number of households. The 16 kW size is for a
    5+ bedroom house, with insulation to 1990s standard or better; the heating system is
    an hybrid heat pump with a 16 kW heat output which provides space heating and hot
    water, has no backup heater and is bi-valent: it switches to gas when the outside
    temperature falls below a threshold (8 °C in the spreadsheet). Its undiversified
    demand is 4.57 kW electrical. The per- household value includes the base household
    demand. Spreadsheet row: "Calculate 16kW Hybrid Total".

    Args:
        diversity_level: Diversity level, from `diversity_level`.
        N_HyHP_16kW: Number of households with this system.

    Returns:
        ADMD in kW of those households (a total, not a value per household).
    """
    return lookups.loc[diversity_level,'HyHP_16kW_coldload_perunit'] * N_HyHP_16kW

def HyHP_coldload_total(HyHP_5kW_coldload:float,
                        HyHP_8kW_coldload:float,
                        HyHP_16kW_coldload:float
                        ) -> float:
    """Total ADMD of all hybrid heat pump households under cold load pickup conditions.

    Sum of the 5 kW, 8 kW and 16 kW results. Spreadsheet row: "Calculate Hybrid Total".

    Args:
        HyHP_5kW_coldload: ADMD of the 5 kW systems.
        HyHP_8kW_coldload: ADMD of the 8 kW systems.
        HyHP_16kW_coldload: ADMD of the 16 kW systems.

    Returns:
        ADMD in kW of all households with this system.
    """
    return HyHP_5kW_coldload + HyHP_8kW_coldload + HyHP_16kW_coldload

def admd_coldload_subtotal_1(EV_total:float,
                             ASHP_coldload_total:float,
                             GSHP_coldload_total:float,
                             HyHP_coldload_total:float,
                             storage_standard_total:float,
                             no_lct_standard_total:float
                             ) -> float:
    """Sum of the cold load pickup ADMD of every group of households, before correction.

    As `admd_standard_subtotal_1`, using the cold load pickup values for heat pumps. EV, storage
    heating and standalone households use the same values as the standard calculation.
    Spreadsheet row: "Sub Total", cold load column.

    Args:
        EV_total: ADMD of households with EV chargers, from `EV_total`.
        ASHP_coldload_total: from `ASHP_coldload_total`.
        GSHP_coldload_total: from `GSHP_coldload_total`.
        HyHP_coldload_total: from `HyHP_coldload_total`.
        storage_standard_total: from `storage_standard_total`.
        no_lct_standard_total: from `no_lct_standard_total`.

    Returns:
        ADMD in kW, before correction.
    """
    return EV_total + ASHP_coldload_total + GSHP_coldload_total + HyHP_coldload_total + storage_standard_total + no_lct_standard_total

def ADMD_coldload(diversity_level:int,
                  admd_coldload_subtotal_1:float,
                  N_EV_and_HP:float
                  ) -> float:
    """After Diversity Maximum Demand of the feeder under cold load pickup conditions.

    Cold load pickup is the demand when supply is restored after an interruption, when
    thermostatically controlled heating loads are running simultaneously. The result is the
    subtotal less a correction for households with both an EV charger and a heat pump, as in
    `ADMD_standard`, but using `ev_hp_coldload_cofactor` (the house-only demand at the diversity
    level). Spreadsheet column: "Cold Load Pickup".

    Args:
        diversity_level: Diversity level, from `diversity_level`.
        admd_coldload_subtotal_1: Subtotal, from `admd_coldload_subtotal_1`.
        N_EV_and_HP: Number of households with both an EV charger and a heat pump.

    Returns:
        ADMD in kW of all customers on the feeder.
    """
    return (
        admd_coldload_subtotal_1
            - N_EV_and_HP * lookups.loc[diversity_level,'ev_hp_coldload_cofactor']
    )
    
def ASHP_count(type_:np.ndarray[tuple[int], np.dtype[str]],
               beds:np.ndarray[tuple[int], np.dtype[int]]
               ) -> dict:
    """Count of air source heat pump systems by size for a set of dwellings, assuming one per dwelling.

    Sizes the system by dwelling, following the sizing of the calculator's assumptions:
    apartments and houses with fewer than 3 bedrooms get 5 kW; houses with 3 or 4 bedrooms
    get 8 kW; houses with 5 or more bedrooms get 16 kW. (The spreadsheet instead takes a
    number of systems and one average size for each of three bedroom bands. Treating
    apartments as 5 kW is an assumption of this function.) The result provides the
    `N_ASHP_*kW` inputs of the calculation. `ASHP_count`, `GSHP_count`, `HyHP_count` and
    `storage_count` all use the same rule.

    Args:
        type_: Array of dwelling types; `'apt'` for an apartment, anything else is a house.
        beds: Array of number of bedrooms of the dwellings.

    Returns:
        Dict of `N_ASHP_5kW`, `N_ASHP_8kW` and `N_ASHP_16kW` - the number of
        dwellings in each size band.
    """
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

def GSHP_count(type_:np.ndarray[tuple[int], np.dtype[str]],
               beds:np.ndarray[tuple[int], np.dtype[int]]
               ) -> dict:
    """Count of ground source heat pump systems by size for a set of dwellings, assuming one per dwelling.

    Sizes the system by dwelling, following the sizing of the calculator's assumptions:
    apartments and houses with fewer than 3 bedrooms get 5 kW; houses with 3 or 4 bedrooms
    get 8 kW; houses with 5 or more bedrooms get 16 kW. (The spreadsheet instead takes a
    number of systems and one average size for each of three bedroom bands. Treating
    apartments as 5 kW is an assumption of this function.) The result provides the
    `N_GSHP_*kW` inputs of the calculation. `ASHP_count`, `GSHP_count`, `HyHP_count` and
    `storage_count` all use the same rule.

    Args:
        type_: Array of dwelling types; `'apt'` for an apartment, anything else is a house.
        beds: Array of number of bedrooms of the dwellings.

    Returns:
        Dict of `N_GSHP_5kW`, `N_GSHP_8kW` and `N_GSHP_16kW` - the number of
        dwellings in each size band.
    """
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

def HyHP_count(type_:np.ndarray[tuple[int], np.dtype[str]],
               beds:np.ndarray[tuple[int], np.dtype[int]]
               ) -> dict:
    """Count of hybrid heat pump systems by size for a set of dwellings, assuming one per dwelling.

    Sizes the system by dwelling, following the sizing of the calculator's assumptions:
    apartments and houses with fewer than 3 bedrooms get 5 kW; houses with 3 or 4 bedrooms
    get 8 kW; houses with 5 or more bedrooms get 16 kW. (The spreadsheet instead takes a
    number of systems and one average size for each of three bedroom bands. Treating
    apartments as 5 kW is an assumption of this function.) The result provides the
    `N_HyHP_*kW` inputs of the calculation. `ASHP_count`, `GSHP_count`, `HyHP_count` and
    `storage_count` all use the same rule.

    Args:
        type_: Array of dwelling types; `'apt'` for an apartment, anything else is a house.
        beds: Array of number of bedrooms of the dwellings.

    Returns:
        Dict of `N_HyHP_5kW`, `N_HyHP_8kW` and `N_HyHP_16kW` - the number of
        dwellings in each size band.
    """
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

def storage_count(
    type_:np.ndarray[tuple[int], np.dtype[str]],
    beds:np.ndarray[tuple[int], np.dtype[int]]
    ) -> dict:
    """Count of storage heating systems by size for a set of dwellings, assuming one per dwelling.

    Sizes the system by dwelling, following the sizing of the calculator's assumptions:
    apartments and houses with fewer than 3 bedrooms get 5 kW; houses with 3 or 4 bedrooms
    get 8 kW; houses with 5 or more bedrooms get 16 kW. (The spreadsheet instead takes a
    number of systems and one average size for each of three bedroom bands. Treating
    apartments as 5 kW is an assumption of this function.) The result provides the
    `N_storage_*kW` inputs of the calculation. `ASHP_count`, `GSHP_count`, `HyHP_count` and
    `storage_count` all use the same rule.

    Args:
        type_: Array of dwelling types; `'apt'` for an apartment, anything else is a house.
        beds: Array of number of bedrooms of the dwellings.

    Returns:
        Dict of `N_storage_5kW`, `N_storage_8kW` and `N_storage_16kW` - the number of
        dwellings in each size band.
    """
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
